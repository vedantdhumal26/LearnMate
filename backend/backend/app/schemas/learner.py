from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class TopicMasteryItem(BaseModel):
    topic: str = Field(..., description="Topic or subject domain identifier")
    mastery_score: float = Field(..., ge=0.0, le=1.0, description="Normalized mastery score from 0.0 to 1.0")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in mastery estimate from 0.0 to 1.0")
    attempts: int = Field(..., ge=0, description="Total question attempts evaluated for this topic")
    correct_attempts: int = Field(..., ge=0, description="Total correct attempts for this topic")
    last_interaction: datetime = Field(..., description="Timestamp of the most recent evaluation or practice")

class TopicMasteryResponse(BaseModel):
    student_id: str
    course_id: str
    topics: List[TopicMasteryItem] = Field(default_factory=list)

class StrongTopicSummaryItem(BaseModel):
    topic: str
    mastery_score: float = Field(..., ge=0.0, le=1.0)

class WeakTopicSummaryItem(BaseModel):
    topic: str
    mastery_score: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field(..., description="Clear explanation for why this topic is flagged as weak")

class RecentTopicSummaryItem(BaseModel):
    topic: str
    mastery_score: float = Field(..., ge=0.0, le=1.0)
    last_interaction: datetime

class LearnerSummaryResponse(BaseModel):
    overall_mastery: float = Field(..., ge=0.0, le=1.0, description="Aggregate average mastery across all evaluated topics")
    strong_topics: List[StrongTopicSummaryItem] = Field(default_factory=list)
    weak_topics: List[WeakTopicSummaryItem] = Field(default_factory=list)
    recent_topics: List[RecentTopicSummaryItem] = Field(default_factory=list)
    status: Optional[str] = Field(default=None, description="Status indicator such as 'active' or 'new_learner'")

class RecommendationItem(BaseModel):
    topic: str
    priority: str = Field(..., description="Priority level: high, medium, low")
    reason: str = Field(..., description="Explainable reason based on real performance")
    recommended_action: str = Field(..., description="Action to take, e.g. practice, challenge, diagnostic")
    recommended_difficulty: Optional[str] = Field(default="medium", description="Suggested question difficulty")
    recommended_question_count: Optional[int] = Field(default=5, description="Suggested question count for practice session")

class LearnerRecommendationsResponse(BaseModel):
    recommendations: List[RecommendationItem] = Field(default_factory=list)

class StudyPlanItem(BaseModel):
    day: int = Field(..., ge=1, le=7, description="Day number in the 7-day study plan")
    topic: str = Field(..., description="Target study topic")
    priority: str = Field(..., description="Priority level: high, medium, low")
    action: str = Field(..., description="Study action: practice, tutor_review, review_material, challenge, diagnostic")
    difficulty: str = Field(..., description="Suggested question or study difficulty: easy, medium, hard")
    question_count: int = Field(..., ge=0, description="Suggested question count for the daily activity")
    reason: str = Field(..., description="Deterministic, explainable rationale based on real mastery")

class StudyPlanResponse(BaseModel):
    student_id: str = Field(..., description="Student ID")
    course_id: str = Field(..., description="Course ID")
    plan_duration_days: int = Field(default=7, description="Duration of study plan in days")
    plan: List[StudyPlanItem] = Field(default_factory=list, description="Ordered 7-day study plan")

