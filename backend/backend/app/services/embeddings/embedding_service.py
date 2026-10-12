from abc import ABC, abstractmethod
from typing import List, Optional
import os
from app.core.config import settings
from app.core.logging_config import logger

class EmbeddingService(ABC):
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding vector for a single query text."""
        pass

    def embed_query(self, text: str) -> List[float]:
        """Alias for embed_text."""
        return self.embed_text(text)

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for a batch of document texts."""
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """Return the vector dimensionality of the embedding model."""
        pass


class FastEmbedEmbeddingService(EmbeddingService):
    """
    Local embedding service powered by FastEmbed (ONNX runtime).
    Requires zero external API keys, generates real dense semantic vectors.
    """
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.model_name = model_name
        self._model = None
        self._dimension = 384  # default for bge-small-en-v1.5

    def _get_model(self):
        if self._model is None:
            logger.info(f"Initializing FastEmbed model: {self.model_name}")
            from fastembed import TextEmbedding
            self._model = TextEmbedding(model_name=self.model_name)
            # Determine dimension dynamically
            test_emb = list(self._model.embed(["test"]))
            self._dimension = len(test_emb[0])
            logger.info(f"FastEmbed model loaded. Vector dimension: {self._dimension}")
        return self._model

    def embed_text(self, text: str) -> List[float]:
        model = self._get_model()
        vectors = list(model.embed([text]))
        return vectors[0].tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        model = self._get_model()
        vectors = list(model.embed(texts))
        return [v.tolist() for v in vectors]

    def get_dimension(self) -> int:
        if self._model is None:
            self._get_model()
        return self._dimension


class OpenAIEmbeddingService(EmbeddingService):
    """
    OpenAI embedding provider (e.g. text-embedding-3-small).
    Requires EMBEDDING_API_KEY or OPENAI_API_KEY.
    """
    def __init__(self, model_name: str = "text-embedding-3-small", api_key: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key or settings.EMBEDDING_API_KEY or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "EMBEDDING_API_KEY is required for OpenAI embedding provider. "
                "Set it in .env or switch EMBEDDING_PROVIDER=fastembed."
            )
        from openai import OpenAI
        self.client = OpenAI(api_key=self.api_key)
        self._dimension = 1536 if "small" in model_name or "ada" in model_name else 3072

    def embed_text(self, text: str) -> List[float]:
        response = self.client.embeddings.create(
            input=[text],
            model=self.model_name
        )
        return response.data[0].embedding

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        # Batch requests up to 100 texts at a time
        batch_size = 100
        all_embeddings: List[List[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = self.client.embeddings.create(
                input=batch,
                model=self.model_name
            )
            # Sort by index to maintain ordering
            sorted_data = sorted(response.data, key=lambda x: x.index)
            all_embeddings.extend([d.embedding for d in sorted_data])
        return all_embeddings

    def get_dimension(self) -> int:
        return self._dimension


_embedding_service_instance: Optional[EmbeddingService] = None

def get_embedding_service() -> EmbeddingService:
    """Singleton getter for the configured embedding service."""
    global _embedding_service_instance
    if _embedding_service_instance is None:
        provider = settings.EMBEDDING_PROVIDER.lower().strip()
        model = settings.EMBEDDING_MODEL
        logger.info(f"Creating EmbeddingService for provider: {provider}, model: {model}")
        if provider == "fastembed":
            _embedding_service_instance = FastEmbedEmbeddingService(model_name=model)
        elif provider == "openai":
            _embedding_service_instance = OpenAIEmbeddingService(
                model_name=model,
                api_key=settings.EMBEDDING_API_KEY
            )
        else:
            raise ValueError(f"Unsupported EMBEDDING_PROVIDER: '{provider}'. Supported: fastembed, openai")
    return _embedding_service_instance
