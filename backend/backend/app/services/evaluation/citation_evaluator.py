from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from app.models.source import Source
from app.models.document_chunk import DocumentChunk
from app.schemas.tutor import CitationItem
from app.schemas.evaluation import ExpectedSource
from app.core.logging_config import logger

class CitationEvaluator:
    """
    Evaluates whether citations retrieved in tutor answers are strictly correct:
    1. Verifies source exists in the database.
    2. Verifies source belongs to the target course.
    3. Verifies modality matches (PDF, PPTX, video/MP4, YouTube).
    4. Verifies location metadata (PDF page, PPTX slide, MP4 timestamp, YouTube timestamp).
    5. Verifies excerpt content actually belongs to the retrieved source (anti-hallucination).
    """

class CitationEvaluator:
    """
    Evaluates whether citations retrieved in tutor answers are strictly correct:
    1. Verifies source exists in the database.
    2. Verifies source belongs to the target course.
    3. Verifies modality matches (PDF, PPTX, video/MP4, YouTube).
    4. Verifies excerpt content actually belongs to the retrieved source (anti-hallucination).
    5. Verifies expected locations (PDF page, PPTX slide, MP4 timestamp, YouTube timestamp)
       are accurately cited where expected.
    """

    @classmethod
    def evaluate_citation_authenticity(
        cls,
        citation: CitationItem,
        course_id: str,
        db: Session
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify that a single citation is authentic: exists in DB, belongs to course,
        modality matches, and excerpt text is not fabricated.
        """
        # 1. Verify source exists in DB and belongs to course
        source = db.query(Source).filter(
            Source.id == citation.source_id,
            Source.course_id == course_id
        ).first()

        if not source:
            return False, f"Source ID '{citation.source_id}' not found for course '{course_id}'."

        # 2. Verify modality matches
        cit_mod = (citation.modality or "").lower()
        src_mod = (source.source_type or "").lower()
        if cit_mod and src_mod:
            norm_cit = "video" if cit_mod in ("video", "video_transcript", "mp4") else "pptx" if "pptx" in cit_mod else cit_mod
            norm_src = "video" if src_mod in ("video", "video_transcript", "mp4") else "pptx" if "pptx" in src_mod else src_mod
            if norm_cit != norm_src:
                return False, f"Modality mismatch: citation claims '{cit_mod}' but source record is '{src_mod}'."

        # 3. Verify excerpt authenticity against document_chunks in DB
        if citation.excerpt:
            cleaned_excerpt = citation.excerpt.strip()
            if cleaned_excerpt.startswith("[YouTube") and "\n" in cleaned_excerpt:
                cleaned_excerpt = cleaned_excerpt.split("\n", 1)[1].strip()
            elif cleaned_excerpt.startswith("[Slide") and "] " in cleaned_excerpt:
                cleaned_excerpt = cleaned_excerpt.split("] ", 1)[1].strip()
            elif cleaned_excerpt.startswith("[Video") and "] " in cleaned_excerpt:
                cleaned_excerpt = cleaned_excerpt.split("] ", 1)[1].strip()

            import re
            excerpt_tokens = set(re.findall(r"\b[a-zA-Z0-9]{4,}\b", cleaned_excerpt.lower()))
            if excerpt_tokens:
                chunks = db.query(DocumentChunk).filter(DocumentChunk.source_id == citation.source_id).all()
                if not chunks:
                    return False, f"Source '{citation.source_id}' has no stored chunks in database."

                matched_in_any = False
                for ch in chunks:
                    ch_lower = ch.content.lower()
                    overlap = sum(1 for tok in excerpt_tokens if tok in ch_lower)
                    if overlap >= min(2, len(excerpt_tokens)):
                        matched_in_any = True
                        break

                if not matched_in_any:
                    return False, f"Citation excerpt appears fabricated; text not found in stored chunks for source '{citation.source_id}'."

        return True, None

    @classmethod
    def matches_expected_source(
        cls,
        citation: CitationItem,
        expected: ExpectedSource
    ) -> bool:
        """Check if a citation satisfies an expected source specification."""
        # Check source_id if specified (allow file_name fallback)
        if expected.source_id and expected.source_id != citation.source_id:
            if not (expected.file_name and citation.file_name and expected.file_name == citation.file_name):
                return False

        # Check PDF page
        if expected.page is not None and citation.page != expected.page:
            return False

        # Check PPTX slide
        if expected.slide is not None and citation.slide != expected.slide:
            return False

        # Check MP4 / YouTube timestamps
        if expected.start_seconds is not None or expected.end_seconds is not None:
            if citation.start_seconds is None or citation.end_seconds is None:
                return False
            exp_s = expected.start_seconds or 0.0
            exp_e = expected.end_seconds or (exp_s + 60.0)
            cit_s = citation.start_seconds
            cit_e = citation.end_seconds

            overlap = max(0.0, min(exp_e, cit_e) - max(exp_s, cit_s))
            if overlap <= 0 and abs(cit_s - exp_s) > 30.0:
                return False

        return True

    @classmethod
    def evaluate_citation(
        cls,
        citation: CitationItem,
        expected_sources: List[ExpectedSource],
        course_id: str,
        db: Session
    ) -> Tuple[bool, Optional[str]]:
        """Verify a single citation item against database authenticity and expectations."""
        is_auth, reason = cls.evaluate_citation_authenticity(citation, course_id, db)
        if not is_auth:
            return False, reason
        if expected_sources:
            if not any(cls.matches_expected_source(citation, exp) for exp in expected_sources):
                return False, "Citation location does not match expected source location."
        return True, None

    @classmethod
    def evaluate_all(
        cls,
        citations: List[CitationItem],
        expected_sources: List[ExpectedSource],
        course_id: str,
        db: Session
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluates citations returned by the tutor:
        1. Checks each citation's authenticity (DB existence, modality, anti-hallucination).
        2. Ensures all expected sources are represented in the returned citations.
        """
        if expected_sources and not citations:
            return False, "Expected citations but none were returned by the tutor."

        if not citations and not expected_sources:
            return True, None

        # 1. Verify authenticity of every citation
        for c in citations:
            is_valid, reason = cls.evaluate_citation_authenticity(c, course_id, db)
            if not is_valid:
                return False, reason

        # 2. Verify all expected sources are satisfied
        for exp in expected_sources:
            satisfied = any(cls.matches_expected_source(c, exp) for c in citations)
            if not satisfied:
                loc_desc = []
                if exp.page is not None:
                    loc_desc.append(f"page={exp.page}")
                if exp.slide is not None:
                    loc_desc.append(f"slide={exp.slide}")
                if exp.start_seconds is not None:
                    loc_desc.append(f"ts={exp.start_seconds}-{exp.end_seconds}")
                loc_str = ", ".join(loc_desc) or f"source_id={exp.source_id}"
                return False, f"Expected citation at location ({loc_str}) was not found in retrieved citations."

        return True, None
