from typing import List
from app.services.embeddings.embedding_service import EmbeddingService, get_embedding_service
from app.services.vector_store.base import VectorStore, VectorSearchResult
from app.services.vector_store.qdrant_store import get_vector_store
from app.core.config import settings
from app.core.logging_config import logger

class CourseRetriever:
    def __init__(
        self,
        embedding_service: EmbeddingService = None,
        vector_store: VectorStore = None
    ):
        self.embedding_service = embedding_service or get_embedding_service()
        self.vector_store = vector_store or get_vector_store()

    def retrieve(
        self,
        course_id: str,
        query: str,
        top_k: int = None,
        score_threshold: float = None
    ) -> List[VectorSearchResult]:
        """
        Embed the query and retrieve relevant chunks filtered strictly by course_id.
        """
        top_k = top_k or settings.RAG_TOP_K
        score_threshold = score_threshold if score_threshold is not None else settings.RAG_SCORE_THRESHOLD

        logger.info(f"Retrieving top {top_k} chunks for course {course_id}, query: '{query}'")

        # 1. Generate query embedding
        query_vector = self.embedding_service.embed_text(query)

        # 2. Search vector store with strict course_id filter
        results = self.vector_store.search_vectors(
            query_vector=query_vector,
            course_id=course_id,
            limit=top_k,
            score_threshold=score_threshold
        )

        logger.info(f"Retrieved {len(results)} relevant chunks for course {course_id}")
        return results
