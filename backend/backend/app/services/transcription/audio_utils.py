import os
import shutil
import subprocess
from typing import List, Tuple, Optional
from app.core.logging_config import logger

def get_ffmpeg_exe() -> Optional[str]:
    """Get the path to the ffmpeg executable from PATH or imageio_ffmpeg."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None

def is_ffmpeg_available() -> bool:
    """Check if ffmpeg executable is available in PATH or imageio_ffmpeg."""
    return get_ffmpeg_exe() is not None

def extract_audio_from_video(video_path: str, output_audio_path: str) -> None:
    """
    Extract audio track from video file using ffmpeg.
    Converts to 128k MP3 for compact speech transcription.
    """
    ffmpeg_exe = get_ffmpeg_exe()
    if not ffmpeg_exe:
        raise RuntimeError(
            "ffmpeg is required for audio extraction from large video files, but it was not found in PATH."
        )

    cmd = [
        ffmpeg_exe,
        "-y",               # Overwrite without asking
        "-i", video_path,   # Input file
        "-vn",              # Disable video recording
        "-acodec", "libmp3lame",
        "-ar", "16000",     # 16kHz sample rate optimal for Whisper
        "-ac", "1",         # Mono channel
        "-b:a", "64k",      # 64kbps bitrate
        output_audio_path
    ]
    logger.info(f"Extracting audio using ffmpeg: {' '.join(cmd)}")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio extraction failed: {result.stderr}")

def chunk_audio_file(
    audio_path: str,
    output_dir: str,
    chunk_seconds: int = 600,
    overlap_seconds: int = 5,
    total_duration: Optional[float] = None
) -> List[Tuple[str, float, float]]:
    """
    Split audio into overlapping segments of duration `chunk_seconds`.
    Returns list of tuples: (chunk_file_path, start_seconds, end_seconds).
    """
    ffmpeg_exe = get_ffmpeg_exe()
    if not ffmpeg_exe:
        raise RuntimeError(
            "ffmpeg is required for chunking long audio files, but it was not found in PATH."
        )

    os.makedirs(output_dir, exist_ok=True)
    chunks_meta: List[Tuple[str, float, float]] = []

    # If duration is unknown, inspect with ffprobe
    if total_duration is None:
        total_duration = get_media_duration_ffprobe(audio_path) or 3600.0

    start = 0.0
    chunk_idx = 0
    while start < total_duration:
        end = min(start + chunk_seconds, total_duration)
        duration = end - start
        chunk_file = os.path.join(output_dir, f"audio_chunk_{chunk_idx:04d}.mp3")

        cmd = [
            ffmpeg_exe,
            "-y",
            "-ss", str(start),
            "-t", str(duration),
            "-i", audio_path,
            "-acodec", "copy",
            chunk_file
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"ffmpeg audio segment split failed at {start}s: {res.stderr}")

        chunks_meta.append((chunk_file, start, end))
        chunk_idx += 1

        if end >= total_duration:
            break
        start += (chunk_seconds - overlap_seconds)

    return chunks_meta

def get_media_duration_ffprobe(file_path: str) -> Optional[float]:
    """Inspect media duration in seconds using ffprobe."""
    if shutil.which("ffprobe") is None:
        return None

    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return float(res.stdout.strip())
    except Exception as e:
        logger.warning(f"Could not read duration with ffprobe: {e}")
    return None
