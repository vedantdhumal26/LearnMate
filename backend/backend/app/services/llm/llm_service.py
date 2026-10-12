from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import os
import re
import time
from openai import OpenAI, RateLimitError, APITimeoutError, APIConnectionError

from app.core.config import settings
from app.core.logging_config import logger
from app.services.llm.concurrency_gate import get_llm_gate, get_priority_for_type, RequestPriority
from app.services.llm.observability import estimate_tokens, log_llm_request_metric


class LLMError(RuntimeError):
    """Base exception for LLM service errors."""
    pass


class LLMRateLimitError(LLMError):
    """Raised when LLM provider rate limits are exceeded or retry budget is exhausted."""
    pass


class LLMTimeoutError(LLMError):
    """Raised when LLM provider request times out."""
    pass


def parse_provider_retry_after(error: Exception) -> Optional[float]:
    """
    Extract provider-requested wait duration in seconds from HTTP headers or message body.
    Supports formats like:
      - '2.5s', '1m30s', '450ms', '4m12.5s'
      - retry-after HTTP headers
      - x-ratelimit-reset-tokens / x-ratelimit-reset-requests headers
    """
    # 1. Inspect HTTP response headers
    response = getattr(error, "response", None)
    if response is not None and hasattr(response, "headers"):
        headers = response.headers
        ra = headers.get("retry-after")
        if ra:
            try:
                return float(ra)
            except ValueError:
                pass
        for header_key in ("x-ratelimit-reset-tokens", "x-ratelimit-reset-requests"):
            h_val = headers.get(header_key)
            if h_val:
                m_h = re.search(r"(?:(\d+)h)?(?:(\d+)m)?(?:([\d\.]+)s)?(?:(\d+)ms)?", str(h_val).lower())
                if m_h and any(m_h.groups()):
                    h_val_s = (
                        (float(m_h.group(1)) * 3600 if m_h.group(1) else 0)
                        + (float(m_h.group(2)) * 60 if m_h.group(2) else 0)
                        + (float(m_h.group(3)) if m_h.group(3) else 0)
                        + (float(m_h.group(4)) / 1000.0 if m_h.group(4) else 0)
                    )
                    if h_val_s > 0:
                        return h_val_s

    # 2. Inspect error message regex
    err_str = str(error).lower()
    m = re.search(r"try again in (?:(\d+)h)?(?:(\d+)m)?(?:([\d\.]+)s)?(?:(\d+)ms)?", err_str)
    if m and any(m.groups()):
        total = (
            (float(m.group(1)) * 3600 if m.group(1) else 0)
            + (float(m.group(2)) * 60 if m.group(2) else 0)
            + (float(m.group(3)) if m.group(3) else 0)
            + (float(m.group(4)) / 1000.0 if m.group(4) else 0)
        )
        if total > 0:
            return total

    m2 = re.search(r"retry after ([\d\.]+) seconds?", err_str)
    if m2:
        try:
            return float(m2.group(1))
        except ValueError:
            pass

    return None


class LLMService(ABC):
    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """
        Generate completion from LLM using provider-independent interface.
        """
        pass


