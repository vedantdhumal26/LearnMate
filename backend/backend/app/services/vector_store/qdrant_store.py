from typing import List, Dict, Any, Optional
import os
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

from app.services.vector_store.base import VectorStore, VectorSearchResult
from app.core.config import settings
from app.core.logging_config import logger

class QdrantVectorStore(VectorStore):
    def __init__(
        self,
        collection_name: Optional[str] = None,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        storage_path: Optional[str] = None,
    ):
        self.collection_name = collection_name or settings.QDRANT_COLLECTION
        self.url = url or settings.QDRANT_URL
        self.api_key = api_key or settings.QDRANT_API_KEY
        self.storage_path = storage_path or settings.QDRANT_STORAGE_PATH

        self.client = self._init_client()

    def _init_client(self) -> QdrantClient:
        """
        Attempt connection to remote Qdrant URL.
        If unavailable, gracefully fallback to local embedded Qdrant storage.
        """
        if self.url:
            try:
                logger.info(f"Attempting connection to Qdrant at {self.url}...")
                client = QdrantClient(url=self.url, api_key=self.api_key, timeout=10.0)
                # Verify connectivity
                client.get_collections()
                logger.info("Successfully connected to remote Qdrant instance.")
                return client
            except Exception as e:
                logger.warning(
                    f"Could not connect to Qdrant at {self.url}: {e}. "
                    f"Falling back to embedded local storage at '{self.storage_path}'."
                )

        # Embedded fallback mode
        if self.storage_path:
            os.makedirs(self.storage_path, exist_ok=True)
            logger.info(f"Using local embedded Qdrant at path: {self.storage_path}")
            return QdrantClient(path=self.storage_path)
        
        logger.info("Using in-memory Qdrant instance.")
        return QdrantClient(location=":memory:")

    def ensure_collection(self, vector_size: int) -> None:
        """Create Qdrant collection if it does not already exist."""
        try:
            if not self.client.collection_exists(self.collection_name):
                logger.info(
                    f"Creating Qdrant collection '{self.collection_name}' "
                    f"with vector size {vector_size} (Cosine distance)"
                )
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=vector_size,
                        distance=models.Distance.COSINE
                    )
                )

                # Attempt payload index creation (supported on remote server)
                try:
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name="course_id",
                        field_schema=models.PayloadSchemaType.KEYWORD
                    )
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name="source_id",
                        field_schema=models.PayloadSchemaType.KEYWORD
                    )
                except Exception as idx_err:
                    logger.debug(f"Payload index creation note: {idx_err}")
            else:
                logger.debug(f"Qdrant collection '{self.collection_name}' already exists.")
        except Exception as e:
            logger.error(f"Error ensuring Qdrant collection '{self.collection_name}': {e}")
            raise

    def upsert_vectors(
        self,
        vectors: List[List[float]],
        payloads: List[Dict[str, Any]],
        ids: List[str]
    ) -> None:
        """Upsert points into Qdrant in batches."""
        if not vectors:
            return

        points = [
            models.PointStruct(
                id=pid,
                vector=vec,
                payload=payload
            )
            for pid, vec, payload in zip(ids, vectors, payloads)
        ]

        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
                wait=True
            )
        logger.info(f"Upserted {len(points)} vector points to collection '{self.collection_name}'.")

    def search_vectors(
        self,
        query_vector: List[float],
        course_id: str,
        limit: int = 5,
        score_threshold: float = 0.0
    ) -> List[VectorSearchResult]:
        """
        Search for top-K vectors filtered strictly by course_id.
        Preserves all source and page metadata.
        """
        if not self.client.collection_exists(self.collection_name):
            logger.warning(f"Collection '{self.collection_name}' does not exist yet. Returning empty results.")
            return []

        course_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="course_id",
                    match=models.MatchValue(value=course_id)
                )
            ]
        )

        try:
            # query_points is the standard API in qdrant-client >= 1.10
            query_response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=course_filter,
                limit=limit,
                score_threshold=score_threshold if score_threshold > 0 else None,
                with_payload=True
            )
            points = query_response.points
        except Exception as e:
            logger.error(f"Qdrant search error for course {course_id}: {e}")
            return []

        results: List[VectorSearchResult] = []
        for point in points:
            payload = point.payload or {}
            raw_page = payload.get("page_number")
            raw_slide = payload.get("slide_number")
            results.append(
                VectorSearchResult(
                    chunk_id=str(payload.get("chunk_id", point.id)),
                    course_id=str(payload.get("course_id", course_id)),
                    source_id=str(payload.get("source_id", "")),
                    file_name=str(payload.get("file_name", "")),
                    page_number=int(raw_page) if raw_page is not None else None,
                    content=str(payload.get("content", "")),
                    score=float(point.score),
                    slide_number=int(raw_slide) if raw_slide is not None else None,
                    start_time_seconds=float(raw_start) if (raw_start := payload.get("start_time_seconds")) is not None else None,
                    end_time_seconds=float(raw_end) if (raw_end := payload.get("end_time_seconds")) is not None else None,
                    modality=str(payload.get("modality", "pdf")),
                    video_id=payload.get("video_id"),
                    canonical_url=payload.get("canonical_url")
                )
            )

        logger.info(
            f"Retrieved {len(results)} vector matches for course {course_id} "
            f"(threshold: {score_threshold})"
        )
        return results

    def delete_source_vectors(self, source_id: str) -> None:
        """Delete all vectors for a specific source_id."""
        try:
            if not self.client.collection_exists(self.collection_name):
                return

            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="source_id",
                                match=models.MatchValue(value=source_id)
                            )
                        ]
                    )
                ),
                wait=True
            )
            logger.info(f"Deleted vectors for source_id: {source_id}")
        except Exception as e:
            logger.error(f"Error deleting vectors for source_id {source_id}: {e}")

    def delete_course_vectors(self, course_id: str) -> None:
        """Delete all vectors for a specific course_id."""
        try:
            if not self.client.collection_exists(self.collection_name):
                return

            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="course_id",
                                match=models.MatchValue(value=course_id)
                            )
                        ]
                    )
                ),
                wait=True
            )
            logger.info(f"Deleted vectors for course_id: {course_id}")
        except Exception as e:
            logger.error(f"Error deleting vectors for course_id {course_id}: {e}")

_vector_store_instance: Optional[VectorStore] = None

def get_vector_store() -> VectorStore:
    """Singleton getter for VectorStore."""
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = QdrantVectorStore()
    return _vector_store_instance
