import os
import shutil
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.core.config import settings
from app.core.logging_config import logger
from app.models.user import User
from app.models.course import Course
from app.models.source import Source
from app.models.document_chunk import DocumentChunk
from app.models.assessment import Assessment, Question, QuestionAttempt, AssessmentAttempt
from app.models.learner_mastery import LearnerMastery
from app.schemas.course import CourseCreate, CourseUpdate, CourseResponse, CourseDetailResponse, SourceSummary
from app.schemas.youtube import YouTubeSourceRequest, YouTubeSourceResponse
from app.services.vector_store.qdrant_store import get_vector_store

router = APIRouter(prefix="/courses", tags=["Courses"])

@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
def create_course(
    course_in: CourseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new course. Owner is strictly derived from the authenticated user."""
    course = Course(
        title=course_in.title.strip(),
        description=course_in.description.strip() if course_in.description else None,
        owner_id=current_user.id
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course

@router.get("", response_model=List[CourseResponse])
def list_courses(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List only the courses belonging to the authenticated user."""
    courses = (
        db.query(Course)
        .filter(Course.owner_id == current_user.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return courses

@router.get("/{course_id}", response_model=CourseDetailResponse)
def get_course(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve detailed course information. Only accessible if owned by the authenticated user."""
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.owner_id == current_user.id
    ).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course with ID '{course_id}' not found."
        )

    chunk_count = db.query(DocumentChunk).filter(DocumentChunk.course_id == course_id).count()

    sources_summary = [
        SourceSummary(
            id=s.id,
            file_name=s.file_name,
            file_type=s.file_type,
            processing_status=s.processing_status,
            source_type=s.source_type,
            title=getattr(s, "title", None) or s.file_name,
            video_id=getattr(s, "video_id", None),
            canonical_url=getattr(s, "canonical_url", None),
            created_at=s.created_at
        )
        for s in course.sources
    ]

    return CourseDetailResponse(
        id=course.id,
        title=course.title,
        description=course.description,
        owner_id=course.owner_id,
        created_at=course.created_at,
        updated_at=course.updated_at,
        sources=sources_summary,
        chunk_count=chunk_count
    )

@router.post("/{course_id}/youtube", response_model=YouTubeSourceResponse, status_code=status.HTTP_201_CREATED)
async def add_youtube_source(
    course_id: str,
    payload: YouTubeSourceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add a public YouTube video URL as a course source.
    Only accessible by the course owner.
    """
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.owner_id == current_user.id
    ).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course with ID '{course_id}' not found."
        )

    from app.services.ingestion.ingestion_service import IngestionService
    ingestion_service = IngestionService()

    source = await ingestion_service.ingest_youtube(
        course_id=course_id,
        url=payload.url,
        db=db
    )

    api_status = "ready" if source.processing_status in ("completed", "ready") else source.processing_status

    return YouTubeSourceResponse(
        source_id=source.id,
        video_id=source.video_id or "",
        canonical_url=source.canonical_url or payload.url,
        status=api_status,
        message="YouTube video transcript processed and indexed successfully.",
        title=getattr(source, "title", None) or source.file_name,
        duration_seconds=source.duration_seconds
    )


@router.patch("/{course_id}", response_model=CourseResponse, status_code=status.HTTP_200_OK)
@router.put("/{course_id}", response_model=CourseResponse, status_code=status.HTTP_200_OK)
def update_course(
    course_id: str,
    course_in: CourseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update course title or description.
    Only accessible by the course owner.
    """
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.owner_id == current_user.id
    ).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course with ID '{course_id}' not found."
        )

    update_data = course_in.model_dump(exclude_unset=True)
    if not update_data or all(v is None for v in update_data.values()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields provided for course update."
        )

    if "title" in update_data and update_data["title"] is not None:
        course.title = update_data["title"]

    if "description" in update_data:
        course.description = update_data["description"].strip() if update_data["description"] else None

    db.commit()
    db.refresh(course)
    return course


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a course and all associated resources.
    Only accessible by the course owner.
    Cleans up vector store embeddings, database records, and physical uploaded files.
    """
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.owner_id == current_user.id
    ).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course with ID '{course_id}' not found."
        )

    # 1. Clean up vector embeddings from Qdrant vector store
    vector_store = get_vector_store()
    try:
        vector_store.delete_course_vectors(course_id)
    except Exception as e:
        logger.error(f"Error deleting vector embeddings for course {course_id}: {e}")

    # 2. Clean up database records explicitly to preserve referential integrity
    assessment_ids = [a.id for a in db.query(Assessment.id).filter(Assessment.course_id == course_id).all()]
    question_ids = [q.id for q in db.query(Question.id).filter(Question.course_id == course_id).all()]

    if assessment_ids:
        db.query(AssessmentAttempt).filter(AssessmentAttempt.assessment_id.in_(assessment_ids)).delete(synchronize_session=False)
        db.query(QuestionAttempt).filter(QuestionAttempt.assessment_id.in_(assessment_ids)).delete(synchronize_session=False)

    if question_ids:
        db.query(QuestionAttempt).filter(QuestionAttempt.question_id.in_(question_ids)).delete(synchronize_session=False)

    db.query(Question).filter(Question.course_id == course_id).delete(synchronize_session=False)
    db.query(Assessment).filter(Assessment.course_id == course_id).delete(synchronize_session=False)
    db.query(LearnerMastery).filter(LearnerMastery.course_id == course_id).delete(synchronize_session=False)
    db.query(DocumentChunk).filter(DocumentChunk.course_id == course_id).delete(synchronize_session=False)
    db.query(Source).filter(Source.course_id == course_id).delete(synchronize_session=False)
    db.delete(course)
    db.commit()

    # 3. Clean up physical files on disk
    course_dir = os.path.join(settings.UPLOAD_DIR, course_id)
    if os.path.isdir(course_dir):
        try:
            shutil.rmtree(course_dir, ignore_errors=True)
            logger.info(f"Removed course upload directory: {course_dir}")
        except Exception as e:
            logger.warning(f"Could not remove upload directory {course_dir}: {e}")

    return None
