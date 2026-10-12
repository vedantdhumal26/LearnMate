"""
Authentication API endpoints: signup, login, and profile.
Phase 6A: Real User Authentication.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth import get_current_user
from app.core.jwt import create_access_token
from app.utils.password import hash_password, verify_password
from app.models.user import User
from app.schemas.auth import SignupRequest, LoginRequest, UserResponse, AuthResponse, UserUpdateRequest

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(
    payload: SignupRequest,
    db: Session = Depends(get_db)
):
    """
    Sign up a new user.
    - Validates input
    - Normalizes lowercase email
    - Rejects duplicate email (HTTP 400)
    - Hashes password using Argon2id
    - Creates user
    - Returns signed JWT access token and user profile
    """
    normalized_email = payload.email.strip().lower()

    existing_user = db.query(User).filter(User.email == normalized_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered."
        )

    # Hash password with Argon2id (never logged or exposed)
    pw_hash = hash_password(payload.password)

    user = User(
        email=normalized_email,
        password_hash=pw_hash,
        display_name=payload.display_name.strip()
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user_id=user.id)

    return AuthResponse(
        user=UserResponse(
            id=user.id,
            email=user.email,
            display_name=user.display_name
        ),
        access_token=token,
        token_type="bearer"
    )


@router.post("/login", response_model=AuthResponse, status_code=status.HTTP_200_OK)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate a user.
    - Normalizes email
    - Verifies password using Argon2id
    - Returns generic error 'Invalid email or password.' on failure (never reveals existence)
    - Returns signed JWT access token on success
    """
    generic_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    normalized_email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()
    if not user:
        # Avoid timing attacks: dummy verification can be used or constant time
        raise generic_error

    if not verify_password(payload.password, user.password_hash):
        raise generic_error

    token = create_access_token(user_id=user.id)

    return AuthResponse(
        user=UserResponse(
            id=user.id,
            email=user.email,
            display_name=user.display_name
        ),
        access_token=token,
        token_type="bearer"
    )


@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
def get_me(
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve profile of the currently authenticated user.
    Requires Authorization: Bearer <token>
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name
    )


@router.patch("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
def update_me(
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update permitted profile fields (display_name, email) for the authenticated user.
    - Identity is derived strictly from the JWT session.
    - Rejects empty display name or invalid email format.
    - Rejects requests containing no permitted updates.
    - Ensures email uniqueness if email is changed.
    - Does not permit modifying user ID, password hash, role, or ownership.
    """
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data or all(v is None for v in update_data.values()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid profile fields provided for update."
        )

    if "display_name" in update_data and update_data["display_name"] is not None:
        current_user.display_name = update_data["display_name"]

    if "email" in update_data and update_data["email"] is not None:
        new_email = update_data["email"]
        if new_email != current_user.email:
            existing_user = db.query(User).filter(User.email == new_email, User.id != current_user.id).first()
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email is already registered."
                )
            current_user.email = new_email

    db.commit()
    db.refresh(current_user)

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name
    )
