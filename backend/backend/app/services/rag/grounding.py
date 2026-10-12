from typing import List, Tuple
import re
from app.services.vector_store.base import VectorSearchResult
from app.schemas.tutor import CitationItem
from app.core.config import settings
from app.core.logging_config import logger

REFUSAL_MESSAGE = "I couldn't find enough information about this topic in the uploaded course material."

# Phrases that indicate the LLM concluded the context is inadequate or off-topic
UNSUPPORTED_PHRASES = [
    "couldn't find enough information",
    "could not find enough information",
    "not enough information",
    "not mentioned in the provided",
    "does not contain information",
    "cannot be answered using the provided",
    "not covered in the course material",
    "not found in the course material",
    "insufficient information",
]

class GroundingValidator:
    def __init__(self, score_threshold: float = None):
        self.score_threshold = (
            score_threshold if score_threshold is not None else settings.RAG_SCORE_THRESHOLD
        )

    def validate_pre_retrieval(
        self, chunks: List[VectorSearchResult]
    ) -> Tuple[bool, str]:
        """
        Validate whether retrieved chunks are sufficient to attempt generating an answer.
        Returns: (is_grounded, refusal_reason)
        """
        if not chunks:
            logger.info("Grounding failed: No chunks retrieved for query.")
            return False, "no_chunks_found"

        max_score = max(c.score for c in chunks)
        if max_score < self.score_threshold:
            logger.info(
                f"Grounding failed: Top chunk score {max_score:.3f} below threshold {self.score_threshold}"
            )
            return False, "score_below_threshold"

        return True, ""

    def validate_post_generation(
        self,
        llm_response: str,
        citations: List[CitationItem]
    ) -> Tuple[bool, str, List[CitationItem]]:
        """
        Validate LLM response text for grounding integrity.
        If the LLM indicated off-material or insufficient info, mark grounded=False and wipe citations.
        Returns: (is_grounded, final_answer, final_citations)
        """
        lower_response = llm_response.lower()

        for phrase in UNSUPPORTED_PHRASES:
            if phrase in lower_response:
                logger.info(f"Grounding check detected refusal phrase: '{phrase}'")
                return False, REFUSAL_MESSAGE, []

        return True, llm_response, citations
