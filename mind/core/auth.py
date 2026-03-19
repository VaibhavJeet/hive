"""
JWT Authentication for AI Community Companions.
Handles token creation, verification, password hashing, and user authentication.
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field

from mind.config.settings import settings


# ============================================================================
# PASSWORD HASHING
# ============================================================================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ============================================================================
# TOKEN MODELS
# ============================================================================

class TokenPayload(BaseModel):
    """JWT Token payload structure."""
    user_id: str
    exp: datetime
    iat: datetime
    token_type: str = "access"  # "access" or "refresh"


class TokenPair(BaseModel):
    """Access and refresh token pair."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token expiration in seconds")


class TokenData(BaseModel):
    """Decoded token data."""
    user_id: Optional[UUID] = None
    token_type: str = "access"


# ============================================================================
# TOKEN CREATION
# ============================================================================

def create_access_token(user_id: UUID) -> str:
    """
    Create a JWT access token for a user.

    Args:
        user_id: The user's UUID

    Returns:
        Encoded JWT access token
    """
    now = datetime.utcnow()
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "user_id": str(user_id),
        "exp": expire,
        "iat": now,
        "token_type": "access"
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def create_refresh_token(user_id: UUID) -> str:
    """
    Create a JWT refresh token for a user.

    Args:
        user_id: The user's UUID

    Returns:
        Encoded JWT refresh token
    """
    now = datetime.utcnow()
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        "user_id": str(user_id),
        "exp": expire,
        "iat": now,
        "token_type": "refresh"
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def create_token_pair(user_id: UUID) -> TokenPair:
    """
    Create both access and refresh tokens for a user.

    Args:
        user_id: The user's UUID

    Returns:
        TokenPair with access and refresh tokens
    """
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


# ============================================================================
# TOKEN VERIFICATION
# ============================================================================

def decode_token(token: str) -> Optional[TokenData]:
    """
    Decode and verify a JWT token.

    Args:
        token: The JWT token to decode

    Returns:
        TokenData if valid, None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )

        user_id = payload.get("user_id")
        token_type = payload.get("token_type", "access")

        if user_id is None:
            return None

        return TokenData(
            user_id=UUID(user_id),
            token_type=token_type
        )

    except JWTError:
        return None


def verify_access_token(token: str) -> Optional[TokenData]:
    """
    Verify an access token and return its data.

    Args:
        token: The JWT access token

    Returns:
        TokenData if valid access token, None otherwise
    """
    token_data = decode_token(token)

    if token_data is None:
        return None

    if token_data.token_type != "access":
        return None

    return token_data


def verify_refresh_token(token: str) -> Optional[TokenData]:
    """
    Verify a refresh token and return its data.

    Args:
        token: The JWT refresh token

    Returns:
        TokenData if valid refresh token, None otherwise
    """
    token_data = decode_token(token)

    if token_data is None:
        return None

    if token_data.token_type != "refresh":
        return None

    return token_data


# ============================================================================
# USER AUTHENTICATION HELPERS
# ============================================================================

class AuthenticatedUser(BaseModel):
    """Represents an authenticated user from a valid token."""
    id: UUID
    email: str
    display_name: str
    avatar_seed: str
    created_at: datetime
    is_active: bool = True
