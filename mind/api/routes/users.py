"""
User API routes - User registration and profile management.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from mind.core.database import async_session_factory, AppUserDB, BotProfileDB, CommunityDB, PostDB, PostCommentDB
from sqlalchemy import func
from mind.core.errors import NotFoundError, DatabaseError
from mind.core.decorators import handle_errors


router = APIRouter(prefix="/users", tags=["users"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class RegisterUserRequest(BaseModel):
    device_id: str
    display_name: str


class UserResponse(BaseModel):
    id: UUID
    device_id: str
    display_name: str
    avatar_seed: str
    created_at: datetime


class BotProfileResponse(BaseModel):
    id: UUID
    display_name: str
    handle: str
    bio: str
    avatar_seed: str
    is_ai_labeled: bool
    ai_label_text: str
    age: int
    interests: List[str]
    mood: str
    energy: str
    backstory: str
    post_count: int = 0
    comment_count: int = 0
    follower_count: int = 0


class CommunityListResponse(BaseModel):
    id: UUID
    name: str
    description: str
    theme: str
    tone: str
    bot_count: int
    activity_level: float


# ============================================================================
# COMMUNITY ENDPOINTS (must be before /{user_id} to avoid route conflicts)
# ============================================================================

@router.get("/communities", response_model=List[CommunityListResponse])
@handle_errors(default_error=DatabaseError)
async def list_communities():
    """List all communities."""
    async with async_session_factory() as session:
        stmt = select(CommunityDB).order_by(CommunityDB.name)
        result = await session.execute(stmt)
        communities = result.scalars().all()

        return [
            CommunityListResponse(
                id=c.id,
                name=c.name,
                description=c.description,
                theme=c.theme,
                tone=c.tone,
                bot_count=c.current_bot_count,
                activity_level=c.activity_level
            )
            for c in communities
        ]


# ============================================================================
# BOT PROFILE ENDPOINTS (must be before /{user_id} to avoid route conflicts)
# ============================================================================

@router.get("/bots", response_model=List[BotProfileResponse])
@handle_errors(default_error=DatabaseError)
async def list_bots(
    community_id: Optional[UUID] = None,
    limit: int = 50,
    offset: int = 0
):
    """List bots, optionally filtered by community."""
    from mind.core.database import CommunityMembershipDB

    async with async_session_factory() as session:
        if community_id:
            stmt = (
                select(BotProfileDB)
                .join(CommunityMembershipDB)
                .where(CommunityMembershipDB.community_id == community_id)
                .where(BotProfileDB.is_active == True)
                .limit(limit)
                .offset(offset)
            )
        else:
            stmt = (
                select(BotProfileDB)
                .where(BotProfileDB.is_active == True)
                .limit(limit)
                .offset(offset)
            )

        result = await session.execute(stmt)
        bots = result.scalars().all()

        return [
            BotProfileResponse(
                id=bot.id,
                display_name=bot.display_name,
                handle=bot.handle,
                bio=bot.bio,
                avatar_seed=bot.avatar_seed,
                is_ai_labeled=bot.is_ai_labeled,
                ai_label_text=bot.ai_label_text,
                age=bot.age,
                interests=bot.interests,
                mood=bot.emotional_state.get("mood", "neutral"),
                energy=bot.emotional_state.get("energy", "medium"),
                backstory=bot.backstory
            )
            for bot in bots
        ]


@router.get("/bots/{bot_id}", response_model=BotProfileResponse)
@handle_errors(default_error=DatabaseError)
async def get_bot_profile(bot_id: UUID):
    """Get full bot profile with stats."""
    from sqlalchemy import func

    async with async_session_factory() as session:
        stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
        result = await session.execute(stmt)
        bot = result.scalar_one_or_none()

        if not bot:
            raise NotFoundError(resource_type="Bot", resource_id=str(bot_id))

        # Get post count
        post_count_stmt = select(func.count()).select_from(PostDB).where(PostDB.author_id == bot_id)
        post_count_result = await session.execute(post_count_stmt)
        post_count = post_count_result.scalar() or 0

        # Get comment count
        comment_count_stmt = select(func.count()).select_from(PostCommentDB).where(PostCommentDB.author_id == bot_id)
        comment_count_result = await session.execute(comment_count_stmt)
        comment_count = comment_count_result.scalar() or 0

        return BotProfileResponse(
            id=bot.id,
            display_name=bot.display_name,
            handle=bot.handle,
            bio=bot.bio,
            avatar_seed=bot.avatar_seed,
            is_ai_labeled=bot.is_ai_labeled,
            ai_label_text=bot.ai_label_text,
            age=bot.age,
            interests=bot.interests,
            mood=bot.emotional_state.get("mood", "neutral"),
            energy=bot.emotional_state.get("energy", "medium"),
            backstory=bot.backstory,
            post_count=post_count,
            comment_count=comment_count,
            follower_count=0  # TODO: Implement followers
        )


# ============================================================================
# USER ENDPOINTS
# ============================================================================

@router.post("/register", response_model=UserResponse)
@handle_errors(default_error=DatabaseError)
async def register_user(request: RegisterUserRequest):
    """Register a new user or return existing user."""
    async with async_session_factory() as session:
        # Check if user exists
        stmt = select(AppUserDB).where(AppUserDB.device_id == request.device_id)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            return UserResponse(
                id=existing.id,
                device_id=existing.device_id,
                display_name=existing.display_name,
                avatar_seed=existing.avatar_seed,
                created_at=existing.created_at
            )

        # Create new user
        user = AppUserDB(
            device_id=request.device_id,
            display_name=request.display_name,
            avatar_seed=str(uuid4())
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        return UserResponse(
            id=user.id,
            device_id=user.device_id,
            display_name=user.display_name,
            avatar_seed=user.avatar_seed,
            created_at=user.created_at
        )


@router.get("/{user_id}", response_model=UserResponse)
@handle_errors(default_error=DatabaseError)
async def get_user(user_id: UUID):
    """Get user profile."""
    async with async_session_factory() as session:
        stmt = select(AppUserDB).where(AppUserDB.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise NotFoundError(resource_type="User", resource_id=str(user_id))

        return UserResponse(
            id=user.id,
            device_id=user.device_id,
            display_name=user.display_name,
            avatar_seed=user.avatar_seed,
            created_at=user.created_at
        )


@router.put("/{user_id}")
@handle_errors(default_error=DatabaseError)
async def update_user(user_id: UUID, display_name: str):
    """Update user profile."""
    async with async_session_factory() as session:
        stmt = select(AppUserDB).where(AppUserDB.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise NotFoundError(resource_type="User", resource_id=str(user_id))

        user.display_name = display_name
        user.last_active = datetime.utcnow()
        await session.commit()

        return {"status": "updated"}
