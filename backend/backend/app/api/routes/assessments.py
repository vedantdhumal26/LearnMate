from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.course import Course
from app.models.assessment import Assessment
from app.schemas.assessment import (
    AssessmentGenerateRequest,
    AssessmentGenerateResponse,
    AssessmentDetailResponse,
    AssessmentSubmitRequest,
    AssessmentSubmitResponse,
)
from app.services.assessment.assessment_service import AssessmentService

router = APIRouter(prefix="/assessments", tags=["Assessments"])
assessment_service = AssessmentService()

@router.post("/generate", response_model=AssessmentGenerateResponse, status_code=status.HTTP_201_CREATED)
def generate_assessment(
    request: AssessmentGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate an adaptive, course-grounded assessment.
    Verifies that the authenticated user owns the course.
    Student identity is derived from the authenticated user.
    """
    course = db.query(Course).filter(
        Course.id == request.course_id,
        Course.owner_id == current_user.id
    ).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course with ID '{request.course_id}' not found."
        )

    # Derive student identity from authenticated user
    request.student_id = current_user.id
    return assessment_service.generate_assessment(db=db, request=request)


@router.get("/{assessment_id}", response_model=AssessmentDetailResponse, status_code=status.HTTP_200_OK)
def get_assessment(
    assessment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve an assessment in student-safe format.
    Verifies that the authenticated user owns the assessment's course.
    """
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment with ID '{assessment_id}' not found."
        )

    course = db.query(Course).filter(
        Course.id == assessment.course_id,
        Course.owner_id == current_user.id
    ).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment with ID '{assessment_id}' not found."
        )

    return assessment_service.get_assessment(db=db, assessment_id=assessment_id)


@router.post("/{assessment_id}/submit", response_model=AssessmentSubmitResponse, status_code=status.HTTP_200_OK)
def submit_assessment(
    assessment_id: str,
    request: AssessmentSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit answers for an assessment.
    Verifies that the authenticated user owns the assessment's course.
    Student identity is derived from the authenticated user.
    """
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment with ID '{assessment_id}' not found."
        )

    course = db.query(Course).filter(
        Course.id == assessment.course_id,
        Course.owner_id == current_user.id
    ).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment with ID '{assessment_id}' not found."
        )

    # Derive student identity from authenticated user
    request.student_id = current_user.id
    return assessment_service.submit_assessment(db=db, assessment_id=assessment_id, request=request)
