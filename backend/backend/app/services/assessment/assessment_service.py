from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.course import Course
from app.models.assessment import Assessment, Question
from app.schemas.assessment import (
    AssessmentGenerateRequest,
    AssessmentGenerateResponse,
    AssessmentDetailResponse,
    AssessmentSubmitRequest,
    AssessmentSubmitResponse,
    StudentQuestionItem,
    CitationItem,
)
from app.services.assessment.question_generator import AssessmentQuestionGenerator
from app.services.assessment.grader import AssessmentGrader
from app.core.logging_config import logger

class AssessmentService:
    def __init__(
        self,
        question_generator: Optional[AssessmentQuestionGenerator] = None,
        grader: Optional[AssessmentGrader] = None
    ):
        self.question_generator = question_generator or AssessmentQuestionGenerator()
        self.grader = grader or AssessmentGrader()

    def generate_assessment(
        self,
        db: Session,
        request: AssessmentGenerateRequest
    ) -> AssessmentGenerateResponse:
        """
        Generate a new adaptive assessment with course-grounded questions.
        """
        # 1. Validate course exists
        course = db.query(Course).filter(Course.id == request.course_id).first()
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Course with ID '{request.course_id}' not found."
            )

        # 2. Generate grounded questions
        questions = self.question_generator.generate_questions(
            db=db,
            course_id=request.course_id,
            topic=request.topic,
            difficulty=request.difficulty,
            question_type=request.question_type,
            count=request.count,
            student_id=request.student_id
        )

        # 3. Create Assessment record
        title = f"{request.topic} - {request.difficulty.capitalize()} Assessment"
        assessment = Assessment(
            course_id=request.course_id,
            title=title,
            student_id=request.student_id,
            questions=[q.id for q in questions]
        )
        db.add(assessment)
        db.commit()
        db.refresh(assessment)

        # 4. Map to student-safe question representations (strictly hiding answers)
        student_questions = self._map_to_student_questions(questions)

        logger.info(
            f"Created assessment '{assessment.id}' with {len(student_questions)} questions for course '{request.course_id}'"
        )

        return AssessmentGenerateResponse(
            assessment_id=assessment.id,
            title=assessment.title,
            questions=student_questions
        )

    def get_assessment(
        self,
        db: Session,
        assessment_id: str
    ) -> AssessmentDetailResponse:
        """
        Retrieve assessment details in student-safe format.
        Answers and expected solutions are strictly omitted.
        """
        assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
        if not assessment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assessment with ID '{assessment_id}' not found."
            )

        q_ids = assessment.questions or []
        questions = db.query(Question).filter(Question.id.in_(q_ids)).all()
        # Preserve original order
        q_dict = {q.id: q for q in questions}
        ordered_questions = [q_dict[qid] for qid in q_ids if qid in q_dict]

        student_questions = self._map_to_student_questions(ordered_questions)

        return AssessmentDetailResponse(
            assessment_id=assessment.id,
            title=assessment.title,
            course_id=assessment.course_id,
            student_id=assessment.student_id,
            questions=student_questions
        )

    def submit_assessment(
        self,
        db: Session,
        assessment_id: str,
        request: AssessmentSubmitRequest
    ) -> AssessmentSubmitResponse:
        """
        Grade submitted answers, calculate scores, provide course-grounded feedback,
        and persist attempt records.
        """
        assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
        if not assessment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assessment with ID '{assessment_id}' not found."
            )

        return self.grader.grade_assessment(
            db=db,
            assessment=assessment,
            student_id=request.student_id,
            student_answers=request.answers
        )

    @staticmethod
    def _map_to_student_questions(questions: List[Question]) -> List[StudentQuestionItem]:
        """Convert Question models to student-safe response models without answer keys."""
        items: List[StudentQuestionItem] = []
        for q in questions:
            citations: List[CitationItem] = []
            if q.source_ids and isinstance(q.source_ids, list):
                for s in q.source_ids:
                    if isinstance(s, dict):
                        try:
                            citations.append(CitationItem(**s))
                        except Exception:
                            pass

            items.append(
                StudentQuestionItem(
                    id=q.id,
                    question_type=q.question_type,
                    question=q.question_text,
                    options=q.options,
                    difficulty=q.difficulty,
                    topic=q.topic_id,
                    sources=citations
                )
            )
        return items
