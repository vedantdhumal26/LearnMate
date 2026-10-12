import os
import hashlib
from fastapi import UploadFile, HTTPException, status
from app.core.logging_config import logger

def ensure_directory(path: str) -> None:
    """Ensure directory exists on disk."""
    os.makedirs(path, exist_ok=True)

def compute_file_sha256(file_path: str) -> str:
    """Compute SHA256 checksum of a file on disk."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()

async def validate_pdf_upload(file: UploadFile, max_size_mb: int = 50) -> bytes:
    """
    Validate uploaded file:
    - filename extension (.pdf)
    - content_type (application/pdf)
    - not empty
    - size limit
    Returns file contents in bytes.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file extension. Only .pdf files are supported."
        )

    # Check content type if provided
    content_type = file.content_type or ""
    if content_type and content_type not in ["application/pdf", "application/x-pdf", "application/octet-stream"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid MIME type '{content_type}'. Must be application/pdf."
        )

    # Read and check size
    contents = await file.read()
    file_size = len(contents)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded PDF file is empty."
        )

    max_bytes = max_size_mb * 1024 * 1024
    if file_size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {max_size_mb} MB."
        )

    # Validate PDF signature (magic bytes: %PDF-)
    if not contents.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid PDF structure. File does not contain standard PDF header (%PDF-)."
        )

    # Reset file pointer for any further operations
    await file.seek(0)
    return contents

async def validate_pptx_upload(file: UploadFile, max_size_mb: int = 50) -> bytes:
    """
    Validate uploaded PPTX file:
    - filename extension (.pptx)
    - explicitly reject .ppt with 'Only .pptx slide decks are supported in Phase 4A.'
    - not empty
    - size limit
    - ZIP magic bytes check (PK\x03\x04)
    Returns file contents in bytes.
    """
    filename = (file.filename or "").lower().strip()
    if filename.endswith(".ppt"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .pptx slide decks are supported in Phase 4A."
        )

    if not filename.endswith(".pptx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file extension. Only .pptx slide decks are supported."
        )

    contents = await file.read()
    file_size = len(contents)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded PPTX file is empty."
        )

    max_bytes = max_size_mb * 1024 * 1024
    if file_size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {max_size_mb} MB."
        )

    # Validate ZIP / OpenXML presentation signature (magic bytes: PK\x03\x04 or PK)
    if not contents.startswith(b"PK\x03\x04") and not contents.startswith(b"PK"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid PPTX structure. File is not a valid presentation package."
        )

    await file.seek(0)
    return contents

async def validate_mp4_upload(file: UploadFile, max_size_mb: int = 50) -> bytes:
    """
    Validate uploaded MP4 video file:
    - filename extension (.mp4)
    - reject other video formats with 'Only .mp4 video files are supported in Phase 4B.'
    - not empty
    - size limit
    - ISO Base Media File Format signature check (ftyp box in first 32 bytes)
    Returns file contents in bytes.
    """
    filename = (file.filename or "").lower().strip()
    video_exts = (".avi", ".mkv", ".mov", ".webm", ".flv", ".wmv", ".m4v", ".3gp", ".mpeg", ".mpg")
    if any(filename.endswith(ext) for ext in video_exts):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .mp4 video files are supported in Phase 4B."
        )

    if not filename.endswith(".mp4"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file extension. Only .mp4 video files are supported."
        )

    contents = await file.read()
    file_size = len(contents)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded MP4 file is empty."
        )

    max_bytes = max_size_mb * 1024 * 1024
    if file_size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {max_size_mb} MB."
        )

    # Validate MP4 / ISO container box (ftyp or moov or valid container structure)
    if len(contents) < 8 or (b"ftyp" not in contents[:32] and contents[4:8] not in [b"moov", b"mdat"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MP4 structure. File is not a valid MP4 video container."
        )

    await file.seek(0)
    return contents

async def validate_course_upload(file: UploadFile, max_size_mb: int = 50):
    """
    Inspects filename extension and delegates to validate_pdf_upload, validate_pptx_upload, or validate_mp4_upload.
    Returns:
        (file_bytes, file_type, source_type)
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
        data = await validate_mp4_upload(file, max_size_mb=max_size_mb)
        return data, "video/mp4", "video"
    elif filename.endswith(".pptx"):
        data = await validate_pptx_upload(file, max_size_mb=max_size_mb)
        return data, "application/vnd.openxmlformats-officedocument.presentationml.presentation", "pptx"
    elif filename.endswith(".pdf"):
        data = await validate_pdf_upload(file, max_size_mb=max_size_mb)
        return data, "application/pdf", "pdf"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Only .pdf files are supported (or .pptx, .mp4 in Phase 4)."
        )
