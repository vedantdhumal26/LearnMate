"""
Password hashing and verification utility using Argon2id.
Phase 6A: Real User Authentication.
"""

from typing import Optional
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from app.core.logging_config import logger

# Initialize Argon2id password hasher with secure parameters
_ph = PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=1,
    hash_len=32,
)


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using Argon2id.
    Never logs plaintext passwords or resulting hashes.
    """
    if not password:
        raise ValueError("Password cannot be empty")
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a plaintext password against an Argon2id hash using constant-time comparison.
    Never logs passwords or hashes.
    """
    if not password or not password_hash:
        return False
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    except Exception as e:
        logger.error("Unexpected error during password verification", exc_info=False)
        return False
