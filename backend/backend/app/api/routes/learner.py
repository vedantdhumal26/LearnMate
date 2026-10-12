from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.course import Course
from app.schemas.learner import (
    TopicMasteryResponse,
    LearnerSummaryResponse,
    LearnerRecommendationsResponse,
    StudyPlanResponse,
)
from app.services.learner_model.learner_service import LearnerModelService

router = APIRouter(prefix="/learner", tags=["Learner Model"])
learner_service = LearnerModelService()

def _verify_learner_access(db: Session, current_user: User, student_id: str, course_id: str) -> Course:
    # 1. Enforce student identity isolation
    if student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You cannot access another student's learner records."
        )

    # 2. Enforce course ownership
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.owner_id == current_user.id
    ).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course with ID '{course_id}' not found."
        )
    return course

@router.get(
    "/{student_id}/courses/{course_id}/mastery",
    response_model=TopicMasteryResponse,
    status_code=status.HTTP_200_OK
)
def get_topic_mastery(
    student_id: str,
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve topic-wise mastery profile for a given student and course.
    Only the authenticated user may retrieve their own mastery records for their owned course.
    """
    _verify_learner_access(db=db, current_user=current_user, student_id=student_id, course_id=course_id)
    return learner_service.get_topic_mastery(db=db, student_id=current_user.id, course_id=course_id)

@router.get(
    "/{student_id}/courses/{course_id}/summary",
    response_model=LearnerSummaryResponse,
    status_code=status.HTTP_200_OK
)
def get_learner_summary(
    student_id: str,
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve aggregate learner summary for a course.
    Only the authenticated user may retrieve their own summary.
    """
    _verify_learner_access(db=db, current_user=current_user, student_id=student_id, course_id=course_id)
    return learner_service.get_learner_summary(db=db, student_id=current_user.id, course_id=course_id)

@router.get(
    "/{student_id}/courses/{course_id}/recommendations",
    response_model=LearnerRecommendationsResponse,
    status_code=status.HTTP_200_OK
)
def get_recommendations(
    student_id: str,
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate personalized practice recommendations grounded in real student mastery data.
    Only the authenticated user may retrieve their own recommendations.
    """
    _verify_learner_access(db=db, current_user=current_user, student_id=student_id, course_id=course_id)
    return learner_service.get_recommendations(db=db, student_id=current_user.id, course_id=course_id)

@router.get(
    "/{student_id}/courses/{course_id}/study-plan",
    response_model=StudyPlanResponse,
    status_code=status.HTTP_200_OK
)
def get_study_plan(
    student_id: str,
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate a deterministic 7-day personalized study plan grounded in actual learner mastery.
    Only the authenticated user may retrieve their own study plan for their owned course.
    """
    _verify_learner_access(db=db, current_user=current_user, student_id=student_id, course_id=course_id)
    return learner_service.get_study_plan(db=db, student_id=current_user.id, course_id=course_id)

