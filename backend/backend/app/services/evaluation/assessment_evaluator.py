import json
import re
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from app.models.course import Course
from app.models.assessment import Question
from app.models.document_chunk import DocumentChunk
from app.services.assessment.question_generator import AssessmentQuestionGenerator
from app.services.assessment.question_verifier import QuestionVerifier
from app.services.assessment.deduplication import (
    QuestionDeduplicator,
    compute_content_hash,
    calculate_jaccard_similarity,
)
from app.services.vector_store.base import VectorSearchResult
from app.core.logging_config import logger

class AssessmentEvaluator:
    """
    Evaluates assessment generation quality and deduplication:
    - Verifies question validity, answer keys, arithmetic consistency, and grounding.
    - Measures repetition and duplicate rates across multiple generations.
    """

    def __init__(
        self,
        generator: Optional[AssessmentQuestionGenerator] = None,
        verifier: Optional[QuestionVerifier] = None,
        deduplicator: Optional[QuestionDeduplicator] = None,
    ):
        self.generator = generator or AssessmentQuestionGenerator()
        self.verifier = verifier or QuestionVerifier()
        self.deduplicator = deduplicator or QuestionDeduplicator()

    def evaluate_questions_quality(
        self,
        questions: List[Question],
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Evaluate a list of existing questions against the verification rules.
        If no questions are provided, represents validity_rate as None (unmeasured).
        """
        if not questions:
            return {
                "total_evaluated": 0,
                "valid_count": 0,
                "invalid_count": 0,
                "validity_rate": None,
                "failures": []
            }

        valid_count = 0
        failures = []
        course_chunks_cache: Dict[str, List[VectorSearchResult]] = {}

        for q in questions:
            opts = q.options
            if isinstance(opts, str):
                try:
                    opts = json.loads(opts)
                except Exception:
                    pass

            q_data = {
                "question": q.question_text,
                "options": opts,
                "correct_answer": q.correct_answer,
                "explanation": q.explanation,
                "sources": q.source_ids or []
            }

            # Retrieve chunks for this course from DB if available for grounding check
            chunks: List[VectorSearchResult] = []
            if db and q.course_id:
                if q.course_id not in course_chunks_cache:
                    try:
                        db_chunks = db.query(DocumentChunk).filter(DocumentChunk.course_id == q.course_id).all()
                        course_chunks_cache[q.course_id] = [
                            VectorSearchResult(
                                chunk_id=c.id,
                                course_id=c.course_id,
                                source_id=c.source_id,
                                content=c.content,
                                page_number=c.page_number,
                                file_name="",
                                score=1.0
                            )
                            for c in db_chunks
                        ]
                    except Exception as err:
                        logger.warning(f"Error loading course chunks from DB for quality eval: {err}")
                        course_chunks_cache[q.course_id] = []
                chunks = course_chunks_cache[q.course_id]

            is_valid, reason = self.verifier.verify_question(
                question_data=q_data,
                question_type=q.question_type,
                topic=q.topic_id or "",
                retrieved_chunks=chunks if chunks else None
            )

            # Check MCQ: exactly one option matches correct answer
            if is_valid and q.question_type == "mcq" and opts and isinstance(opts, list):
                correct_str = str(q.correct_answer).strip()
                cleaned_opts = [str(opt).strip() for opt in opts]
                letters = ["A", "B", "C", "D"]
                first_char = correct_str[0].upper() if correct_str else ""
                is_letter = first_char in letters and (len(correct_str) == 1 or correct_str[1] in [")", ".", ":", " "])

                if not is_letter:
                    def _matches_mcq_option(opt_text: str, ans: str) -> bool:
                        clean_o = re.sub(r"^[A-Da-d][\)\.\:\s-]\s*", "", opt_text).strip().lower()
                        clean_a = re.sub(r"^[A-Da-d][\)\.\:\s-]\s*", "", ans).strip().lower()
                        return clean_a == clean_o or clean_a == opt_text.strip().lower() or clean_a in opt_text.strip().lower()

                    matches = sum(1 for opt in cleaned_opts if _matches_mcq_option(opt, correct_str))
                    if matches != 1:
                        is_valid = False
                        reason = f"MCQ does not have exactly one matching correct option (matches: {matches})"

            if is_valid:
                valid_count += 1
            else:
                failures.append({
                    "question_id": q.id,
                    "question_text": q.question_text[:50],
                    "reason": reason
                })

        validity_rate = round(valid_count / len(questions), 3) if len(questions) > 0 else None
        return {
            "total_evaluated": len(questions),
            "valid_count": valid_count,
            "invalid_count": len(failures),
            "validity_rate": validity_rate,
            "failures": failures
        }

    def evaluate_duplicate_rate_from_questions(
        self,
        questions: List[Question]
    ) -> Dict[str, Any]:
        """
        Calculate duplicate rate across a provided list of questions without generating new ones.
        """
        if not questions or len(questions) < 2:
            return {
                "total_questions": len(questions) if questions else 0,
                "unique_questions": len(questions) if questions else 0,
                "duplicate_questions": 0,
                "duplicate_rate": None,
                "note": "At least 2 questions are required to measure duplicate rate"
            }

        all_hashes = []
        seen_hashes = set()
        seen_texts = []
        duplicates_detected = 0

        for q in questions:
            q_text = q.question_text if hasattr(q, "question_text") else str(q.get("question", ""))
            h = (getattr(q, "content_hash", None)) or compute_content_hash(q_text)

            is_dup = False
            if h in seen_hashes:
                is_dup = True
            else:
                for prev_text in seen_texts:
                    if calculate_jaccard_similarity(q_text, prev_text) >= 0.80:
                        is_dup = True
                        break

            if is_dup:
                duplicates_detected += 1
            else:
                seen_hashes.add(h)
                seen_texts.append(q_text)
            all_hashes.append(h)

        total = len(all_hashes)
        unique = len(seen_hashes)
        duplicate_rate = round(duplicates_detected / total, 3)

        return {
            "total_questions": total,
            "unique_questions": unique,
            "duplicate_questions": duplicates_detected,
            "duplicate_rate": duplicate_rate
        }

    def evaluate_duplicate_rate(
        self,
        db: Session,
        course_id: str,
        topic: str,
        rounds: int = 3,
        count_per_round: int = 3,
        question_type: str = "mcq"
    ) -> Dict[str, Any]:
        """
        Generate multiple batches of questions for the same course and topic,
        and calculate total_questions, unique_questions, duplicate_questions, and duplicate_rate.
        """
        # Validate course has content
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course or not course.sources:
            return {
                "total_questions": 0,
                "unique_questions": 0,
                "duplicate_questions": 0,
                "duplicate_rate": None,
                "note": "Course has no sources to generate questions from"
            }

        all_hashes = []
        seen_hashes = set()
        seen_texts = []
        duplicates_detected = 0

        for r in range(rounds):
            try:
                questions = self.generator.generate_questions(
                    db=db,
                    course_id=course_id,
                    topic=topic,
                    question_type=question_type,
                    count=count_per_round,
                    student_id=f"eval-student-{r}"
                )
                for q in questions:
                    q_text = q.question_text if hasattr(q, "question_text") else str(q.get("question", ""))
                    h = (getattr(q, "content_hash", None)) or compute_content_hash(q_text)
                    is_dup = False
                    if h in seen_hashes:
                        is_dup = True
                    else:
                        for prev_text in seen_texts:
                            if calculate_jaccard_similarity(q_text, prev_text) >= 0.80:
                                is_dup = True
                                break
                    if is_dup:
                        duplicates_detected += 1
                    else:
                        seen_hashes.add(h)
                        seen_texts.append(q_text)
                    all_hashes.append(h)
            except Exception as e:
                logger.warning(f"Error during duplicate rate assessment round {r}: {e}")
                break

        total = len(all_hashes)
        if total == 0:
            return {
                "total_questions": 0,
                "unique_questions": 0,
                "duplicate_questions": 0,
                "duplicate_rate": None,
            }

        if total < 2:
            return {
                "total_questions": total,
                "unique_questions": len(seen_hashes),
                "duplicate_questions": duplicates_detected,
                "duplicate_rate": None,
                "note": "At least 2 questions are required to measure duplicate rate"
            }

        unique = len(seen_hashes)
        duplicate_rate = round(duplicates_detected / total, 3)

        return {
            "total_questions": total,
            "unique_questions": unique,
            "duplicate_questions": duplicates_detected,
            "duplicate_rate": duplicate_rate
        }
