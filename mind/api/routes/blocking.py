"""
Blocking and Flagging API routes - User blocking and behavior flagging.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from mind.core.database import async_session_factory, AppUserDB
from mind.blocking.blocking_service import BlockingService, blocking_service
from mind.blocking.flagging_service import (
    FlaggingService, flagging_service, FlagType, FlagStatus
)
from sqlalchemy import select


router = APIRouter(tags=["blocking"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class BlockBotRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500, description="Optional reason for blocking")


class BlockedBotResponse(BaseModel):
    id: UUID
    display_name: str
    handle: str
    avatar_seed: str
    bio: str
    blocked_at: datetime
    reason: Optional[str]


class BlockedBotsListResponse(BaseModel):
    blocked_bots: List[BlockedBotResponse]
    total: int


class FlagBotRequest(BaseModel):
    flag_type: str = Field(..., description="Type of flag: inappropriate, spam, harassment, impersonation, misinformation, other")
    description: Optional[str] = Field(None, max_length=1000, description="Description of the issue")
    content_type: Optional[str] = Field(None, description="Type of content being flagged: post, comment, dm, chat")
    content_id: Optional[UUID] = Field(None, description="ID of the specific content being flagged")


class FlagResponse(BaseModel):
    id: UUID
    flag_type: str
    description: Optional[str]
    status: str
    created_at: datetime
    reporter_id: UUID
    reporter_name: str
    content_type: Optional[str]
    content_id: Optional[UUID]
    resolution: Optional[str]
    resolved_at: Optional[datetime]


class FlagListResponse(BaseModel):
    flags: List[FlagResponse]
    total: int


class ResolveFlagRequest(BaseModel):
    resolution: str = Field(..., min_length=1, max_length=1000, description="Resolution description")


class FlaggedBotResponse(BaseModel):
    id: UUID
    display_name: str
    handle: str
    avatar_seed: str
    is_paused: bool
    is_active: bool
    flag_count: int
    created_at: datetime
    last_active: datetime


class FlagStatisticsResponse(BaseModel):
    total_flags: int
    by_status: dict
    by_type: dict


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def verify_user_exists(user_id: UUID) -> bool:
    """Verify that a user exists."""
    async with async_session_factory() as session:
        stmt = select(AppUserDB).where(AppUserDB.id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None


async def verify_admin(admin_id: UUID) -> bool:
    """Verify that a user is an admin."""
    async with async_session_factory() as session:
        stmt = select(AppUserDB).where(
            AppUserDB.id == admin_id,
            AppUserDB.is_admin == True
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None


# ============================================================================
# BLOCKING ENDPOINTS
# ============================================================================

@router.post("/users/block/{bot_id}")
async def block_bot(
    bot_id: UUID,
    user_id: UUID,
    request: Optional[BlockBotRequest] = None
):
    """
    Block a bot.

    The user will no longer see posts, comments, or messages from this bot.
    """
    if not await verify_user_exists(user_id):
        raise HTTPException(status_code=404, detail="User not found")

    reason = request.reason if request else None
    result = await blocking_service.block_bot(user_id, bot_id, reason)

    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message"))

    return result


@router.delete("/users/block/{bot_id}")
async def unblock_bot(bot_id: UUID, user_id: UUID):
    """
    Unblock a bot.

    The user will start seeing content from this bot again.
    """
    if not await verify_user_exists(user_id):
        raise HTTPException(status_code=404, detail="User not found")

    result = await blocking_service.unblock_bot(user_id, bot_id)
    return result


@router.get("/users/blocked", response_model=BlockedBotsListResponse)
async def list_blocked_bots(
    user_id: UUID,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0)
):
    """
    List all bots blocked by the user.
    """
    if not await verify_user_exists(user_id):
        raise HTTPException(status_code=404, detail="User not found")

    blocked_bots = await blocking_service.get_blocked_bots(user_id, limit, offset)
    total = await blocking_service.get_block_count(user_id)

    return BlockedBotsListResponse(
        blocked_bots=[
            BlockedBotResponse(
                id=bot["id"],
                display_name=bot["display_name"],
                handle=bot["handle"],
                avatar_seed=bot["avatar_seed"],
                bio=bot["bio"],
                blocked_at=bot["blocked_at"],
                reason=bot["reason"]
            )
            for bot in blocked_bots
        ],
        total=total
    )


@router.get("/users/blocked/{bot_id}/check")
async def check_blocked(user_id: UUID, bot_id: UUID):
    """
    Check if a specific bot is blocked by the user.
    """
    if not await verify_user_exists(user_id):
        raise HTTPException(status_code=404, detail="User not found")

    is_blocked = await blocking_service.is_blocked(user_id, bot_id)
    return {"is_blocked": is_blocked, "bot_id": str(bot_id)}


# ============================================================================
# FLAGGING ENDPOINTS
# ============================================================================

@router.post("/bots/{bot_id}/flag")
async def flag_bot(
    bot_id: UUID,
    user_id: UUID,
    request: FlagBotRequest
):
    """
    Flag a bot's behavior.

    Users can report bots for inappropriate behavior, spam, harassment, etc.
    Bots with too many pending flags may be auto-paused.
    """
    if not await verify_user_exists(user_id):
        raise HTTPException(status_code=404, detail="User not found")

    result = await flagging_service.flag_behavior(
        bot_id=bot_id,
        reporter_id=user_id,
        flag_type=request.flag_type,
        description=request.description,
        content_type=request.content_type,
        content_id=request.content_id
    )

    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message"))

    return result


@router.get("/bots/{bot_id}/flags", response_model=FlagListResponse)
async def get_bot_flags(
    bot_id: UUID,
    admin_id: UUID,
    status: Optional[str] = Query(default=None, description="Filter by status: pending, reviewed, resolved"),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0)
):
    """
    Get flags for a bot. Admin only.
    """
    if not await verify_admin(admin_id):
        raise HTTPException(status_code=403, detail="Admin access required")

    flags = await flagging_service.get_flags(bot_id, status, limit, offset)

    return FlagListResponse(
        flags=[
            FlagResponse(
                id=flag["id"],
                flag_type=flag["flag_type"],
                description=flag["description"],
                status=flag["status"],
                created_at=flag["created_at"],
                reporter_id=flag["reporter"]["id"],
                reporter_name=flag["reporter"]["display_name"],
                content_type=flag["content_type"],
                content_id=flag["content_id"],
                resolution=flag["resolution"],
                resolved_at=flag["resolved_at"]
            )
            for flag in flags
        ],
        total=len(flags)
    )


@router.post("/flags/{flag_id}/resolve")
async def resolve_flag(
    flag_id: UUID,
    admin_id: UUID,
    request: ResolveFlagRequest
):
    """
    Resolve a behavior flag. Admin only.
    """
    result = await flagging_service.resolve_flag(flag_id, request.resolution, admin_id)

    if result.get("status") == "error":
        if "Unauthorized" in result.get("message", ""):
            raise HTTPException(status_code=403, detail=result.get("message"))
        raise HTTPException(status_code=404, detail=result.get("message"))

    return result


@router.get("/admin/flagged-bots", response_model=List[FlaggedBotResponse])
async def get_flagged_bots(
    admin_id: UUID,
    min_flags: int = Query(default=3, ge=1, description="Minimum number of flags"),
    status: Optional[str] = Query(default=None, description="Filter by flag status"),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0)
):
    """
    Get bots with multiple flags. Admin only.
    """
    if not await verify_admin(admin_id):
        raise HTTPException(status_code=403, detail="Admin access required")

    flagged_bots = await flagging_service.get_flagged_bots(min_flags, status, limit, offset)

    return [
        FlaggedBotResponse(
            id=bot["id"],
            display_name=bot["display_name"],
            handle=bot["handle"],
            avatar_seed=bot["avatar_seed"],
            is_paused=bot["is_paused"],
            is_active=bot["is_active"],
            flag_count=bot["flag_count"],
            created_at=bot["created_at"],
            last_active=bot["last_active"]
        )
        for bot in flagged_bots
    ]


@router.get("/admin/flag-statistics", response_model=FlagStatisticsResponse)
async def get_flag_statistics(
    admin_id: UUID,
    bot_id: Optional[UUID] = None
):
    """
    Get flag statistics. Admin only.
    """
    if not await verify_admin(admin_id):
        raise HTTPException(status_code=403, detail="Admin access required")

    stats = await flagging_service.get_flag_statistics(bot_id)

    return FlagStatisticsResponse(
        total_flags=stats["total_flags"],
        by_status=stats["by_status"],
        by_type=stats["by_type"]
    )


@router.post("/admin/bots/{bot_id}/unpause-if-resolved")
async def unpause_bot_if_resolved(
    bot_id: UUID,
    admin_id: UUID
):
    """
    Check if all flags are resolved and unpause bot if so. Admin only.
    """
    if not await verify_admin(admin_id):
        raise HTTPException(status_code=403, detail="Admin access required")

    result = await flagging_service.unpause_bot_if_resolved(bot_id)

    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message"))

    return result
