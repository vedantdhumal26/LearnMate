import os
import uuid
import re
from typing import List, Optional, Tuple
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from app.services.ingestion.pdf_processor import ExtractedChunk
from app.utils.text_utils import clean_extracted_text
from app.utils.hashing import generate_chunk_hash
from app.utils.file_utils import ensure_directory
from app.services.llm.vision_service import VisionService, get_vision_service
from app.core.config import settings
from app.core.logging_config import logger

class PPTXProcessor:
    """
    Dedicated slide-by-slide processor for PowerPoint presentations (.pptx).
    Extracts structured text from titles, placeholders, text frames, tables, and groups.
    Extracts embedded diagrams and pictures, saves them, and generates visual descriptions.
    """
    def __init__(
        self,
        vision_service: Optional[VisionService] = None,
        max_chunk_size: int = 1000,
        chunk_overlap: int = 100,
    ):
        self.vision_service = vision_service or get_vision_service()
        self.max_chunk_size = max_chunk_size
        self.chunk_overlap = chunk_overlap

    def process_pptx(
        self,
        file_path: str,
        course_id: str,
        source_id: str,
        file_name: str,
    ) -> List[ExtractedChunk]:
        """
        Processes a PPTX presentation slide-by-slide.
        Returns a list of ExtractedChunk objects with exact slide_number and modality.
        """
        logger.info(f"Opening PPTX for processing: '{file_name}' (path: {file_path})")
        try:
            prs = Presentation(file_path)
        except Exception as e:
            logger.error(f"Failed to parse PPTX presentation '{file_name}': {e}")
            raise ValueError(f"Unable to read or parse PPTX file: {e}")

        total_slides = len(prs.slides)
        logger.info(f"PPTX '{file_name}' contains {total_slides} slide(s)")

        # Prepare directory for visual artifacts
        # e.g., uploads/<course_id>/<source_id>/visuals/
        visuals_dir = os.path.join(settings.UPLOAD_DIR, course_id, source_id, "visuals")
        ensure_directory(visuals_dir)

        extracted_chunks: List[ExtractedChunk] = []
        global_chunk_idx = 0

        for slide_idx, slide in enumerate(prs.slides):
            slide_number = slide_idx + 1  # 1-indexed slide number

            # A. Extract text content
            text_lines = []
            for shape in slide.shapes:
                text_lines.extend(self._extract_shape_text(shape))

            slide_raw_text = "\n".join(text_lines).strip()
            clean_text = clean_extracted_text(slide_raw_text)

            if clean_text:
                text_chunks = self._chunk_slide_text(clean_text)
                for chunk_text in text_chunks:
                    formatted_content = f"[Slide {slide_number}]\n{chunk_text}"
                    c_hash = generate_chunk_hash(
                        course_id=course_id,
                        source_id=source_id,
                        page_number=None,
                        chunk_index=global_chunk_idx,
                        content=formatted_content,
                        slide_number=slide_number
                    )
                    extracted_chunks.append(
                        ExtractedChunk(
                            chunk_id=str(uuid.uuid4()),
                            course_id=course_id,
                            source_id=source_id,
                            file_name=file_name,
                            page_number=None,
                            slide_number=slide_number,
                            chunk_index=global_chunk_idx,
                            content=formatted_content,
                            content_hash=c_hash,
                            modality="pptx_text",
                            visual_description=None
                        )
                    )
                    global_chunk_idx += 1

            # B. Extract visual images and diagrams
            slide_images = []
            for shape in slide.shapes:
                slide_images.extend(self._extract_shape_images(shape))

            for img_idx, (image_bytes, ext, mime_type) in enumerate(slide_images, 1):
                safe_ext = ext.lstrip(".").lower() if ext else "png"
                media_filename = f"slide-{slide_number:03d}-image-{img_idx:03d}.{safe_ext}"
                media_path = os.path.join(visuals_dir, media_filename)

                # Save extracted image bytes to disk
                try:
                    with open(media_path, "wb") as img_file:
                        img_file.write(image_bytes)
                except Exception as save_err:
                    logger.error(f"Failed to save visual '{media_filename}': {save_err}")
                    continue

                # Generate concise factual description via VisionService
                try:
                    description = self.vision_service.describe_image(
                        image_bytes=image_bytes,
                        mime_type=mime_type,
                        slide_number=slide_number,
                        media_filename=media_filename
                    )
                except Exception as vis_err:
                    logger.error(
                        f"Vision processing failed for visual '{media_filename}' on slide {slide_number}: {vis_err}. "
                        f"Preserving chunk with fallback description."
                    )
                    description = f"Visual element on slide {slide_number} ({media_filename}). Visual description unavailable."

                visual_content = f"[Slide {slide_number} Visual: {media_filename}]\n{description}"
                v_hash = generate_chunk_hash(
                    course_id=course_id,
                    source_id=source_id,
                    page_number=None,
                    chunk_index=global_chunk_idx,
                    content=visual_content,
                    slide_number=slide_number
                )

                extracted_chunks.append(
                    ExtractedChunk(
                        chunk_id=str(uuid.uuid4()),
                        course_id=course_id,
                        source_id=source_id,
                        file_name=file_name,
                        page_number=None,
                        slide_number=slide_number,
                        chunk_index=global_chunk_idx,
                        content=visual_content,
                        content_hash=v_hash,
                        modality="pptx_visual",
                        visual_description=description
                    )
                )
                global_chunk_idx += 1

        logger.info(
            f"PPTX '{file_name}' processing complete: {len(extracted_chunks)} chunks extracted "
            f"across {total_slides} slides."
        )
        return extracted_chunks

    def _extract_shape_text(self, shape) -> List[str]:
        """Extracts text recursively from shapes, tables, and grouped shapes."""
        texts: List[str] = []
        try:
            if shape.has_text_frame:
                for p in shape.text_frame.paragraphs:
                    t = p.text.strip()
                    if t:
                        texts.append(t)
            elif shape.has_table:
                for row in shape.table.rows:
                    row_parts = []
                    for cell in row.cells:
                        if cell.text_frame and cell.text_frame.text.strip():
                            row_parts.append(cell.text_frame.text.strip())
                    if row_parts:
                        texts.append(" | ".join(row_parts))
            elif shape.shape_type == MSO_SHAPE_TYPE.GROUP:
                for child in shape.shapes:
                    texts.extend(self._extract_shape_text(child))
        except Exception as e:
            logger.debug(f"Non-critical shape text extraction notice: {e}")
        return texts

    def _extract_shape_images(self, shape) -> List[Tuple[bytes, str, str]]:
        """Extracts image blobs recursively from pictures and grouped shapes."""
        images: List[Tuple[bytes, str, str]] = []
        try:
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                if hasattr(shape, "image"):
                    img = shape.image
                    ext = getattr(img, "ext", "png") or "png"
                    mime = getattr(img, "content_type", f"image/{ext}") or f"image/{ext}"
                    images.append((img.blob, ext, mime))
            elif shape.shape_type == MSO_SHAPE_TYPE.GROUP:
                for child in shape.shapes:
                    images.extend(self._extract_shape_images(child))
        except Exception as e:
            logger.debug(f"Non-critical shape image extraction notice: {e}")
        return images

    def _chunk_slide_text(self, text: str) -> List[str]:
        """Splits long slide text into bounded chunks if necessary."""
        if len(text) <= self.max_chunk_size:
            return [text]

        # Break text along paragraphs or sentences
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        chunks = []
        current_chunk = []
        current_len = 0

        for p in paragraphs:
            p_len = len(p)
            if current_len + p_len > self.max_chunk_size and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = [p]
                current_len = p_len
            else:
                current_chunk.append(p)
                current_len += p_len + 1

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks if chunks else [text]