class OpenAILLMService(LLMService):
    """
    OpenAI-compatible LLM service supporting OpenAI, Groq, Ollama, and other compatible endpoints.
    Protected by the process-wide priority concurrency gate and rate pacer.
    """
    def __init__(
        self,
        provider: str = "openai",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.provider = provider.lower().strip()
        self.model = model or settings.LLM_MODEL
        self.api_key = api_key or settings.LLM_API_KEY or os.getenv("OPENAI_API_KEY")

        # Resolve custom base URLs
        if base_url:
            self.base_url = base_url
        elif self.provider == "groq":
            self.base_url = "https://api.groq.com/openai/v1"
            self.api_key = self.api_key or os.getenv("GROQ_API_KEY")
        elif self.provider == "ollama":
            self.base_url = "http://localhost:11434/v1"
            self.api_key = self.api_key or "ollama"
        else:
            self.base_url = settings.LLM_BASE_URL

        # Validate credentials for providers that require API keys
        if self.provider in ["openai", "groq"] and not self.api_key:
            raise ValueError(
                f"LLM_API_KEY is required for provider '{self.provider}'. "
                f"Please set LLM_API_KEY in your .env file or environment variables."
            )

        # Finite HTTP timeouts: connect=5s, read=25s, write=5s, total=30s
        from httpx import Timeout
        self.timeout = Timeout(30.0, connect=5.0, read=25.0, write=5.0)

        self.client = OpenAI(
            api_key=self.api_key or "no-key-required",
            base_url=self.base_url,
            timeout=self.timeout
        )
        logger.info(
            f"Initialized LLM service: provider='{self.provider}', model='{self.model}', base_url='{self.base_url}', timeout={self.timeout}"
        )

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        request_type: Optional[str] = None,
        priority: Optional[int] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Resolve effective request type and priority
        eff_type = request_type or "tutor"
        eff_priority = priority if priority is not None else get_priority_for_type(eff_type)

        # Output token bounds
        if max_tokens is None:
            if eff_priority == RequestPriority.TUTOR:
                eff_max_tokens = 600
            elif eff_priority == RequestPriority.ASSESSMENT:
                eff_max_tokens = 800
            else:  # EVALUATION
                eff_max_tokens = 600
        else:
            eff_max_tokens = max_tokens

        # Estimate input token count safely
        estimated_input_tokens = estimate_tokens(system_prompt) + estimate_tokens(prompt)

        # Bounded retry configuration (Evaluation uses max 1 attempt to fail-fast)
        if eff_priority == RequestPriority.EVALUATION or eff_type == "evaluation":
            max_retries = 1
        else:
            max_retries = getattr(settings, "LLM_MAX_RETRIES", 2)
        max_delay_per_retry = getattr(settings, "LLM_MAX_RETRY_DELAY_SECONDS", 3.0)
        max_cumulative_wait = getattr(settings, "LLM_MAX_CUMULATIVE_RETRY_WAIT_SECONDS", 5.0)

        total_waited = 0.0
        gate = get_llm_gate()

        # Gate acquisition (Tutor jumps ahead of Evaluation)
        with gate.limit(priority=eff_priority, request_type=eff_type):
            call_start_time = time.time()
            for attempt in range(max_retries):
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=0.1,  # Low temperature for factual, grounded answers
                        max_tokens=eff_max_tokens,
                        timeout=25.0,
                    )
                    content = response.choices[0].message.content or ""
                    
                    # Compute output token count
                    output_tokens = 0
                    if getattr(response, "usage", None):
                        output_tokens = getattr(response.usage, "completion_tokens", 0) or 0
                    if output_tokens == 0:
                        output_tokens = estimate_tokens(content)

                    duration = time.time() - call_start_time
                    log_llm_request_metric(
                        request_type=eff_type,
                        model=self.model,
                        start_time=call_start_time,
                        duration=duration,
                        status_str="success",
                        input_tokens=estimated_input_tokens,
                        output_tokens=output_tokens,
                        retry_count=attempt
                    )
                    return content.strip()

                except RateLimitError as e:
                    provider_wait = parse_provider_retry_after(e)
                    cooldown = provider_wait if provider_wait is not None else 3.0
                    gate.record_rate_limit(duration=min(max(cooldown, 2.0), 10.0), reason=str(e)[:100])

                    # Evaluation fail-fast: do not retry
                    if eff_priority == RequestPriority.EVALUATION or eff_type == "evaluation":
                        logger.warning(
                            f"Evaluation request hit rate limit (429) on '{self.model}'. "
                            f"Failing fast without retry to protect user-facing traffic."
                        )
                        duration = time.time() - call_start_time
                        log_llm_request_metric(
                            request_type=eff_type,
                            model=self.model,
                            start_time=call_start_time,
                            duration=duration,
                            status_str="429",
                            input_tokens=estimated_input_tokens,
                            output_tokens=0,
                            retry_count=attempt,
                            error_msg=str(e)
                        )
                        raise LLMRateLimitError("AI service is temporarily busy. Please try again.")

                    # If provider asks to wait longer than bounded threshold, fail immediately
                    if provider_wait is not None and provider_wait > max_delay_per_retry:
                        logger.warning(
                            f"Provider rate limit hit on '{self.model}'. Required wait ({provider_wait:.1f}s) "
                            f"exceeds retry threshold ({max_delay_per_retry}s). Failing promptly without sleep."
                        )
                        duration = time.time() - call_start_time
                        log_llm_request_metric(
                            request_type=eff_type,
                            model=self.model,
                            start_time=call_start_time,
                            duration=duration,
                            status_str="429",
                            input_tokens=estimated_input_tokens,
                            output_tokens=0,
                            retry_count=attempt,
                            error_msg=str(e)
                        )
                        raise LLMRateLimitError("AI service is temporarily busy. Please try again.")

                    if attempt < max_retries - 1 and (total_waited + max_delay_per_retry) <= max_cumulative_wait:
                        wait_time = min(provider_wait if provider_wait is not None else 1.5, max_delay_per_retry)
                        total_waited += wait_time
                        logger.warning(
                            f"Provider rate limit hit (429). Waiting {wait_time:.1f}s before bounded retry "
                            f"({attempt + 1}/{max_retries})..."
                        )
                        time.sleep(wait_time)
                        continue

                    logger.warning(
                        f"Provider rate limit exhausted for '{self.model}' after {attempt + 1} attempts "
                        f"({total_waited:.1f}s waited). Failing fast."
                    )
                    duration = time.time() - call_start_time
                    log_llm_request_metric(
                        request_type=eff_type,
                        model=self.model,
                        start_time=call_start_time,
                        duration=duration,
                        status_str="429",
                        input_tokens=estimated_input_tokens,
                        output_tokens=0,
                        retry_count=attempt,
                        error_msg=str(e)
                    )
                    raise LLMRateLimitError("AI service is temporarily busy. Please try again.")

                except (APITimeoutError, TimeoutError) as e:
                    logger.error(f"Timeout calling LLM provider '{self.provider}' ({self.model}): {e}")
                    duration = time.time() - call_start_time
                    log_llm_request_metric(
                        request_type=eff_type,
                        model=self.model,
                        start_time=call_start_time,
                        duration=duration,
                        status_str="timeout",
                        input_tokens=estimated_input_tokens,
                        output_tokens=0,
                        retry_count=attempt,
                        error_msg=str(e)
                    )
                    raise LLMTimeoutError("AI service request timed out. Please try again.")

                except Exception as e:
                    err_str = str(e).lower()
                    if "429" in err_str or "rate_limit" in err_str or "rate limit" in err_str:
                        provider_wait = parse_provider_retry_after(e)
                        if provider_wait is not None and provider_wait > max_delay_per_retry:
                            duration = time.time() - call_start_time
                            log_llm_request_metric(
                                request_type=eff_type,
                                model=self.model,
                                start_time=call_start_time,
                                duration=duration,
                                status_str="429",
                                input_tokens=estimated_input_tokens,
                                output_tokens=0,
                                retry_count=attempt,
                                error_msg=str(e)
                            )
                            raise LLMRateLimitError("AI service is temporarily busy. Please try again.")

                        if attempt < max_retries - 1 and (total_waited + 1.5) <= max_cumulative_wait:
                            wait_time = min(provider_wait if provider_wait is not None else 1.5, max_delay_per_retry)
                            total_waited += wait_time
                            logger.warning(f"Rate limit detected. Waiting {wait_time:.1f}s before retry...")
                            time.sleep(wait_time)
                            continue
                        duration = time.time() - call_start_time
                        log_llm_request_metric(
                            request_type=eff_type,
                            model=self.model,
                            start_time=call_start_time,
                            duration=duration,
                            status_str="429",
                            input_tokens=estimated_input_tokens,
                            output_tokens=0,
                            retry_count=attempt,
                            error_msg=str(e)
                        )
                        raise LLMRateLimitError("AI service is temporarily busy. Please try again.")

                    if "timeout" in err_str or "timed out" in err_str:
                        duration = time.time() - call_start_time
                        log_llm_request_metric(
                            request_type=eff_type,
                            model=self.model,
                            start_time=call_start_time,
                            duration=duration,
                            status_str="timeout",
                            input_tokens=estimated_input_tokens,
                            output_tokens=0,
                            retry_count=attempt,
                            error_msg=str(e)
                        )
                        raise LLMTimeoutError("AI service request timed out. Please try again.")

                    duration = time.time() - call_start_time
                    log_llm_request_metric(
                        request_type=eff_type,
                        model=self.model,
                        start_time=call_start_time,
                        duration=duration,
                        status_str="error",
                        input_tokens=estimated_input_tokens,
                        output_tokens=0,
                        retry_count=attempt,
                        error_msg=str(e)
                    )
                    logger.error(f"Error calling LLM provider '{self.provider}' ({self.model}): {e}")
                    raise RuntimeError(f"LLM generation failed: {e}")


def get_llm_service() -> LLMService:
    """Factory function to instantiate the configured LLM service."""
    provider = settings.LLM_PROVIDER.lower().strip()
    return OpenAILLMService(
        provider=provider,
        model=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL
    )
