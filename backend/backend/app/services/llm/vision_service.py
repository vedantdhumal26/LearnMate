import base64
import os
from typing import Optional
from openai import OpenAI
from app.core.config import settings
from app.core.logging_config import logger

class VisionService:
    """
    OpenAI-compatible Vision Service for diagram and visual extraction (Phase 4A).
    Supports Groq, OpenAI, and other vision-capable multimodal endpoints.
    """
    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        enabled: Optional[bool] = None,
    ):
        self.provider = (provider or settings.VISION_PROVIDER).lower().strip()
        self.model = model or settings.VISION_MODEL
        self.enabled = settings.VISION_ENABLED if enabled is None else enabled

        # Resolve API key: fallback to LLM_API_KEY or provider-specific env var
        resolved_key = api_key or settings.VISION_API_KEY or settings.LLM_API_KEY
        if self.provider == "groq" and not resolved_key:
            resolved_key = os.getenv("GROQ_API_KEY")
        elif self.provider == "openai" and not resolved_key:
            resolved_key = os.getenv("OPENAI_API_KEY")
        self.api_key = resolved_key

        # Resolve Base URL
        if base_url:
            self.base_url = base_url
        elif settings.VISION_BASE_URL:
            self.base_url = settings.VISION_BASE_URL
        elif self.provider == "groq":
            self.base_url = "https://api.groq.com/openai/v1"
        elif self.provider == "ollama":
            self.base_url = "http://localhost:11434/v1"
        else:
            self.base_url = settings.LLM_BASE_URL

        self._client: Optional[OpenAI] = None
        if self.enabled and self.api_key:
            try:
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url
                )
                logger.info(
                    f"Initialized VisionService: provider='{self.provider}', model='{self.model}', base_url='{self.base_url}'"
                )
            except Exception as e:
                logger.warning(f"Could not initialize Vision client: {e}. Visual descriptions will use fallback.")
        else:
            logger.info("VisionService initialized without active API key or disabled; will use fallback descriptions.")

    def describe_image(
        self,
        image_bytes: bytes,
        mime_type: str = "image/png",
        slide_number: Optional[int] = None,
        media_filename: Optional[str] = None,
    ) -> str:
        """
        Generate a concise, factual, searchable description of a slide diagram or image.
        If vision is disabled or fails, returns a safe fallback without throwing an exception.
        """
        fallback_desc = (
            f"Visual diagram/image from Slide {slide_number} ({media_filename})"
            if slide_number and media_filename
            else "Extracted slide diagram/visual"
        )

        if not self.enabled or not self._client:
            logger.debug("Vision processing disabled or client uninitialized; using fallback description.")
            return fallback_desc

        try:
            b64_data = base64.b64encode(image_bytes).decode("utf-8")
            data_url = f"data:{mime_type};base64,{b64_data}"

            prompt = (
                "You are an expert technical diagram and visual analyst for course materials.\n"
                "Analyze the provided image from a course presentation slide.\n"
                "Generate a concise, factual, and searchable description suitable for document retrieval:\n"
                "1. What the diagram, chart, equation, or image represents.\n"
                "2. Visible labels, variables, and components.\n"
                "3. Important relationships, directions, arrows, or trends shown.\n"
                "4. Any visible formulas or text exactly as written.\n"
                "5. Avoid speculating or inventing information that is not clearly visible.\n"
                "Provide only the factual description in 2 to 4 concise sentences."
            )

            from app.services.llm.concurrency_gate import get_llm_gate, RequestPriority
            gate = get_llm_gate()
            with gate.limit(priority=RequestPriority.EVALUATION, request_type="vision"):
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": data_url}
                                }
                            ]
                        }
                    ],
                    temperature=0.1,
                    max_tokens=250,
                )

            desc = response.choices[0].message.content or ""
            desc = desc.strip()
            if desc:
                logger.info(f"Generated vision description ({len(desc)} chars) for slide {slide_number} image {media_filename}")
                return desc
            return fallback_desc

        except Exception as e:
            logger.warning(
                f"Vision model description failed for slide {slide_number} image '{media_filename}': {e}. "
                "Preserving chunk with fallback description."
            )
            return fallback_desc

def get_vision_service() -> VisionService:
    """Factory function for VisionService."""
    return VisionService()
