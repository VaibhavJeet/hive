"""
Authentication API routes - User registration, login, token refresh, and logout.
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select

from mind.config.settings import settings
from mind.core.database import async_session_factory, AppUserDB, RefreshTokenDB
from mind.core.auth import (
    hash_password,
    verify_password,
    create_token_pair,
    verify_refresh_token,
    create_access_token,
    TokenPair,
    AuthenticatedUser
)
from mind.api.dependencies import get_current_user
from mind.core.errors import (
    AuthenticationError,
    ConflictError,
    DatabaseError,
    ErrorCode
)
from mind.core.decorators import handle_errors


router = APIRouter(prefix="/auth", tags=["auth"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class RegisterRequest(BaseModel):
    """User registration request."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email": "newuser@example.com",
                    "password": "securePassword8",
                    "display_name": "Alex",
                }
            ]
        }
    )

    email: EmailStr
    password: str = Field(min_length=8, description="Password must be at least 8 characters")
    display_name: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    """User login request."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"email": "alex@example.com", "password": "securePassword8"}
            ]
        }
    )

    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Token refresh request."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                }
            ]
        }
    )

    refresh_token: str


class LogoutRequest(BaseModel):
    """Logout request."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                }
            ]
        }
    )

    refresh_token: str


class AuthResponse(BaseModel):
    """Authentication response with tokens and user info."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "bearer",
                    "expires_in": 1800,
                    "user": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "email": "alex@example.com",
                        "display_name": "Alex",
                        "avatar_seed": "seed-abc",
                        "created_at": "2026-03-01T12:00:00",
                    },
                }
            ]
        }
    )

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class UserInfoResponse(BaseModel):
    """Current user info response."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "email": "alex@example.com",
                    "display_name": "Alex",
                    "avatar_seed": "seed-abc",
                    "created_at": "2026-03-01T12:00:00",
                    "is_active": True,
                }
            ]
        }
    )

    id: UUID
    email: str
    display_name: str
    avatar_seed: str
    created_at: datetime
    is_active: bool


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str


class ErrorResponse(BaseModel):
    """Standard error response payload."""
    detail: str


# ============================================================================
# AUTH ENDPOINTS
# ============================================================================

