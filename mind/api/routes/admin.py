"""
Admin API routes - Dashboard, Bot/User/Content management, System monitoring.
All endpoints require admin authentication.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import async_session_factory, AppUserDB, get_session
from mind.core.admin_service import AdminService


router = APIRouter(prefix="/admin", tags=["admin"])

# Declared for OpenAPI: admin routes expect this header (UUID of an app user with admin rights).
admin_user_header = APIKeyHeader(
    name="X-User-ID",
    auto_error=False,
    scheme_name="Admin X-User-ID",
    description=(
        "App user UUID for admin dashboard routes. "
        "The user must exist and have `is_admin=true`. "
        "In production, prefer aligning this with your JWT/session strategy."
    ),
)


# ============================================================================
# AUTHENTICATION DEPENDENCIES
# ============================================================================

async def get_current_user(
    session: AsyncSession = Depends(get_session),
    x_user_id: Optional[str] = Depends(admin_user_header),
) -> AppUserDB:
    """
    Resolve the current user from the `X-User-ID` header (admin dashboard auth).
    Exposed in OpenAPI so Swagger shows this requirement on protected admin routes.
    """
    user_id = x_user_id
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid user ID")

    stmt = select(AppUserDB).where(AppUserDB.id == user_uuid)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if user.is_banned:
        raise HTTPException(status_code=403, detail="User is banned")

    return user


async def require_admin(
    current_user: AppUserDB = Depends(get_current_user)
) -> AppUserDB:
    """Require the current user to be an admin."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
    return current_user


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class DashboardStatsResponse(BaseModel):
    total_users: int
    active_users_24h: int
    total_bots: int
    active_bots: int
    total_posts: int
    posts_24h: int
    total_messages: int
    llm_requests_today: int
    avg_response_time: float
    timestamp: str


class BotListItem(BaseModel):
    id: str
    display_name: str
    handle: str
    bio: str
    avatar_seed: str
    is_active: bool
    is_paused: bool
    is_deleted: bool
    created_at: str
    last_active: Optional[str]
    post_count: int
    comment_count: int


class BotDetailsResponse(BaseModel):
    id: str
    display_name: str
    handle: str
    bio: str
    backstory: str
    avatar_seed: str
    age: int
    gender: str
    location: str
    interests: List[str]
    personality_traits: Dict[str, Any]
    writing_fingerprint: Dict[str, Any]
    activity_pattern: Dict[str, Any]
    emotional_state: Dict[str, Any]
    is_active: bool
    is_paused: bool
    is_deleted: bool
    is_ai_labeled: bool
    ai_label_text: str
    created_at: str
    last_active: Optional[str]
    paused_at: Optional[str]
    stats: Dict[str, int]
    recent_posts: List[Dict[str, Any]]
    metrics: Optional[Dict[str, float]]


class UpdateBotRequest(BaseModel):
    display_name: Optional[str] = None
    bio: Optional[str] = None
    is_active: Optional[bool] = None
    is_ai_labeled: Optional[bool] = None
    ai_label_text: Optional[str] = None
    interests: Optional[List[str]] = None


class PauseBotRequest(BaseModel):
    reason: Optional[str] = None


class DeleteBotRequest(BaseModel):
    reason: Optional[str] = None


class UserListItem(BaseModel):
    id: str
    display_name: str
    device_id: str
    avatar_seed: str
    is_admin: bool
    is_banned: bool
    created_at: str
    last_active: Optional[str]
    like_count: int


class UserDetailsResponse(BaseModel):
    id: str
    display_name: str
    device_id: str
    avatar_seed: str
    is_admin: bool
    is_banned: bool
    ban_reason: Optional[str]
    banned_at: Optional[str]
    created_at: str
    last_active: Optional[str]
    stats: Dict[str, int]


class BanUserRequest(BaseModel):
    reason: Optional[str] = None


class PostListItem(BaseModel):
    id: str
    author: Dict[str, str]
    community: Dict[str, str]
    content: str
    image_url: Optional[str]
    like_count: int
    comment_count: int
    is_deleted: bool
    created_at: str


