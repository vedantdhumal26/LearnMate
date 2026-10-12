import hashlib

def compute_content_hash(text: str) -> str:
    """Compute deterministic SHA256 hex digest for chunk content."""
    normalized = " ".join(text.strip().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def generate_chunk_hash(
    course_id: str,
    source_id: str,
    page_number: int = None,
    chunk_index: int = 0,
    content: str = "",
    slide_number: int = None,
    start_time_seconds: float = None,
    end_time_seconds: float = None,
) -> str:
    """
    Generate unique deterministic hash for a specific chunk location and content.
    Backward-compatible with PDF page_number, PPTX slide_number, and video timestamps.
    """
    if slide_number is not None:
        loc = f"slide:{slide_number}"
    elif start_time_seconds is not None:
        loc = f"time:{start_time_seconds:.2f}-{end_time_seconds:.2f}"
    else:
        loc = f"page:{page_number}"
    composite = f"{course_id}:{source_id}:{loc}:{chunk_index}:{content.strip()}"
    return hashlib.sha256(composite.encode("utf-8")).hexdigest()