@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
    description=(
        "Creates a user and returns **access_token** and **refresh_token**. "
        "Use **Authorize** in Swagger with the access token for protected routes."
    ),
    responses={
        409: {"model": ErrorResponse, "description": "Email already registered"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
@handle_errors(default_error=DatabaseError)
async def register(request: RegisterRequest):
    """
    Register a new user account.

    Creates a new user with hashed password and returns access + refresh tokens.
    """
    async with async_session_factory() as session:
        # Check if email already exists
        stmt = select(AppUserDB).where(AppUserDB.email == request.email)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            raise ConflictError(
                message="Email already registered",
                resource_type="User",
                conflicting_field="email"
            )

        # Create new user with hashed password
        user = AppUserDB(
            email=request.email,
            password_hash=hash_password(request.password),
            display_name=request.display_name,
            avatar_seed=str(uuid4()),
            device_id=str(uuid4()),  # Generate a device_id for compatibility
            is_active=True
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # Create token pair
        tokens = create_token_pair(user.id)

        # Store refresh token in database
        refresh_token_record = RefreshTokenDB(
            user_id=user.id,
            token_hash=hash_password(tokens.refresh_token),
            expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        session.add(refresh_token_record)
        await session.commit()

        return AuthResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
            expires_in=tokens.expires_in,
            user={
                "id": str(user.id),
                "email": user.email,
                "display_name": user.display_name,
                "avatar_seed": user.avatar_seed,
                "created_at": user.created_at.isoformat()
            }
        )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Login",
    description="Returns JWT **access_token** and **refresh_token** for the given email and password.",
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        403: {"model": ErrorResponse, "description": "Account is disabled"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
@handle_errors(default_error=DatabaseError)
async def login(request: LoginRequest):
    """
    Login with email and password.

    Returns access + refresh tokens on successful authentication.
    """
    async with async_session_factory() as session:
        # Find user by email
        stmt = select(AppUserDB).where(AppUserDB.email == request.email)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            raise AuthenticationError(
                message="Invalid email or password",
                error_code=ErrorCode.INVALID_CREDENTIALS
            )

        # Verify password
        if not hasattr(user, 'password_hash') or user.password_hash is None:
            raise AuthenticationError(
                message="Invalid email or password",
                error_code=ErrorCode.INVALID_CREDENTIALS
            )

        if not verify_password(request.password, user.password_hash):
            raise AuthenticationError(
                message="Invalid email or password",
                error_code=ErrorCode.INVALID_CREDENTIALS
            )

        # Check if user is active
        if hasattr(user, 'is_active') and not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled"
            )

        # Create token pair
        tokens = create_token_pair(user.id)

        # Store refresh token in database
        refresh_token_record = RefreshTokenDB(
            user_id=user.id,
            token_hash=hash_password(tokens.refresh_token),
            expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        session.add(refresh_token_record)

        # Update last active
        user.last_active = datetime.utcnow()
        await session.commit()

        return AuthResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
            expires_in=tokens.expires_in,
            user={
                "id": str(user.id),
                "email": user.email if hasattr(user, 'email') else "",
                "display_name": user.display_name,
                "avatar_seed": user.avatar_seed,
                "created_at": user.created_at.isoformat()
            }
        )


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Refresh access token",
    description="Exchange a valid **refresh_token** for a new **access_token**.",
    responses={
        401: {"model": ErrorResponse, "description": "Invalid, expired, or revoked refresh token"},
        403: {"model": ErrorResponse, "description": "Account is disabled"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
@handle_errors(default_error=DatabaseError)
async def refresh_token(request: RefreshRequest):
    """
    Refresh an access token using a valid refresh token.

    Returns a new access token. The refresh token remains valid until expiration.
    """
    # Verify the refresh token
    token_data = verify_refresh_token(request.refresh_token)

    if token_data is None or token_data.user_id is None:
        raise AuthenticationError(
            message="Invalid or expired refresh token",
            error_code=ErrorCode.TOKEN_INVALID
        )

    async with async_session_factory() as session:
        # Check if refresh token is blacklisted
        stmt = select(RefreshTokenDB).where(
            RefreshTokenDB.user_id == token_data.user_id,
            RefreshTokenDB.is_revoked == True
        )
        result = await session.execute(stmt)
        revoked_tokens = result.scalars().all()

        # Check if this specific token was revoked (by comparing hashes)
        for revoked in revoked_tokens:
            if verify_password(request.refresh_token, revoked.token_hash):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token has been revoked"
                )

        # Verify user exists and is active
        user_stmt = select(AppUserDB).where(AppUserDB.id == token_data.user_id)
        user_result = await session.execute(user_stmt)
        user = user_result.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        if hasattr(user, 'is_active') and not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled"
            )

        # Create new access token
        new_access_token = create_access_token(token_data.user_id)

        return TokenPair(
            access_token=new_access_token,
            refresh_token=request.refresh_token,  # Return same refresh token
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout",
    description="Revokes the given **refresh_token** so it cannot be used again.",
    responses={422: {"model": ErrorResponse, "description": "Validation error"}},
)
@handle_errors(default_error=DatabaseError)
async def logout(request: LogoutRequest):
    """
    Logout by invalidating the refresh token.

    The refresh token will be blacklisted and cannot be used again.
    """
    # Verify the refresh token
    token_data = verify_refresh_token(request.refresh_token)

    if token_data is None or token_data.user_id is None:
        # Even if token is invalid, return success (idempotent logout)
        return MessageResponse(message="Logged out successfully")

    async with async_session_factory() as session:
        # Find and revoke the refresh token
        stmt = select(RefreshTokenDB).where(
            RefreshTokenDB.user_id == token_data.user_id,
            RefreshTokenDB.is_revoked == False
        )
        result = await session.execute(stmt)
        tokens = result.scalars().all()

        # Revoke matching token
        for token in tokens:
            if verify_password(request.refresh_token, token.token_hash):
                token.is_revoked = True
                token.revoked_at = datetime.utcnow()
                break

        await session.commit()

    return MessageResponse(message="Logged out successfully")


@router.get(
    "/me",
    response_model=UserInfoResponse,
    summary="Current user profile",
    description=(
        "Returns the authenticated app user. Requires **JWT Bearer** "
        "(use **Authorize** with `access_token` from login/register)."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Missing/invalid/expired access token"},
    },
)
@handle_errors(default_error=DatabaseError)
async def get_current_user_info(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Get the current authenticated user's information.

    Requires a valid access token in the Authorization header.
    """
    return UserInfoResponse(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        avatar_seed=current_user.avatar_seed,
        created_at=current_user.created_at,
        is_active=current_user.is_active
    )
