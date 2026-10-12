import os
import uuid
import tempfile
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from groq import Groq

from app.core.config import settings
from app.core.logging_config import logger
from app.utils.hashing import generate_chunk_hash
from app.services.ingestion.pdf_processor import ExtractedChunk
from app.services.transcription.audio_utils import (
    is_ffmpeg_available,
    extract_audio_from_video,
    chunk_audio_file,
    get_media_duration_ffprobe
)

class TranscriptionSegment(BaseModel):
    text: str
    start: float
    end: float

class TranscriptionResult(BaseModel):
    segments: List[TranscriptionSegment]
    duration_seconds: float
    full_text: str

def format_timestamp(seconds: float) -> str:
    """Format seconds into HH:MM:SS string."""
    secs_int = max(0, int(round(seconds)))
    hours = secs_int // 3600
    minutes = (secs_int % 3600) // 60
    secs = secs_int % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

class TranscriptionService:
    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        language: Optional[str] = None,
    ):
        self.provider = (provider or settings.TRANSCRIPTION_PROVIDER).lower().strip()
        self.model = model or settings.TRANSCRIPTION_MODEL
        self.api_key = (
            api_key
            or settings.TRANSCRIPTION_API_KEY
            or settings.LLM_API_KEY
            or os.getenv("GROQ_API_KEY")
        )
        self.base_url = base_url or settings.TRANSCRIPTION_BASE_URL
        self.language = language or settings.TRANSCRIPTION_LANGUAGE

        if not self.api_key:
            logger.warning(
                "TRANSCRIPTION_API_KEY or LLM_API_KEY not configured. "
                "Speech-to-text transcription will fail unless mocked in tests."
            )

        # Initialize Groq client
        client_kwargs: Dict[str, Any] = {"api_key": self.api_key or "no-key-set"}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        self.client = Groq(**client_kwargs)

        logger.info(
            f"Initialized TranscriptionService: provider='{self.provider}', "
            f"model='{self.model}', language='{self.language}'"
        )

    def normalize_segments(
        self, raw_segments: List[Any], offset_seconds: float = 0.0
    ) -> List[TranscriptionSegment]:
        """
        Normalize raw speech-to-text segment representations.
        Ensures text is cleaned, timestamps are floats, and offset is applied.
        Safely ignores malformed segments without failing the transcript.
        """
        normalized: List[TranscriptionSegment] = []
        for raw in raw_segments:
            try:
                # Support both dict and object attributes (VerboseTranscription)
                if isinstance(raw, dict):
                    text = str(raw.get("text", "")).strip()
                    start = float(raw.get("start", 0.0))
                    end = float(raw.get("end", start))
                else:
                    text = str(getattr(raw, "text", "")).strip()
                    start = float(getattr(raw, "start", 0.0))
                    end = float(getattr(raw, "end", start))

                if not text:
                    continue

                # Ensure end is at least equal to start
                if end < start:
                    end = start

                normalized.append(
                    TranscriptionSegment(
                        text=text,
                        start=round(start + offset_seconds, 2),
                        end=round(end + offset_seconds, 2)
                    )
                )
            except Exception as seg_err:
                logger.warning(f"Skipping malformed transcription segment ({raw}): {seg_err}")
                continue

        return normalized

    def transcribe_file(self, file_path: str, filename: str) -> TranscriptionResult:
        """
        Transcribe audio/video file.
        - If file size <= TRANSCRIPTION_MAX_FILE_MB: transcribes directly.
        - If file size > TRANSCRIPTION_MAX_FILE_MB: extracts audio and chunks with ffmpeg.
        """
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        max_mb = settings.TRANSCRIPTION_MAX_FILE_MB

        if file_size_mb <= max_mb:
            logger.info(
                f"Transcribing file '{filename}' directly ({file_size_mb:.2f} MB <= {max_mb} MB limit) "
                f"using model '{self.model}'..."
            )
            with open(file_path, "rb") as f:
                response = self.client.audio.transcriptions.create(
                    file=(filename, f),
                    model=self.model,
                    response_format="verbose_json",
                    language=self.language or None,
                    temperature=0.0
                )
            raw_segments = getattr(response, "segments", None)
            if raw_segments is None and isinstance(response, dict):
                raw_segments = response.get("segments", [])
            elif raw_segments is None:
                raw_segments = []

            segments = self.normalize_segments(raw_segments, offset_seconds=0.0)
            duration = getattr(response, "duration", None)
            if duration is None and isinstance(response, dict):
                duration = response.get("duration")
            if duration is None:
                duration = segments[-1].end if segments else 0.0

            full_text = getattr(response, "text", None)
            if full_text is None and isinstance(response, dict):
                full_text = response.get("text", "")
            if not full_text:
                full_text = " ".join(s.text for s in segments)

            return TranscriptionResult(
                segments=segments,
                duration_seconds=float(duration or 0.0),
                full_text=full_text
            )

        # Large file handling
        logger.info(
            f"File '{filename}' ({file_size_mb:.2f} MB) exceeds direct upload limit ({max_mb} MB). "
            f"Extracting and chunking audio..."
        )
        if not is_ffmpeg_available():
            raise RuntimeError(
                f"Video file '{filename}' size ({file_size_mb:.1f} MB) exceeds direct upload limit of "
                f"{max_mb} MB, and ffmpeg is not available on this system to extract and chunk audio. "
                f"Please install ffmpeg or upload a smaller video file."
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            extracted_audio = os.path.join(temp_dir, "extracted_audio.mp3")
            extract_audio_from_video(file_path, extracted_audio)

            chunk_meta = chunk_audio_file(
                audio_path=extracted_audio,
                output_dir=os.path.join(temp_dir, "chunks"),
                chunk_seconds=settings.TRANSCRIPTION_CHUNK_SECONDS,
                overlap_seconds=settings.TRANSCRIPTION_OVERLAP_SECONDS
            )

            all_segments: List[TranscriptionSegment] = []
            seen_texts = set()

            for chunk_path, start_offset, end_offset in chunk_meta:
                logger.info(f"Transcribing audio chunk {start_offset:.1f}s to {end_offset:.1f}s...")
                with open(chunk_path, "rb") as cf:
                    chunk_res = self.client.audio.transcriptions.create(
                        file=(os.path.basename(chunk_path), cf),
                        model=self.model,
                        response_format="verbose_json",
                        language=self.language or None,
                        temperature=0.0
                    )
                raw_segs = getattr(chunk_res, "segments", []) or []
                chunk_segments = self.normalize_segments(raw_segs, offset_seconds=start_offset)

                for seg in chunk_segments:
                    # De-duplicate identical text across overlapping boundaries
                    seg_key = (round(seg.start, 1), seg.text.lower())
                    if seg_key not in seen_texts:
                        seen_texts.add(seg_key)
                        all_segments.append(seg)

            all_segments.sort(key=lambda s: s.start)
            total_dur = all_segments[-1].end if all_segments else 0.0
            full_txt = " ".join(s.text for s in all_segments)

            return TranscriptionResult(
                segments=all_segments,
                duration_seconds=float(total_dur),
                full_text=full_txt
            )

    def combine_segments_into_chunks(
        self,
        segments: List[TranscriptionSegment],
        course_id: str,
        source_id: str,
        file_name: str,
        target_chunk_duration: float = 45.0,
        max_chunk_duration: float = 90.0,
    ) -> List[ExtractedChunk]:
        """
        Combine transcription segments into cohesive, contiguous time-window chunks
        suitable for semantic retrieval and dense embeddings (typically 30-120 seconds).
        """
        if not segments:
            return []

        chunks: List[ExtractedChunk] = []
        global_chunk_idx = 0

        curr_segments: List[TranscriptionSegment] = []
        curr_start = segments[0].start

        for seg in segments:
            curr_segments.append(seg)
            elapsed = seg.end - curr_start

            # When chunk duration exceeds target and has sufficient content, finalize chunk
            combined_len = sum(len(s.text) for s in curr_segments)
            if (elapsed >= target_chunk_duration and combined_len >= 120) or elapsed >= max_chunk_duration:
                chunk_start = curr_segments[0].start
                chunk_end = curr_segments[-1].end
                chunk_text = " ".join(s.text for s in curr_segments)
                content = f"[Video {format_timestamp(chunk_start)}–{format_timestamp(chunk_end)}]\n{chunk_text}"

                c_hash = generate_chunk_hash(
                    course_id=course_id,
                    source_id=source_id,
                    page_number=None,
                    chunk_index=global_chunk_idx,
                    content=content,
                    slide_number=None,
                    start_time_seconds=chunk_start,
                    end_time_seconds=chunk_end
                )

                chunks.append(
                    ExtractedChunk(
                        chunk_id=str(uuid.uuid4()),
                        course_id=course_id,
                        source_id=source_id,
                        file_name=file_name,
                        page_number=None,
                        chunk_index=global_chunk_idx,
                        content=content,
                        content_hash=c_hash,
                        slide_number=None,
                        start_time_seconds=chunk_start,
                        end_time_seconds=chunk_end,
                        modality="video_transcript",
                        visual_description=None
                    )
                )
                global_chunk_idx += 1
                curr_segments = []
                curr_start = seg.end

        # Finalize trailing segment group
        if curr_segments:
            chunk_start = curr_segments[0].start
            chunk_end = curr_segments[-1].end
            chunk_text = " ".join(s.text for s in curr_segments)
            content = f"[Video {format_timestamp(chunk_start)}–{format_timestamp(chunk_end)}]\n{chunk_text}"

            c_hash = generate_chunk_hash(
                course_id=course_id,
                source_id=source_id,
                page_number=None,
                chunk_index=global_chunk_idx,
                content=content,
                slide_number=None,
                start_time_seconds=chunk_start,
                end_time_seconds=chunk_end
            )

            chunks.append(
                ExtractedChunk(
                    chunk_id=str(uuid.uuid4()),
                    course_id=course_id,
                    source_id=source_id,
                    file_name=file_name,
                    page_number=None,
                    chunk_index=global_chunk_idx,
                    content=content,
                    content_hash=c_hash,
                    slide_number=None,
                    start_time_seconds=chunk_start,
                    end_time_seconds=chunk_end,
                    modality="video_transcript",
                    visual_description=None
                )
            )

        return chunks

_transcription_service: Optional[TranscriptionService] = None

def get_transcription_service() -> TranscriptionService:
    global _transcription_service
    if _transcription_service is None:
        _transcription_service = TranscriptionService()
    return _transcription_service
