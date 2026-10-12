import re
from typing import List

def clean_extracted_text(text: str) -> str:
    """
    Clean extracted raw text from PDF:
    - Remove NULL bytes and non-printable control characters
    - Fix hyphenation at line breaks (e.g. 'auto-\nmatic' -> 'automatic')
    - Normalize excessive whitespace while preserving paragraph breaks
    """
    if not text:
        return ""

    # Remove null bytes and non-printable characters (except newline, tab)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)

    # Fix line-broken hyphenated words
    cleaned = re.sub(r"(\w+)-\n(\w+)", r"\1\2", cleaned)

    # Normalize carriage returns
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")

    # Replace runs of spaces/tabs with single space
    cleaned = re.sub(r"[ \t]+", " ", cleaned)

    # Collapse more than two consecutive newlines into two (paragraph break)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    # Strip leading/trailing whitespace
    return cleaned.strip()

def is_heading(line: str) -> bool:
    """
    Heuristic check to determine if a given line is likely a section heading.
    Criteria:
    - Relatively short (<= 80 chars)
    - Does not end with standard sentence punctuation (period, colon, semicolon)
    - Starts with a capital letter or number (e.g. '1. Introduction', 'Chapter 2', 'Newton's Laws')
    """
    trimmed = line.strip()
    if not trimmed or len(trimmed) > 80:
        return False

    # Avoid bullet points
    if trimmed.startswith(("-", "*", "•", "–")):
        return False

    # Check ending
    if trimmed.endswith((".", ";", ",")):
        return False

    # All caps or Title Case pattern or numbered section
    if trimmed.isupper() and len(trimmed) > 3:
        return True

    numbered_pattern = r"^(\d+(\.\d+)*|[A-Z](\.\d+)*)\s+[A-Za-z]"
    if re.match(numbered_pattern, trimmed):
        return True

    # Title case with 2 to 7 words
    words = trimmed.split()
    if 1 <= len(words) <= 7 and all(w[0].isupper() for w in words if w.isalpha()):
        return True

    return False
