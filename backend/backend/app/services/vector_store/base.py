from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class VectorSearchResult:
    chunk_id: str
    course_id: str
    source_id: str
    file_name: str
    page_number: Optional[int]
    content: str
    score: float
    slide_number: Optional[int] = None
    start_time_seconds: Optional[float] = None
    end_time_seconds: Optional[float] = None
    modality: Optional[str] = "pdf"
    video_id: Optional[str] = None
    canonical_url: Optional[str] = None

class VectorStore(ABC):
    @abstractmethod
    def ensure_collection(self, vector_size: int) -> None:
        """Ensure that the vector collection exists with the specified dimension."""
        pass

    @abstractmethod
    def upsert_vectors(
        self,
        vectors: List[List[float]],
        payloads: List[Dict[str, Any]],
        ids: List[str]
    ) -> None:
        """
        Store vectors along with their metadata payloads.
        Payloads must contain: course_id, source_id, file_name, page_number, chunk_id, content.
        """
        pass

    @abstractmethod
    def search_vectors(
        self,
        query_vector: List[float],
        course_id: str,
        limit: int = 5,
        score_threshold: float = 0.0
    ) -> List[VectorSearchResult]:
        """
        Search for vectors matching course_id strictly, ranked by cosine similarity.
        """
        pass

    @abstractmethod
    def delete_source_vectors(self, source_id: str) -> None:
        """Delete all vectors associated with a given source_id."""
        pass

    @abstractmethod
    def delete_course_vectors(self, course_id: str) -> None:
        """Delete all vectors associated with a given course_id."""
        pass
