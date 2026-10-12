import uuid
import re
from typing import List, Dict, Any, Optional
import pymupdf
from dataclasses import dataclass

from app.utils.text_utils import clean_extracted_text, is_heading
from app.utils.hashing import compute_content_hash, generate_chunk_hash
from app.core.logging_config import logger

@dataclass
class ExtractedChunk:
    chunk_id: str
    course_id: str
    source_id: str
    file_name: str
    page_number: Optional[int]
    chunk_index: int
    content: str
    content_hash: str
    slide_number: Optional[int] = None
    start_time_seconds: Optional[float] = None
    end_time_seconds: Optional[float] = None
    modality: Optional[str] = "pdf"
    visual_description: Optional[str] = None
    video_id: Optional[str] = None
    canonical_url: Optional[str] = None

class PDFProcessor:
    def __init__(
        self,
        min_chunk_size: int = 150,
        target_chunk_size: int = 650,
        max_chunk_size: int = 1000,
        chunk_overlap: int = 100,
    ):
        self.min_chunk_size = min_chunk_size
        self.target_chunk_size = target_chunk_size
        self.max_chunk_size = max_chunk_size
        self.chunk_overlap = chunk_overlap

    def process_pdf(
        self,
        file_path: str,
        course_id: str,
        source_id: str,
        file_name: str
    ) -> List[ExtractedChunk]:
        """
        Open PDF, extract text page by page preserving page metadata,
        detect headings, create sensible chunks, and generate hashes.
        """
        logger.info(f"Opening PDF for processing: {file_name} (path: {file_path})")
        try:
            doc = pymupdf.open(file_path)
        except Exception as e:
            logger.error(f"Failed to open PDF {file_path}: {e}")
            raise ValueError(f"Unable to read or parse PDF file: {e}")

        total_pages = len(doc)
        logger.info(f"PDF {file_name} has {total_pages} pages")

        extracted_chunks: List[ExtractedChunk] = []
        seen_hashes = set()
        global_chunk_idx = 0

        for page_idx in range(total_pages):
            page_number = page_idx + 1  # 1-indexed for citation
            page = doc[page_idx]

            # Extract text blocks: each block is (x0, y0, x1, y1, text, block_no, block_type)
            # block_type == 0 indicates text
            try:
                blocks = page.get_text("blocks")
            except Exception as e:
                logger.warning(f"Error extracting blocks from page {page_number}: {e}")
                blocks = []

            # Clean and filter blocks
            text_blocks: List[str] = []
            current_heading: Optional[str] = None

            for b in blocks:
                if len(b) > 4 and b[6] == 0:  # Text block
                    raw_text = b[4]
                    cleaned_block = clean_extracted_text(raw_text)
                    if not cleaned_block:
                        continue

                    # Check for section heading
                    first_line = cleaned_block.split("\n")[0]
                    if is_heading(first_line):
                        current_heading = first_line

                    # Attach heading context if detected
                    if current_heading and not cleaned_block.startswith(current_heading):
                        formatted_block = f"[{current_heading}]\n{cleaned_block}"
                    else:
                        formatted_block = cleaned_block

                    text_blocks.append(formatted_block)

            # If no blocks detected via get_text("blocks"), fallback to full page text
            if not text_blocks:
                raw_page_text = page.get_text("text")
                cleaned_page_text = clean_extracted_text(raw_page_text)
                if cleaned_page_text:
                    text_blocks.append(cleaned_page_text)

            # Chunk the page text blocks
            page_chunks = self._chunk_page_blocks(text_blocks, page_number)

            for chunk_text in page_chunks:
                # Discard useless tiny chunks
                if len(chunk_text.strip()) < self.min_chunk_size and total_pages > 1 and len(page_chunks) > 1:
                    continue

                content_hash = compute_content_hash(chunk_text)
                if content_hash in seen_hashes:
                    logger.debug(f"Skipping duplicate chunk on page {page_number}")
                    continue

                seen_hashes.add(content_hash)
                chunk_id = str(uuid.uuid4())

                extracted_chunks.append(
                    ExtractedChunk(
                        chunk_id=chunk_id,
                        course_id=course_id,
                        source_id=source_id,
                        file_name=file_name,
                        page_number=page_number,
                        chunk_index=global_chunk_idx,
                        content=chunk_text,
                        content_hash=content_hash
                    )
                )
                global_chunk_idx += 1

        doc.close()
        logger.info(f"Extracted {len(extracted_chunks)} chunks across {total_pages} pages for {file_name}")
        return extracted_chunks

    def _chunk_page_blocks(self, blocks: List[str], page_number: int) -> List[str]:
        """
        Group and split blocks on a page to adhere to target_chunk_size
        with overlap where appropriate.
        """
        if not blocks:
            return []

        chunks: List[str] = []
        current_chunk_parts: List[str] = []
        current_len = 0

        for block in blocks:
            block_len = len(block)

            # If a single block is larger than max_chunk_size, split it into smaller pieces
            if block_len > self.max_chunk_size:
                # Flush existing buffer first
                if current_chunk_parts:
                    combined = "\n\n".join(current_chunk_parts).strip()
                    if combined:
                        chunks.append(combined)
                    current_chunk_parts = []
                    current_len = 0

                # Split large block by sentences or word windows
                sub_chunks = self._split_large_text(block)
                chunks.extend(sub_chunks)
                continue

            # If adding this block exceeds target_chunk_size
            if current_len + block_len > self.target_chunk_size and current_chunk_parts:
                combined = "\n\n".join(current_chunk_parts).strip()
                if combined:
                    chunks.append(combined)

                # Overlap: keep the last small part if appropriate
                overlap_text = current_chunk_parts[-1]
                if len(overlap_text) <= self.chunk_overlap * 2:
                    current_chunk_parts = [overlap_text, block]
                    current_len = len(overlap_text) + block_len
                else:
                    current_chunk_parts = [block]
                    current_len = block_len
            else:
                current_chunk_parts.append(block)
                current_len += block_len

        if current_chunk_parts:
            combined = "\n\n".join(current_chunk_parts).strip()
            if combined:
                chunks.append(combined)

        return chunks

    def _split_large_text(self, text: str) -> List[str]:
        """Split a large paragraph into overlapping segments on sentence boundaries."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        result: List[str] = []
        current_sentences: List[str] = []
        current_len = 0

        for s in sentences:
            s_len = len(s)
            if current_len + s_len > self.target_chunk_size and current_sentences:
                chunk_str = " ".join(current_sentences).strip()
                if chunk_str:
                    result.append(chunk_str)

                # Keep last sentence for overlap
                last_s = current_sentences[-1]
                if len(last_s) <= self.chunk_overlap * 2:
                    current_sentences = [last_s, s]
                    current_len = len(last_s) + s_len
                else:
                    current_sentences = [s]
                    current_len = s_len
            else:
                current_sentences.append(s)
                current_len += s_len

        if current_sentences:
            chunk_str = " ".join(current_sentences).strip()
            if chunk_str:
                result.append(chunk_str)

        return result
