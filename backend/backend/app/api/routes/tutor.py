from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.course import Course
from app.schemas.tutor import TutorChatRequest, TutorChatResponse
from app.services.rag.tutor_service import TutorService

router = APIRouter(prefix="/tutor", tags=["Tutor"])
tutor_service = TutorService()

@router.post("/chat", response_model=TutorChatResponse, status_code=status.HTTP_200_OK)
def chat_with_tutor(
    request: TutorChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    RAG-grounded tutor endpoint.
    Course ownership is verified BEFORE retrieval.
    Existing course_id Qdrant filtering is preserved.
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

    return tutor_service.answer_question(request=request, db=db)
