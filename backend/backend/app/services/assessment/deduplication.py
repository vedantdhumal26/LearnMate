import re
import hashlib
from typing import Optional, List, Set
from sqlalchemy.orm import Session
from app.models.assessment import Question, QuestionAttempt

def normalize_text(text: str) -> str:
    """Normalize text for consistent hashing and similarity comparison."""
    if not text:
        return ""
    # Lowercase and remove punctuation except alphanumeric and space
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    # Collapse multiple whitespaces
    return " ".join(cleaned.split()).strip()

def compute_content_hash(text: str) -> str:
    """Compute deterministic SHA-256 hash of normalized text."""
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def calculate_jaccard_similarity(text1: str, text2: str) -> float:
    """
    Calculate token-based similarity between two texts.
    Uses Jaccard similarity, and allows overlap ratio only when lengths are comparable
    (min_len / max_len >= 0.70) to prevent short subset phrases from falsely matching longer questions.
    """
    words1 = set(normalize_text(text1).split())
    words2 = set(normalize_text(text2).split())
    if not words1 or not words2:
        return 0.0
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    jaccard = len(intersection) / len(union)
    min_len = min(len(words1), len(words2))
    max_len = max(len(words1), len(words2))
    if max_len > 0 and (min_len / max_len) >= 0.70:
        overlap = len(intersection) / min_len
        return max(jaccard, overlap)
    return jaccard

class QuestionDeduplicator:
    def __init__(self, similarity_threshold: float = 0.80):
        self.similarity_threshold = similarity_threshold

    def is_duplicate(
        self,
        db: Session,
        course_id: str,
        question_text: str,
        student_id: Optional[str] = None
    ) -> bool:
        """
        Check whether the question is an exact or near duplicate for the course,
        and whether the student has already encountered or attempted it.
        """
        q_hash = compute_content_hash(question_text)

        # 1. Exact hash check for the course
        exact_match = db.query(Question).filter(
            Question.course_id == course_id,
            Question.content_hash == q_hash
        ).first()
        if exact_match:
            return True

        # 2. Check student's previous attempts if student_id is provided
        if student_id:
            attempted_question_ids = (
                db.query(QuestionAttempt.question_id)
                .filter(QuestionAttempt.student_id == student_id)
                .all()
            )
            attempted_ids = {qid[0] for qid in attempted_question_ids}
            if attempted_ids:
                attempted_questions = (
                    db.query(Question)
                    .filter(Question.id.in_(attempted_ids))
                    .all()
                )
                for aq in attempted_questions:
                    if aq.content_hash == q_hash or calculate_jaccard_similarity(question_text, aq.question_text) >= self.similarity_threshold:
                        return True

        # 3. Near-duplicate text similarity check across recent course questions
        recent_questions = (
            db.query(Question)
            .filter(Question.course_id == course_id)
            .order_by(Question.created_at.desc())
            .limit(100)
            .all()
        )
        for rq in recent_questions:
            sim = calculate_jaccard_similarity(question_text, rq.question_text)
            if sim >= self.similarity_threshold:
                return True

        return False
