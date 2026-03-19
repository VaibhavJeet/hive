"""
FastAPI dependencies for authentication, authorization, and dependency injection.

Provides:
- Authentication dependencies (get_current_user, get_optional_user)
- Database session injection (get_db_session)
- LLM client injection (get_llm_client)
- Cache injection (get_cache)
- Activity engine injection (get_activity_engine)
"""

import logging
from typing import AsyncGenerator, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.auth import verify_access_token, AuthenticatedUser
from mind.core.database import async_session_factory, AppUserDB
from mind.core.dependencies import (
    get_db_provider,
    get_llm_provider,
    get_cache_provider,
    get_memory_provider,
    get_activity_provider,
)

logger = logging.getLogger(__name__)

# HTTP Bearer scheme for extracting tokens from Authorization header
security = HTTPBearer(auto_error=False)


# ============================================================================
# DATABASE SESSION DEPENDENCY
# ============================================================================

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Request-scoped database session dependency.

    Usage in routes:
        @router.get("/items")
        async def get_items(session: AsyncSession = Depends(get_db_session)):
            result = await session.execute(select(ItemDB))
            return result.scalars().all()
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            raise
        finally:
            await session.close()


# ============================================================================
# LLM CLIENT DEPENDENCY
# ============================================================================

async def get_llm_client():
    """
    Singleton LLM client dependency.

    Usage in routes:
        @router.post("/generate")
        async def generate(llm = Depends(get_llm_client)):
            response = await llm.generate(request)
            return response
    """
    provider = get_llm_provider()
    return await provider.get_cached_client()


# ============================================================================
# CACHE DEPENDENCY
# ============================================================================

async def get_cache():
    """
    Singleton cache service dependency.

    Usage in routes:
        @router.get("/cached-data")
        async def get_cached(cache = Depends(get_cache)):
            data = await cache.get("key")
            return data
    """
    provider = get_cache_provider()
    return await provider.get_cache()


# ============================================================================
# MEMORY DEPENDENCY
# ============================================================================

async def get_memory():
    """
    Singleton memory core dependency.

    Usage in routes:
        @router.get("/bot/{bot_id}/memories")
        async def get_memories(memory = Depends(get_memory)):
            memories = await memory.recall(bot_id, query)
            return memories
    """
    provider = get_memory_provider()
    return await provider.get_memory_core()


async def get_relationship_memory():
    """
    Singleton relationship memory dependency.
    """
    provider = get_memory_provider()
    return await provider.get_relationship_memory()


# ============================================================================
# ACTIVITY ENGINE DEPENDENCY
# ============================================================================

async def get_activity_engine():
    """
    Singleton activity engine dependency.

    Usage in routes:
        @router.post("/bot/{bot_id}/action")
        async def trigger_action(engine = Depends(get_activity_engine)):
            await engine.queue_response(bot_id, message)
            return {"status": "queued"}
    """
    provider = get_activity_provider()
    return await provider.get_engine()


# ============================================================================
# AUTHENTICATION DEPENDENCIES
# ============================================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_db_session)
) -> AuthenticatedUser:
    """
    Dependency to get the current authenticated user.

    Extracts the JWT token from the Authorization header,
    validates it, and returns the user.

    Raises:
        HTTPException 401: If token is missing, invalid, or user not found
    """
    # Check if credentials were provided
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify the token
    token_data = verify_access_token(credentials.credentials)

    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database using injected session
    stmt = select(AppUserDB).where(AppUserDB.id == token_data.user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if hasattr(user, 'is_active') and not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthenticatedUser(
        id=user.id,
        email=user.email if hasattr(user, 'email') else "",
        display_name=user.display_name,
        avatar_seed=user.avatar_seed,
        created_at=user.created_at,
        is_active=getattr(user, 'is_active', True)
    )


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[AuthenticatedUser]:
    """
    Dependency to optionally get the current user.

    Works for routes that support both authenticated and unauthenticated access.

    Returns:
        AuthenticatedUser if valid token provided, None otherwise
    """
    if credentials is None:
        return None

    # Try to verify the token
    token_data = verify_access_token(credentials.credentials)

    if token_data is None:
        return None

    # Get user from database
    async with async_session_factory() as session:
        stmt = select(AppUserDB).where(AppUserDB.id == token_data.user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            return None

        # Check if user is active
        if hasattr(user, 'is_active') and not user.is_active:
            return None

        return AuthenticatedUser(
            id=user.id,
            email=user.email if hasattr(user, 'email') else "",
            display_name=user.display_name,
            avatar_seed=user.avatar_seed,
            created_at=user.created_at,
            is_active=getattr(user, 'is_active', True)
        )


async def get_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UUID:
    """
    Dependency to get just the user ID from the token.

    Lighter weight than get_current_user - doesn't fetch user from DB.

    Raises:
        HTTPException 401: If token is missing or invalid
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = verify_access_token(credentials.credentials)

    if token_data is None or token_data.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_data.user_id


# ============================================================================
# COMPOSITE DEPENDENCIES
# ============================================================================

class RequestContext:
    """
    Composite dependency that bundles common request dependencies.

    Usage:
        @router.get("/items")
        async def get_items(ctx: RequestContext = Depends(get_request_context)):
            async with ctx.session:
                result = await ctx.session.execute(...)
    """

    def __init__(
        self,
        session: AsyncSession,
        user: Optional[AuthenticatedUser] = None,
    ):
        self.session = session
        self.user = user


async def get_request_context(
    session: AsyncSession = Depends(get_db_session),
    user: Optional[AuthenticatedUser] = Depends(get_optional_user)
) -> RequestContext:
    """Get a request context with session and optional user."""
    return RequestContext(session=session, user=user)


async def get_authenticated_context(
    session: AsyncSession = Depends(get_db_session),
    user: AuthenticatedUser = Depends(get_current_user)
) -> RequestContext:
    """Get a request context requiring authentication."""
    return RequestContext(session=session, user=user)
