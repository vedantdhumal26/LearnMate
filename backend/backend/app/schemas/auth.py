"""
Authentication schemas for Signup, Login, and User Identity.
Phase 6A: Real User Authentication.
"""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SignupRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255, description="User email address")
    password: str = Field(..., min_length=6, max_length=128, description="User password")
    display_name: str = Field(..., min_length=1, max_length=255, description="User display name")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Email cannot be blank")
        clean = v.strip().lower()
        if "@" not in clean or "." not in clean:
            raise ValueError("Invalid email format")
        return clean

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Display name cannot be blank")
        return v.strip()


class LoginRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Email cannot be blank")
        return v.strip().lower()


class UserResponse(BaseModel):
    id: str = Field(..., description="Unique user identifier")
    email: str = Field(..., description="User email address")
    display_name: str = Field(..., description="User display name")

    model_config = ConfigDict(from_attributes=True)


class AuthResponse(BaseModel):
    user: UserResponse = Field(..., description="Authenticated user profile")
    access_token: str = Field(..., description="Signed JWT access token")
    token_type: str = Field(default="bearer", description="Token type")

    model_config = ConfigDict(from_attributes=True)


class UserUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=255, description="Updated user display name")
    email: Optional[str] = Field(default=None, min_length=3, max_length=255, description="Updated user email address")

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            if not clean:
                raise ValueError("Display name cannot be blank")
            return clean
        return None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip().lower()
            if not clean:
                raise ValueError("Email cannot be blank")
            if "@" not in clean or "." not in clean:
                raise ValueError("Invalid email format")
            return clean
        return None
