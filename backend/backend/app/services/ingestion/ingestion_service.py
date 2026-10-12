import os
import shutil
from typing import Tuple
from sqlalchemy.orm import Session
from fastapi import UploadFile, HTTPException, status

from app.models.source import Source
from app.models.document_chunk import DocumentChunk
from app.models.course import Course
from app.services.ingestion.pdf_processor import PDFProcessor
from app.services.ingestion.pptx_processor import PPTXProcessor
from app.services.embeddings.embedding_service import get_embedding_service
from app.services.vector_store.qdrant_store import get_vector_store
from app.utils.file_utils import (
    ensure_directory,
    compute_file_sha256,
    validate_pdf_upload,
    validate_pptx_upload,
    validate_mp4_upload,
    validate_course_upload,
)
from app.core.config import settings
from app.core.logging_config import logger

class IngestionService:
    def __init__(self, transcription_service=None, youtube_service=None):
        self.processor = PDFProcessor()
        self.pptx_processor = PPTXProcessor()
        self._transcription_service = transcription_service
        self._youtube_service = youtube_service
        self.embedding_service = get_embedding_service()
        self.vector_store = get_vector_store()

    @property
    def transcription_service(self):
        if self._transcription_service is None:
            from app.services.transcription.transcription_service import get_transcription_service
            self._transcription_service = get_transcription_service()
        return self._transcription_service

    @property
    def youtube_service(self):
        if self._youtube_service is None:
            from app.services.youtube.youtube_service import get_youtube_service
            self._youtube_service = get_youtube_service()
        return self._youtube_service

    async def ingest_pdf(
        self,
        course_id: str,
        file: UploadFile,
        db: Session
    ) -> Source:
        """
        Validate, save, extract text, chunk, embed, and store in PostgreSQL & Qdrant.
        """
        # 1. Validate course existence
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Course with ID '{course_id}' not found."
            )

        # 2. Validate PDF upload format and size
        file_bytes = await validate_pdf_upload(file, max_size_mb=settings.MAX_UPLOAD_SIZE_MB)
        file_name = file.filename

        # 3. Setup upload directory and save temporary file to check duplicates
        course_upload_dir = os.path.join(settings.UPLOAD_DIR, course_id)
        ensure_directory(course_upload_dir)
        destination_path = os.path.join(course_upload_dir, file_name)

        # Write file to disk
        with open(destination_path, "wb") as f:
            f.write(file_bytes)

        file_checksum = compute_file_sha256(destination_path)

        # Check for duplicate file in the same course
        existing_source = db.query(Source).filter(
            Source.course_id == course_id,
            Source.file_name == file_name
        ).first()

        if existing_source and existing_source.processing_status == "completed":
            # Check if identical checksum already processed
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"File '{file_name}' has already been uploaded and processed for this course."
            )

        # 4. Create or update Source database record
        source = existing_source or Source(
            course_id=course_id,
            file_name=file_name,
            file_type="application/pdf",
            file_path=destination_path,
            source_type="pdf",
            processing_status="processing"
        )
        if not existing_source:
            db.add(source)
        else:
            source.processing_status = "processing"
        db.commit()
        db.refresh(source)

        try:
            # 5. Extract text, page numbers, and chunk
            extracted_chunks = self.processor.process_pdf(
                file_path=destination_path,
                course_id=course_id,
                source_id=source.id,
                file_name=file_name
            )

            if not extracted_chunks:
                logger.warning(f"No extractable text chunks found in PDF {file_name}")
                source.processing_status = "completed"
                db.commit()
                return source

            # Delete any previous chunks for this source if re-processing
            db.query(DocumentChunk).filter(DocumentChunk.source_id == source.id).delete()
            self.vector_store.delete_source_vectors(source.id)

            # 6. Save chunks in PostgreSQL
            db_chunks = [
                DocumentChunk(
                    id=chunk.chunk_id,
                    source_id=chunk.source_id,
                    course_id=chunk.course_id,
                    content=chunk.content,
                    page_number=chunk.page_number,
                    slide_number=None,
                    start_time_seconds=None,
                    end_time_seconds=None,
                    modality="pdf",
                    visual_description=None,
                    chunk_index=chunk.chunk_index,
                    content_hash=chunk.content_hash
                )
                for chunk in extracted_chunks
            ]
            db.bulk_save_objects(db_chunks)
            db.commit()
            logger.info(f"Saved {len(db_chunks)} chunks to PostgreSQL for source {source.id}")

            # 7. Generate embeddings
            texts_to_embed = [chunk.content for chunk in extracted_chunks]
            embeddings = self.embedding_service.embed_documents(texts_to_embed)
            dimension = self.embedding_service.get_dimension()

            # 8. Ensure Qdrant collection exists and upsert vectors
            self.vector_store.ensure_collection(vector_size=dimension)

            payloads = [
                {
                    "course_id": chunk.course_id,
                    "source_id": chunk.source_id,
                    "file_name": chunk.file_name,
                    "page_number": chunk.page_number,
                    "slide_number": None,
                    "modality": "pdf",
                    "chunk_id": chunk.chunk_id,
                    "content": chunk.content
                }
                for chunk in extracted_chunks
            ]
            ids = [chunk.chunk_id for chunk in extracted_chunks]

            self.vector_store.upsert_vectors(
                vectors=embeddings,
                payloads=payloads,
                ids=ids
            )

            # Check if source or course was deleted during processing
            still_exists = db.query(Source).filter(Source.id == source.id).first()
            if not still_exists:
                logger.warning(f"Source {source.id} was deleted during ingestion. Cleaning up newly generated vectors.")
                self.vector_store.delete_source_vectors(source.id)
                return source

            # 9. Mark source as completed
            source.processing_status = "completed"
            db.commit()
            db.refresh(source)
            logger.info(f"Successfully processed PDF '{file_name}' for course {course_id}")
            return source

        except Exception as e:
            logger.error(f"Failed processing PDF '{file_name}': {e}", exc_info=True)
            source.processing_status = "failed"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process and index PDF: {str(e)}"
            )

    async def ingest_pptx(
        self,
        course_id: str,
        file: UploadFile,
        db: Session
    ) -> Source:
        """
        Validate, save, extract slide-by-slide text & visuals, chunk, embed,
        and store in database & Qdrant with exact slide citations.
        """
        # 1. Validate course existence
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Course with ID '{course_id}' not found."
            )

        # 2. Validate PPTX upload format, extension, and size
        file_bytes = await validate_pptx_upload(file, max_size_mb=settings.MAX_UPLOAD_SIZE_MB)
        file_name = file.filename

        # 3. Setup upload directory and save file
        course_upload_dir = os.path.join(settings.UPLOAD_DIR, course_id)
        ensure_directory(course_upload_dir)
        destination_path = os.path.join(course_upload_dir, file_name)

        with open(destination_path, "wb") as f:
            f.write(file_bytes)

        # Check for duplicate file in the same course
        existing_source = db.query(Source).filter(
            Source.course_id == course_id,
            Source.file_name == file_name
        ).first()

        if existing_source and existing_source.processing_status == "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"File '{file_name}' has already been uploaded and processed for this course."
            )

        # 4. Create or update Source record
        source = existing_source or Source(
            course_id=course_id,
            file_name=file_name,
            file_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            file_path=destination_path,
            source_type="pptx",
            processing_status="processing"
        )
        if not existing_source:
            db.add(source)
        else:
            source.processing_status = "processing"
        db.commit()
        db.refresh(source)

        try:
            # 5. Extract slide-by-slide text and diagrams
            extracted_chunks = self.pptx_processor.process_pptx(
                file_path=destination_path,
                course_id=course_id,
                source_id=source.id,
                file_name=file_name
            )

            if not extracted_chunks:
                logger.warning(f"No extractable text or visual chunks found in PPTX {file_name}")
                source.processing_status = "completed"
                db.commit()
                return source

            # Delete any previous chunks for this source if re-processing
            db.query(DocumentChunk).filter(DocumentChunk.source_id == source.id).delete()
            self.vector_store.delete_source_vectors(source.id)

            # 6. Save chunks in database
            db_chunks = [
                DocumentChunk(
                    id=chunk.chunk_id,
                    source_id=chunk.source_id,
                    course_id=chunk.course_id,
                    content=chunk.content,
                    page_number=None,
                    slide_number=chunk.slide_number,
                    start_time_seconds=None,
                    end_time_seconds=None,
                    modality=chunk.modality or "pptx_text",
                    visual_description=chunk.visual_description,
                    chunk_index=chunk.chunk_index,
                    content_hash=chunk.content_hash
                )
                for chunk in extracted_chunks
            ]
            db.bulk_save_objects(db_chunks)
            db.commit()
            logger.info(f"Saved {len(db_chunks)} PPTX chunks to database for source {source.id}")

            # 7. Generate embeddings
            texts_to_embed = [chunk.content for chunk in extracted_chunks]
            embeddings = self.embedding_service.embed_documents(texts_to_embed)
            dimension = self.embedding_service.get_dimension()

            # 8. Ensure Qdrant collection exists and upsert vectors
            self.vector_store.ensure_collection(vector_size=dimension)

            payloads = [
                {
                    "course_id": chunk.course_id,
                    "source_id": chunk.source_id,
                    "file_name": chunk.file_name,
                    "page_number": None,
                    "slide_number": chunk.slide_number,
                    "modality": chunk.modality or "pptx_text",
                    "visual_description": chunk.visual_description,
                    "chunk_id": chunk.chunk_id,
                    "content": chunk.content
                }
                for chunk in extracted_chunks
            ]
            ids = [chunk.chunk_id for chunk in extracted_chunks]

            self.vector_store.upsert_vectors(
                vectors=embeddings,
                payloads=payloads,
                ids=ids
            )

            # Check if source or course was deleted during processing
            still_exists = db.query(Source).filter(Source.id == source.id).first()
            if not still_exists:
                logger.warning(f"Source {source.id} was deleted during ingestion. Cleaning up newly generated vectors.")
                self.vector_store.delete_source_vectors(source.id)
                return source

            # 9. Mark source as completed
            source.processing_status = "completed"
            db.commit()
            db.refresh(source)
            logger.info(f"Successfully processed PPTX '{file_name}' for course {course_id}")
            return source

        except Exception as e:
            logger.error(f"Failed processing PPTX '{file_name}': {e}", exc_info=True)
            source.processing_status = "failed"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process and index PPTX: {str(e)}"
            )

    async def ingest_video(
        self,
        course_id: str,
        file: UploadFile,
        db: Session
    ) -> Source:
        """
        Validate, save, transcribe MP4 video, chunk transcript with timestamps,
        embed, and store in database & Qdrant with exact timestamp citations.
        """
        # 1. Validate course existence
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Course with ID '{course_id}' not found."
            )

        # 2. Validate MP4 upload format, extension, and size
        file_bytes = await validate_mp4_upload(file, max_size_mb=settings.MAX_UPLOAD_SIZE_MB)
        file_name = file.filename

        # 3. Setup upload directory and save file
        course_upload_dir = os.path.join(settings.UPLOAD_DIR, course_id)
        ensure_directory(course_upload_dir)
        destination_path = os.path.join(course_upload_dir, file_name)

        with open(destination_path, "wb") as f:
            f.write(file_bytes)

        # Check for duplicate file in the same course
        existing_source = db.query(Source).filter(
            Source.course_id == course_id,
            Source.file_name == file_name
        ).first()

        if existing_source and existing_source.processing_status == "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"File '{file_name}' has already been uploaded and processed for this course."
            )

        # 4. Create or update Source record
        source = existing_source or Source(
            course_id=course_id,
            file_name=file_name,
            file_type="video/mp4",
            file_path=destination_path,
            source_type="video",
            processing_status="processing"
        )
        if not existing_source:
            db.add(source)
        else:
            source.processing_status = "processing"
        db.commit()
        db.refresh(source)

        try:
            # 5. Transcribe speech-to-text with Groq Whisper
            transcription_res = self.transcription_service.transcribe_file(
                file_path=destination_path,
                filename=file_name
            )

            # 6. Group transcript segments into contiguous time-window chunks
            extracted_chunks = self.transcription_service.combine_segments_into_chunks(
                segments=transcription_res.segments,
                course_id=course_id,
                source_id=source.id,
                file_name=file_name
            )

            if not extracted_chunks:
                logger.warning(f"No spoken transcript chunks extracted from video {file_name}")
                source.processing_status = "completed"
                db.commit()
                return source

            # Delete any previous chunks for this source if re-processing
            db.query(DocumentChunk).filter(DocumentChunk.source_id == source.id).delete()
            self.vector_store.delete_source_vectors(source.id)

            # 7. Save chunks in database
            db_chunks = [
                DocumentChunk(
                    id=chunk.chunk_id,
                    source_id=chunk.source_id,
                    course_id=chunk.course_id,
                    content=chunk.content,
                    page_number=None,
                    slide_number=None,
                    start_time_seconds=chunk.start_time_seconds,
                    end_time_seconds=chunk.end_time_seconds,
                    modality="video_transcript",
                    visual_description=None,
                    chunk_index=chunk.chunk_index,
                    content_hash=chunk.content_hash
                )
                for chunk in extracted_chunks
            ]
            db.bulk_save_objects(db_chunks)
            db.commit()
            logger.info(f"Saved {len(db_chunks)} video transcript chunks to database for source {source.id}")

            # 8. Generate embeddings
            texts_to_embed = [chunk.content for chunk in extracted_chunks]
            embeddings = self.embedding_service.embed_documents(texts_to_embed)
            dimension = self.embedding_service.get_dimension()

            # 9. Ensure Qdrant collection exists and upsert vectors
            self.vector_store.ensure_collection(vector_size=dimension)

            payloads = [
                {
                    "course_id": chunk.course_id,
                    "source_id": chunk.source_id,
                    "file_name": chunk.file_name,
                    "page_number": None,
                    "slide_number": None,
                    "start_time_seconds": chunk.start_time_seconds,
                    "end_time_seconds": chunk.end_time_seconds,
                    "modality": "video_transcript",
                    "visual_description": None,
                    "chunk_id": chunk.chunk_id,
                    "content": chunk.content
                }
                for chunk in extracted_chunks
            ]
            ids = [chunk.chunk_id for chunk in extracted_chunks]

            self.vector_store.upsert_vectors(
                vectors=embeddings,
                payloads=payloads,
                ids=ids
            )

            # Check if source or course was deleted during processing
            still_exists = db.query(Source).filter(Source.id == source.id).first()
            if not still_exists:
                logger.warning(f"Source {source.id} was deleted during ingestion. Cleaning up newly generated vectors.")
                self.vector_store.delete_source_vectors(source.id)
                return source

            # 10. Mark source as completed
            source.processing_status = "completed"
            db.commit()
            db.refresh(source)
            logger.info(f"Successfully processed video '{file_name}' for course {course_id}")
            return source

        except Exception as e:
            logger.error(f"Failed processing video '{file_name}': {e}", exc_info=True)
            source.processing_status = "failed"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process and transcribe video: {str(e)}"
            )

    async def ingest_file(
        self,
        course_id: str,
        file: UploadFile,
        db: Session
    ) -> Source:
        """
        Unified ingestion entry point: validates file extension and dispatches to PDF, PPTX, or Video ingestion.
        """
        filename = (file.filename or "").lower().strip()
        video_exts = (".avi", ".mkv", ".mov", ".webm", ".flv", ".wmv", ".m4v", ".3gp", ".mpeg", ".mpg")
        if filename.endswith(".ppt"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only .pptx slide decks are supported in Phase 4A."
            )
        elif any(filename.endswith(ext) for ext in video_exts):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only .mp4 video files are supported in Phase 4B."
            )
        elif filename.endswith(".mp4"):
            return await self.ingest_video(course_id=course_id, file=file, db=db)
        elif filename.endswith(".pptx"):
            return await self.ingest_pptx(course_id=course_id, file=file, db=db)
        elif filename.endswith(".pdf"):
            return await self.ingest_pdf(course_id=course_id, file=file, db=db)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file format. Only .pdf files are supported (or .pptx, .mp4 in Phase 4)."
            )

    async def ingest_youtube(
        self,
        course_id: str,
        url: str,
        db: Session
    ) -> Source:
        """
        Validate YouTube URL, retrieve metadata, extract transcript captions,
        chunk with timestamps, embed, and index in Qdrant and database without storing audiovisual files.
        """
        from app.services.youtube.youtube_service import (
            InvalidYouTubeURLError,
            YouTubeUnavailableError,
            YouTubePrivateError,
            YouTubeNotEmbeddableError,
            TranscriptUnavailableError,
        )

        # 1. Validate course exists
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Course with ID '{course_id}' not found."
            )

        # 2. Validate URL and extract video_id and canonical_url
        try:
            video_id, canonical_url = self.youtube_service.extract_url(url)
        except InvalidYouTubeURLError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

        # 3. Check for existing source for this (course_id, video_id)
        existing_source = db.query(Source).filter(
            Source.course_id == course_id,
            Source.video_id == video_id
        ).first()

        if existing_source and existing_source.processing_status in ("completed", "ready"):
            return existing_source

        # 4. Retrieve metadata
        try:
            meta = self.youtube_service.get_metadata(video_id)
        except YouTubeUnavailableError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        except (YouTubePrivateError, YouTubeNotEmbeddableError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Error getting YouTube metadata for {video_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to retrieve YouTube metadata: {str(e)}"
            )

        # 5. Create or update Source record
        source = existing_source or Source(
            course_id=course_id,
            file_name=meta.title,
            file_type="youtube",
            file_path=canonical_url,
            source_type="youtube",
            video_id=video_id,
            canonical_url=canonical_url,
            duration_seconds=meta.duration_seconds,
            transcript_available=True,
            title=meta.title,
            processing_status="processing"
        )
        if not existing_source:
            db.add(source)
        else:
            source.processing_status = "processing"
            source.file_name = meta.title
            source.title = meta.title
            source.canonical_url = canonical_url
            source.duration_seconds = meta.duration_seconds
        db.commit()
        db.refresh(source)

        try:
            # 6. Retrieve transcript segments
            try:
                segments = self.youtube_service.get_transcript(video_id)
            except TranscriptUnavailableError as e:
                source.processing_status = "failed"
                source.transcript_available = False
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e)
                )

            # 7. Group into contiguous timestamped chunks
            extracted_chunks = self.youtube_service.combine_segments_into_chunks(
                segments=segments,
                course_id=course_id,
                source_id=source.id,
                file_name=meta.title,
                video_id=video_id,
                canonical_url=canonical_url
            )

            if not extracted_chunks:
                source.processing_status = "completed"
                source.transcript_available = False
                db.commit()
                return source

            # 8. Clean up prior chunks if re-processing
            db.query(DocumentChunk).filter(DocumentChunk.source_id == source.id).delete()
            self.vector_store.delete_source_vectors(source.id)

            # 9. Save chunks in database
            db_chunks = [
                DocumentChunk(
                    id=chunk.chunk_id,
                    source_id=chunk.source_id,
                    course_id=chunk.course_id,
                    content=chunk.content,
                    page_number=None,
                    slide_number=None,
                    start_time_seconds=chunk.start_time_seconds,
                    end_time_seconds=chunk.end_time_seconds,
                    modality="youtube",
                    video_id=video_id,
                    canonical_url=canonical_url,
                    visual_description=None,
                    chunk_index=chunk.chunk_index,
                    content_hash=chunk.content_hash
                )
                for chunk in extracted_chunks
            ]
            db.bulk_save_objects(db_chunks)
            db.commit()
            logger.info(f"Saved {len(db_chunks)} YouTube transcript chunks to database for source {source.id}")

            # 10. Generate embeddings
            texts_to_embed = [chunk.content for chunk in extracted_chunks]
            embeddings = self.embedding_service.embed_documents(texts_to_embed)
            dimension = self.embedding_service.get_dimension()

            # 11. Ensure Qdrant collection exists and upsert vectors
            self.vector_store.ensure_collection(vector_size=dimension)

            payloads = [
                {
                    "course_id": chunk.course_id,
                    "source_id": chunk.source_id,
                    "file_name": chunk.file_name,
                    "page_number": None,
                    "slide_number": None,
                    "start_time_seconds": chunk.start_time_seconds,
                    "end_time_seconds": chunk.end_time_seconds,
                    "modality": "youtube",
                    "video_id": video_id,
                    "canonical_url": canonical_url,
                    "visual_description": None,
                    "chunk_id": chunk.chunk_id,
                    "content": chunk.content
                }
                for chunk in extracted_chunks
            ]
            ids = [chunk.chunk_id for chunk in extracted_chunks]

            self.vector_store.upsert_vectors(
                vectors=embeddings,
                payloads=payloads,
                ids=ids
            )

            # Check if source or course was deleted during processing
            still_exists = db.query(Source).filter(Source.id == source.id).first()
            if not still_exists:
                logger.warning(f"Source {source.id} was deleted during ingestion. Cleaning up newly generated vectors.")
                self.vector_store.delete_source_vectors(source.id)
                return source

            # 12. Mark source as completed
            source.processing_status = "completed"
            source.transcript_available = True
            db.commit()
            db.refresh(source)
            logger.info(f"Successfully processed YouTube video '{meta.title}' for course {course_id}")
            return source

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed processing YouTube video '{video_id}': {e}", exc_info=True)
            source.processing_status = "failed"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process and index YouTube video: {str(e)}"
            )
