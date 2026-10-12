import re
import json
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.assessment import Question, QuestionAttempt, AssessmentAttempt, Assessment
from app.schemas.assessment import (
    StudentAnswerItem,
    QuestionResultItem,
    TopicPerformanceItem,
    AssessmentSubmitResponse,
    CitationItem,
)
from app.services.llm.llm_service import get_llm_service, LLMService
from app.core.logging_config import logger

class AssessmentGrader:
    def __init__(self, llm_service: Optional[LLMService] = None):
        self._llm_service = llm_service

    @property
    def llm_service(self) -> LLMService:
        if self._llm_service is None:
            self._llm_service = get_llm_service()
        return self._llm_service

    def grade_assessment(
        self,
        db: Session,
        assessment: Assessment,
        student_id: str,
        student_answers: List[StudentAnswerItem]
    ) -> AssessmentSubmitResponse:
        """
        Grades submitted student answers, persists QuestionAttempt and AssessmentAttempt records,
        and generates grounded feedback with exact source citations.
        """
        # Load questions for this assessment
        question_ids = assessment.questions or []
        questions = db.query(Question).filter(Question.id.in_(question_ids)).all()
        q_map: Dict[str, Question] = {q.id: q for q in questions}

        # Map student answers by question_id
        ans_map: Dict[str, str] = {sa.question_id: sa.answer for sa in student_answers}

        question_results: List[QuestionResultItem] = []
        topic_counts: Dict[str, Dict[str, int]] = {}  # topic -> {"correct": int, "total": int}
        performance_items: List[Dict[str, Any]] = []

        total_correct = 0

        for q_id in question_ids:
            q = q_map.get(q_id)
            if not q:
                continue

            submitted_ans = ans_map.get(q_id, "").strip()
            topic_name = q.topic_id or "General"
            if topic_name not in topic_counts:
                topic_counts[topic_name] = {"correct": 0, "total": 0}
            topic_counts[topic_name]["total"] += 1

            # Grade individual question
            is_correct, feedback = self._grade_single_question(q, submitted_ans)

            if is_correct:
                total_correct += 1
                topic_counts[topic_name]["correct"] += 1

            # Track for learner mastery model update (Phase 3)
            performance_items.append({
                "topic": topic_name,
                "is_correct": is_correct,
                "difficulty": q.difficulty or "medium"
            })

            # Record QuestionAttempt
            attempt = QuestionAttempt(
                assessment_id=assessment.id,
                question_id=q.id,
                student_id=student_id,
                submitted_answer=submitted_ans,
                is_correct=is_correct,
            )
            db.add(attempt)

            # Format source citations
            citations: List[CitationItem] = []
            if q.source_ids and isinstance(q.source_ids, list):
                for s in q.source_ids:
                    if isinstance(s, dict):
                        try:
                            citations.append(CitationItem(**s))
                        except Exception:
                            pass

            question_results.append(
                QuestionResultItem(
                    question_id=q.id,
                    correct=is_correct,
                    feedback=feedback,
                    sources=citations
                )
            )

        total_questions = len(question_ids)
        score = round((total_correct / total_questions * 100.0), 1) if total_questions > 0 else 0.0

        # Record AssessmentAttempt
        assessment_attempt = AssessmentAttempt(
            assessment_id=assessment.id,
            student_id=student_id,
            score=score,
            total_questions=total_questions,
            correct_answers=total_correct
        )
        db.add(assessment_attempt)
        db.commit()

        # Update Learner Mastery Model (Phase 3)
        try:
            from app.services.learner_model.learner_service import LearnerModelService
            learner_service = LearnerModelService()
            learner_service.record_assessment_performance(
                db=db,
                student_id=student_id,
                course_id=assessment.course_id,
                performance_items=performance_items
            )
        except Exception as e:
            logger.error(f"Error updating learner mastery for student '{student_id}': {e}", exc_info=True)

        # Build topic performance breakdown
        topic_performance: List[TopicPerformanceItem] = []
        for topic, counts in topic_counts.items():
            t_total = counts["total"]
            t_correct = counts["correct"]
            t_score = round((t_correct / t_total * 100.0), 1) if t_total > 0 else 0.0
            topic_performance.append(
                TopicPerformanceItem(
                    topic=topic,
                    score=t_score,
                    correct=t_correct,
                    total=t_total
                )
            )

        return AssessmentSubmitResponse(
            assessment_id=assessment.id,
            score=score,
            correct=total_correct,
            total=total_questions,
            question_results=question_results,
            topic_performance=topic_performance
        )

    def _grade_single_question(self, question: Question, submitted_ans: str) -> Tuple[bool, str]:
        q_type = question.question_type.lower().strip()

        if q_type == "mcq":
            return self._grade_mcq(question, submitted_ans)
        elif q_type == "numerical":
            return self._grade_numerical(question, submitted_ans)
        else:  # short_answer
            return self._grade_short_answer(question, submitted_ans)

    def _grade_mcq(self, question: Question, submitted_ans: str) -> Tuple[bool, str]:
        if not submitted_ans:
            return False, f"No answer submitted. The correct answer is {question.correct_answer}. {question.explanation}"

        correct_ans = question.correct_answer.strip()
        options = question.options or []

        # Extract answer identifier letter (e.g. 'A', 'B', 'C', 'D')
        def extract_letter_or_norm(text: str) -> str:
            t = text.strip()
            if not t:
                return ""
            m = re.match(r"^([A-Da-d])(?:[\)\.\:\s]|$)", t)
            if m:
                return m.group(1).upper()
            return t.lower()

        sub_key = extract_letter_or_norm(submitted_ans)
        corr_key = extract_letter_or_norm(correct_ans)

        is_match = False
        if len(sub_key) == 1 and sub_key in ["A", "B", "C", "D"]:
            if len(corr_key) == 1 and corr_key in ["A", "B", "C", "D"]:
                is_match = (sub_key == corr_key)
            else:
                # Compare by option index (A=0, B=1, C=2, D=3)
                idx = ord(sub_key) - ord("A")
                if 0 <= idx < len(options):
                    is_match = (corr_key in options[idx].lower())
        else:
            # Full text match or substring
            is_match = (sub_key == corr_key or corr_key in sub_key or sub_key in corr_key)

        if is_match:
            feedback = f"Correct! {question.explanation}"
            return True, feedback
        else:
            feedback = (
                f"Incorrect. You selected '{submitted_ans}'. The correct answer is {question.correct_answer}. "
                f"{question.explanation}"
            )
            return False, feedback

    def _grade_numerical(self, question: Question, submitted_ans: str) -> Tuple[bool, str]:
        if not submitted_ans:
            return False, f"No answer submitted. The correct answer is {question.correct_answer}. {question.explanation}"

        sub_nums = re.findall(r"[-+]?\d*\.?\d+", submitted_ans)
        corr_nums = re.findall(r"[-+]?\d*\.?\d+", question.correct_answer)

        if not sub_nums:
            return False, f"Could not parse a numeric value from '{submitted_ans}'. The correct answer is {question.correct_answer}. {question.explanation}"

        if not corr_nums:
            return False, f"Configuration error: correct answer '{question.correct_answer}' has no number."

        try:
            sub_val = float(sub_nums[0])
            corr_val = float(corr_nums[0])
            # Tolerance of 2% or 0.05
            tol = max(0.02 * abs(corr_val), 0.05)
            is_correct = abs(sub_val - corr_val) <= tol

            if is_correct:
                return True, f"Correct! {question.explanation}"
            else:
                return False, f"Incorrect. Your calculated value was {sub_val}. The correct value is {question.correct_answer}. {question.explanation}"
        except ValueError:
            return False, f"Invalid numeric input. The correct answer is {question.correct_answer}. {question.explanation}"

    def _grade_short_answer(self, question: Question, submitted_ans: str) -> Tuple[bool, str]:
        if not submitted_ans or len(submitted_ans.strip()) < 2:
            return False, f"No substantial answer submitted. The expected answer is: {question.correct_answer}. {question.explanation}"

        prompt = (
            f"You are a strict, fair academic examiner for LearnSphere AI.\n\n"
            f"EVALUATION TASK:\n"
            f"Question: {question.question_text}\n"
            f"Expected Answer: {question.correct_answer}\n"
            f"Reference Explanation: {question.explanation}\n"
            f"Student Submitted Answer: {submitted_ans}\n\n"
            "INSTRUCTIONS:\n"
            "1. Evaluate whether the student's answer captures the essential meaning and accuracy of the expected answer.\n"
            "2. Do NOT mark correct merely because it contains one keyword if the conceptual meaning is absent or wrong.\n"
            "3. If conceptually sound and accurate, mark is_correct: true.\n"
            "4. Provide constructive feedback referencing the course concept.\n\n"
            "OUTPUT FORMAT (STRICT JSON ONLY):\n"
            "{\n"
            "  \"is_correct\": true,\n"
            "  \"feedback\": \"...\"\n"
            "}"
        )

        system_prompt = "You are an objective academic evaluator. Output strict JSON with boolean 'is_correct' and string 'feedback'."

        try:
            try:
                response = self.llm_service.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    request_type="assessment",
                    max_tokens=200
                )
            except TypeError as te:
                if "unexpected keyword argument" in str(te):
                    response = self.llm_service.generate(prompt=prompt, system_prompt=system_prompt)
                else:
                    raise
            # Parse JSON
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                cleaned = re.sub(r"\s*```$", "", cleaned)
                cleaned = cleaned.strip()

            s_idx = cleaned.find("{")
            e_idx = cleaned.rfind("}")
            if s_idx != -1 and e_idx != -1:
                data = json.loads(cleaned[s_idx : e_idx + 1])
                is_correct = bool(data.get("is_correct", False))
                feedback = str(data.get("feedback", question.explanation))
                return is_correct, feedback
        except Exception as e:
            logger.warning(f"Error evaluating short answer via LLM: {e}")

        # Fallback keyword/phrase containment check
        corr_norm = question.correct_answer.lower()
        sub_norm = submitted_ans.lower()
        # Non-trivial similarity
        words_corr = set(corr_norm.split())
        words_sub = set(sub_norm.split())
        overlap = len(words_corr.intersection(words_sub)) / max(len(words_corr), 1)

        if overlap >= 0.6:
            return True, f"Correct! {question.explanation}"
        else:
            return False, f"Incorrect. The expected answer is: {question.correct_answer}. {question.explanation}"