class DeletePostRequest(BaseModel):
    reason: Optional[str] = None


class FlaggedContentItem(BaseModel):
    id: str
    content_type: str
    content_id: str
    content_text: str
    flag_reason: str
    is_system_flagged: bool
    status: str
    created_at: str
    reviewed_at: Optional[str]
    action_taken: Optional[str]


class SystemLogItem(BaseModel):
    id: str
    level: str
    source: str
    message: str
    details: Dict[str, Any]
    created_at: str


class EngineStatusResponse(BaseModel):
    status: str
    uptime_hours: float
    pending_activities: int
    running_tasks: int
    last_error: Optional[str]
    capacity_used: float


class AuditLogItem(BaseModel):
    id: str
    admin: Dict[str, str]
    action: str
    entity_type: str
    entity_id: str
    details: Dict[str, Any]
    created_at: str


# ============================================================================
# DASHBOARD ENDPOINTS
# ============================================================================

@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    admin: AppUserDB = Depends(require_admin)
):
    """Get overall platform statistics for the admin dashboard."""
    async with async_session_factory() as session:
        stats = await AdminService.get_dashboard_stats(session)
        return DashboardStatsResponse(**stats)


# ============================================================================
# BOT MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/bots", response_model=List[BotListItem])
async def list_bots(
    include_deleted: bool = Query(False, description="Include soft-deleted bots"),
    include_paused: bool = Query(True, description="Include paused bots"),
    search: Optional[str] = Query(None, description="Search by name or handle"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AppUserDB = Depends(require_admin)
):
    """List all bots with stats."""
    async with async_session_factory() as session:
        bots = await AdminService.list_bots(
            session=session,
            include_deleted=include_deleted,
            include_paused=include_paused,
            limit=limit,
            offset=offset,
            search=search
        )
        return [BotListItem(**bot) for bot in bots]


@router.get("/bots/{bot_id}", response_model=BotDetailsResponse)
async def get_bot_details(
    bot_id: UUID,
    admin: AppUserDB = Depends(require_admin)
):
    """Get detailed bot information with activity stats."""
    async with async_session_factory() as session:
        bot = await AdminService.get_bot_details(session, bot_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        return BotDetailsResponse(**bot)


@router.put("/bots/{bot_id}")
async def update_bot(
    bot_id: UUID,
    request: UpdateBotRequest,
    admin: AppUserDB = Depends(require_admin)
):
    """Update bot settings."""
    async with async_session_factory() as session:
        updates = request.model_dump(exclude_unset=True)
        success = await AdminService.update_bot(
            session=session,
            bot_id=bot_id,
            updates=updates,
            admin_id=admin.id
        )
        if not success:
            raise HTTPException(status_code=404, detail="Bot not found")
        return {"status": "updated", "bot_id": str(bot_id)}


@router.post("/bots/{bot_id}/pause")
async def pause_bot(
    bot_id: UUID,
    request: PauseBotRequest,
    admin: AppUserDB = Depends(require_admin)
):
    """Pause bot activity."""
    async with async_session_factory() as session:
        success = await AdminService.pause_bot(
            session=session,
            bot_id=bot_id,
            admin_id=admin.id,
            reason=request.reason
        )
        if not success:
            raise HTTPException(status_code=404, detail="Bot not found")
        return {"status": "paused", "bot_id": str(bot_id)}


@router.post("/bots/{bot_id}/resume")
async def resume_bot(
    bot_id: UUID,
    admin: AppUserDB = Depends(require_admin)
):
    """Resume bot activity."""
    async with async_session_factory() as session:
        success = await AdminService.resume_bot(
            session=session,
            bot_id=bot_id,
            admin_id=admin.id
        )
        if not success:
            raise HTTPException(status_code=404, detail="Bot not found")
        return {"status": "resumed", "bot_id": str(bot_id)}


@router.delete("/bots/{bot_id}")
async def delete_bot(
    bot_id: UUID,
    request: DeleteBotRequest,
    admin: AppUserDB = Depends(require_admin)
):
    """Soft delete a bot."""
    async with async_session_factory() as session:
        success = await AdminService.delete_bot(
            session=session,
            bot_id=bot_id,
            admin_id=admin.id,
            reason=request.reason
        )
        if not success:
            raise HTTPException(status_code=404, detail="Bot not found")
        return {"status": "deleted", "bot_id": str(bot_id)}


# ============================================================================
# USER MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/users", response_model=List[UserListItem])
async def list_users(
    include_banned: bool = Query(True, description="Include banned users"),
    search: Optional[str] = Query(None, description="Search by display name"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AppUserDB = Depends(require_admin)
):
    """List all users with pagination."""
    async with async_session_factory() as session:
        users = await AdminService.list_users(
            session=session,
            include_banned=include_banned,
            limit=limit,
            offset=offset,
            search=search
        )
        return [UserListItem(**user) for user in users]


@router.get("/users/{user_id}", response_model=UserDetailsResponse)
async def get_user_details(
    user_id: UUID,
    admin: AppUserDB = Depends(require_admin)
):
    """Get detailed user information."""
    async with async_session_factory() as session:
        user = await AdminService.get_user_details(session, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return UserDetailsResponse(**user)


@router.put("/users/{user_id}/ban")
async def ban_user(
    user_id: UUID,
    request: BanUserRequest,
    admin: AppUserDB = Depends(require_admin)
):
    """Ban a user."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot ban yourself")

    async with async_session_factory() as session:
        success = await AdminService.ban_user(
            session=session,
            user_id=user_id,
            admin_id=admin.id,
            reason=request.reason
        )
        if not success:
            raise HTTPException(
                status_code=400,
                detail="User not found or cannot be banned (may be admin)"
            )
        return {"status": "banned", "user_id": str(user_id)}


@router.put("/users/{user_id}/unban")
async def unban_user(
    user_id: UUID,
    admin: AppUserDB = Depends(require_admin)
):
    """Unban a user."""
    async with async_session_factory() as session:
        success = await AdminService.unban_user(
            session=session,
            user_id=user_id,
            admin_id=admin.id
        )
        if not success:
            raise HTTPException(status_code=404, detail="User not found")
        return {"status": "unbanned", "user_id": str(user_id)}


# ============================================================================
# CONTENT MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/posts", response_model=List[PostListItem])
async def list_posts(
    include_deleted: bool = Query(False, description="Include deleted posts"),
    community_id: Optional[UUID] = Query(None, description="Filter by community"),
    author_id: Optional[UUID] = Query(None, description="Filter by author"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AppUserDB = Depends(require_admin)
):
    """List posts with filters."""
    async with async_session_factory() as session:
        posts = await AdminService.list_posts(
            session=session,
            include_deleted=include_deleted,
            community_id=community_id,
            author_id=author_id,
            limit=limit,
            offset=offset
        )
        return [PostListItem(**post) for post in posts]


@router.delete("/posts/{post_id}")
async def delete_post(
    post_id: UUID,
    request: DeletePostRequest,
    admin: AppUserDB = Depends(require_admin)
):
    """Delete a post."""
    async with async_session_factory() as session:
        success = await AdminService.delete_post(
            session=session,
            post_id=post_id,
            admin_id=admin.id,
            reason=request.reason
        )
        if not success:
            raise HTTPException(status_code=404, detail="Post not found")
        return {"status": "deleted", "post_id": str(post_id)}


@router.get("/flagged", response_model=List[FlaggedContentItem])
async def list_flagged_content(
    status: Optional[str] = Query("pending", description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AppUserDB = Depends(require_admin)
):
    """List flagged content for moderation."""
    async with async_session_factory() as session:
        flagged = await AdminService.list_flagged_content(
            session=session,
            status=status,
            limit=limit,
            offset=offset
        )
        return [FlaggedContentItem(**item) for item in flagged]


# ============================================================================
# SYSTEM ENDPOINTS
# ============================================================================

@router.get("/logs", response_model=List[SystemLogItem])
async def get_system_logs(
    level: Optional[str] = Query(None, description="Filter by log level"),
    source: Optional[str] = Query(None, description="Filter by source"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    admin: AppUserDB = Depends(require_admin)
):
    """Get recent system logs."""
    async with async_session_factory() as session:
        logs = await AdminService.get_system_logs(
            session=session,
            level=level,
            source=source,
            limit=limit,
            offset=offset
        )
        return [SystemLogItem(**log) for log in logs]


@router.get("/engine/status", response_model=EngineStatusResponse)
async def get_engine_status(
    admin: AppUserDB = Depends(require_admin)
):
    """Get activity engine status and stats."""
    status = await AdminService.get_engine_status()
    return EngineStatusResponse(**status)


@router.post("/engine/restart")
async def restart_engine(
    admin: AppUserDB = Depends(require_admin)
):
    """
    Restart the activity engine.
    Note: This is a placeholder - actual implementation depends on how the engine is managed.
    """
    async with async_session_factory() as session:
        # Log the restart action
        await AdminService.log_system_event(
            session=session,
            level="INFO",
            source="admin_api",
            message=f"Activity engine restart requested by admin {admin.display_name}",
            details={"admin_id": str(admin.id)}
        )

    # In a real implementation, this would send a signal to restart the engine
    # For now, just return success
    return {
        "status": "restart_initiated",
        "message": "Engine restart signal sent. This may take a few seconds."
    }


# ============================================================================
# AUDIT LOG ENDPOINTS
# ============================================================================

@router.get("/audit-logs", response_model=List[AuditLogItem])
async def get_audit_logs(
    admin_id: Optional[UUID] = Query(None, description="Filter by admin"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    admin: AppUserDB = Depends(require_admin)
):
    """Get admin audit logs."""
    async with async_session_factory() as session:
        logs = await AdminService.get_audit_logs(
            session=session,
            admin_id=admin_id,
            action=action,
            entity_type=entity_type,
            limit=limit,
            offset=offset
        )
        return [AuditLogItem(**log) for log in logs]


# ============================================================================
# AUTHENTICITY MODE ENDPOINTS
# ============================================================================

class AuthenticityModeRequest(BaseModel):
    """Request to change authenticity mode."""
    demo_mode: bool = Field(description="True for demo mode (10x faster), False for production (realistic timing)")


class AuthenticityModeResponse(BaseModel):
    """Current authenticity mode status."""
    demo_mode: bool
    timing_multiplier: float
    description: str


@router.get("/authenticity-mode", response_model=AuthenticityModeResponse)
async def get_authenticity_mode(
    admin: AppUserDB = Depends(require_admin)
):
    """
    Get current authenticity mode.

    Demo mode: 10x faster timing for testing/demos
    Production mode: Realistic human-like timing (minutes/hours)
    """
    from mind.engine.authenticity import get_authenticity_engine

    engine = get_authenticity_engine()
    return AuthenticityModeResponse(
        demo_mode=engine.demo_mode,
        timing_multiplier=engine.timing_multiplier,
        description="Demo mode: fast timing for testing" if engine.demo_mode else "Production mode: realistic human-like timing"
    )


@router.post("/authenticity-mode", response_model=AuthenticityModeResponse)
async def set_authenticity_mode(
    request: AuthenticityModeRequest,
    admin: AppUserDB = Depends(require_admin)
):
    """
    Toggle authenticity mode.

    - demo_mode=true: Bot interactions happen in seconds (for testing)
    - demo_mode=false: Bot interactions happen in minutes/hours (realistic)
    """
    from mind.engine.authenticity import get_authenticity_engine

    engine = get_authenticity_engine()
    engine.set_demo_mode(request.demo_mode)

    return AuthenticityModeResponse(
        demo_mode=engine.demo_mode,
        timing_multiplier=engine.timing_multiplier,
        description="Demo mode: fast timing for testing" if engine.demo_mode else "Production mode: realistic human-like timing"
    )
