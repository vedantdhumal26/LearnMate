"""
JWT token creation and decoding utilities.
Phase 6A: Real User Authentication.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import jwt
from fastapi import HTTPException, status
from app.core.config import settings
from app.core.logging_config import logger


def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Generate a signed JWT access token containing 'sub' and 'exp'.
    Never logs secrets or generated tokens.
    """
    if not user_id:
        raise ValueError("user_id is required to create an access token")

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }

    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    return token


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT access token.
    Rejects:
    - invalid signature
    - expired token
    - malformed token
    - missing sub

    Raises HTTPException 401 on validation failure.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    expired_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token has expired",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token or not isinstance(token, str):
        raise credentials_exception

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.ExpiredSignatureError:
        raise expired_exception
    except (jwt.InvalidSignatureError, jwt.DecodeError, jwt.InvalidTokenError):
        raise credentials_exception
    except Exception as e:
        logger.warning(f"Unexpected error decoding token: {type(e).__name__}")
        raise credentials_exception

    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        raise credentials_exception

    return payload
