"""
Safe observability for LLM requests (Milestone: Groq 429 & Quota Contention).
Logs structured metrics without exposing sensitive user prompts, headers, or API keys.
"""

from datetime import datetime, timezone
from typing import Optional
from app.core.logging_config import logger


def estimate_tokens(text: Optional[str]) -> int:
    """Fast, safe estimate of token count based on whitespace and character heuristics."""
    if not text:
        return 0
    # Rule of thumb for English/code: ~1.3 tokens per whitespace word or len(text)/4
    words = len(text.split())
    chars = len(text)
    return max(1, int(max(words * 1.3, chars / 4.0)))


def log_llm_request_metric(
    request_type: str,
    model: str,
    start_time: float,
    duration: float,
    status_str: str,
    input_tokens: int,
    output_tokens: int,
    retry_count: int = 0,
    error_msg: Optional[str] = None
) -> None:
    """
    Log safe structured LLM invocation metrics.
    Never logs authorization headers, API keys, or raw prompt bodies.
    """
    start_iso = datetime.fromtimestamp(start_time, timezone.utc).isoformat()
    log_msg = (
        f"[LLM_METRIC] request_type='{request_type}' model='{model}' "
        f"status='{status_str}' duration={duration:.3f}s "
        f"in_tokens={input_tokens} out_tokens={output_tokens} retries={retry_count} "
        f"timestamp='{start_iso}'"
    )
    if error_msg:
        # Sanitize any potential keys from error message
        sanitized_err = error_msg.replace("gsk_", "gsk_***")
        log_msg += f" error='{sanitized_err}'"

    if status_str == "success":
        logger.info(log_msg)
    elif status_str in ("429", "timeout"):
        logger.warning(log_msg)
    else:
        logger.error(log_msg)
