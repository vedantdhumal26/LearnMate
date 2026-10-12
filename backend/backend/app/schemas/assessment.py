from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.tutor import CitationItem

class StudentQuestionItem(BaseModel):
    id: str = Field(..., description="Unique question identifier")
    question_type: str = Field(..., description="Type of question: mcq, short_answer, numerical")
    question: str = Field(..., description="Question statement or prompt")
    options: Optional[List[str]] = Field(default=None, description="List of choices for MCQ (4 options)")
    difficulty: str = Field(default="medium", description="Difficulty level: easy, medium, hard")
    topic: Optional[str] = Field(default=None, description="Topic or subject area")
    sources: List[CitationItem] = Field(default_factory=list, description="Grounding source citations from course material")

    model_config = ConfigDict(from_attributes=True)


class AssessmentGenerateRequest(BaseModel):
    course_id: str = Field(..., description="Course ID to generate questions from")
    student_id: Optional[str] = Field(default=None, description="Optional student ID for personalization and deduplication")
    topic: str = Field(..., min_length=1, description="Subject topic to generate questions for")
    difficulty: str = Field(default="medium", description="Difficulty level: easy, medium, hard")
    question_type: str = Field(default="mcq", description="Question format: mcq, short_answer, numerical")
    count: int = Field(default=5, ge=1, le=20, description="Number of questions to generate")


class AssessmentGenerateResponse(BaseModel):
    assessment_id: str = Field(..., description="Unique ID of created assessment")
    title: str = Field(..., description="Assessment title")
    questions: List[StudentQuestionItem] = Field(..., description="Student-safe question list (answers hidden)")

    model_config = ConfigDict(from_attributes=True)


class AssessmentDetailResponse(BaseModel):
    assessment_id: str = Field(..., description="Unique assessment ID")
    title: str = Field(..., description="Assessment title")
    course_id: str = Field(..., description="Course ID")
    student_id: Optional[str] = Field(default=None, description="Student ID if assigned")
    questions: List[StudentQuestionItem] = Field(..., description="Student-safe question list")

    model_config = ConfigDict(from_attributes=True)


class StudentAnswerItem(BaseModel):
    question_id: str = Field(..., description="ID of the question being answered")
    answer: str = Field(..., description="Student's submitted answer (e.g. 'B', short text, or numeric string)")


class AssessmentSubmitRequest(BaseModel):
    student_id: str = Field(..., min_length=1, description="Student submitting the assessment")
    answers: List[StudentAnswerItem] = Field(..., description="List of student answers")


class QuestionResultItem(BaseModel):
    question_id: str = Field(..., description="Question ID")
    correct: bool = Field(..., description="Whether the answer was graded correct")
    feedback: str = Field(..., description="Grounded explanatory feedback citing course material")
    sources: List[CitationItem] = Field(default_factory=list, description="Relevant citations supporting the answer")

    model_config = ConfigDict(from_attributes=True)


class TopicPerformanceItem(BaseModel):
    topic: str = Field(..., description="Topic name")
    score: float = Field(..., description="Percentage score for this topic (0.0 to 100.0)")
    correct: int = Field(..., description="Number of correctly answered questions")
    total: int = Field(..., description="Total questions for this topic")

    model_config = ConfigDict(from_attributes=True)


class AssessmentSubmitResponse(BaseModel):
    assessment_id: str = Field(..., description="ID of submitted assessment")
    score: float = Field(..., description="Total percentage score (0.0 to 100.0)")
    correct: int = Field(..., description="Total number of correct answers")
    total: int = Field(..., description="Total number of questions")
    question_results: List[QuestionResultItem] = Field(..., description="Detailed feedback per question")
    topic_performance: List[TopicPerformanceItem] = Field(default_factory=list, description="Performance breakdown per topic")

    model_config = ConfigDict(from_attributes=True)
