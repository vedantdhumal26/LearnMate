import os
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.core.logging_config import logger
from app.models.user import User
from app.models.course import Course
from app.models.source import Source
from app.models.document_chunk import DocumentChunk
from app.schemas.upload import UploadResponse, SourceStatusResponse
from app.services.ingestion.ingestion_service import IngestionService
from app.services.vector_store.qdrant_store import get_vector_store

router = APIRouter(prefix="/courses", tags=["Uploads"])
ingestion_service = IngestionService()

@router.post("/{course_id}/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_course_file(
    course_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload and process a course document (.pdf, .pptx, or video .mp4).
    Verifies that the authenticated user owns the course.
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

    source = await ingestion_service.ingest_file(
        course_id=course_id,
        file=file,
        db=db
    )

    return UploadResponse(
        source_id=source.id,
        file_name=source.file_name,
        status=source.processing_status,
        id=source.id,
        processing_status=source.processing_status
    )

@router.get("/{course_id}/uploads/{source_id}", response_model=SourceStatusResponse)
def get_upload_status(
    course_id: str,
    source_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check the ingestion status and chunk count of an uploaded document.
    Enforces course ownership to prevent unauthorized source metadata inspection.
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

    source = db.query(Source).filter(
        Source.id == source_id,
        Source.course_id == course_id
    ).first()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source with ID '{source_id}' not found for course '{course_id}'."
        )

    chunk_count = db.query(DocumentChunk).filter(DocumentChunk.source_id == source_id).count()

    slide_count = None
    visual_count = None
    duration_seconds = None
    segment_count = None

    if source.source_type == "pptx":
        slide_count = (
            db.query(DocumentChunk.slide_number)
            .filter(DocumentChunk.source_id == source_id, DocumentChunk.slide_number.isnot(None))
            .distinct()
            .count()
        )
        visual_count = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.source_id == source_id, DocumentChunk.modality == "pptx_visual")
            .count()
        )
    elif source.source_type in ("video", "youtube"):
        from sqlalchemy import func
        segment_count = chunk_count
        if source.source_type == "youtube" and source.duration_seconds is not None:
            duration_seconds = source.duration_seconds
        else:
            max_end = (
                db.query(func.max(DocumentChunk.end_time_seconds))
                .filter(DocumentChunk.source_id == source_id)
                .scalar()
            )
            duration_seconds = round(float(max_end), 2) if max_end is not None else None

    return SourceStatusResponse(
        source_id=source.id,
        course_id=source.course_id,
        file_name=source.file_name,
        file_type=source.file_type,
        processing_status=source.processing_status,
        source_type=source.source_type,
        title=getattr(source, "title", None) or source.file_name,
        video_id=getattr(source, "video_id", None),
        canonical_url=getattr(source, "canonical_url", None),
        chunks_count=chunk_count,
        slide_count=slide_count,
        visual_count=visual_count,
        duration_seconds=duration_seconds,
        segment_count=segment_count,
        created_at=source.created_at
    )


@router.delete("/{course_id}/materials/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
@router.delete("/{course_id}/uploads/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course_material(
    course_id: str,
    material_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete an individual uploaded material/source from a course.
    Verifies that the authenticated user owns the course and that the material belongs to this course.
    Cleans up associated vector store embeddings, document chunks, and physical files.
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

    source = db.query(Source).filter(
        Source.id == material_id,
        Source.course_id == course_id
    ).first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID '{material_id}' not found in course '{course_id}'."
        )

    # 1. Clean up vector embeddings for this source
    try:
        vector_store = get_vector_store()
        vector_store.delete_source_vectors(source.id)
    except Exception as e:
        logger.error(f"Error deleting vector embeddings for source {material_id}: {e}")

    # 2. Clean up physical file on disk (if not shared by other courses/sources)
    file_path = source.file_path
    if file_path and os.path.isfile(file_path):
        other_usage = db.query(Source).filter(
            Source.id != source.id,
            Source.file_path == file_path
        ).count()
        if other_usage == 0:
            try:
                os.remove(file_path)
                logger.info(f"Removed physical file: {file_path}")
            except OSError as e:
                logger.warning(f"Could not delete physical file {file_path}: {e}")

    # 3. Clean up database chunks and source record
    db.query(DocumentChunk).filter(DocumentChunk.source_id == source.id).delete(synchronize_session=False)
    db.delete(source)
    db.commit()

    return None
