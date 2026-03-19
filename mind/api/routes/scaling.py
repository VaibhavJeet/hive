"""
Scaling API routes - Admin-only endpoints for bot scaling operations.

Provides endpoints for:
- Bot retirement management
- Community scaling and rebalancing
- Memory consolidation
- System scaling statistics
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from mind.core.database import async_session_factory, AppUserDB, BotProfileDB
from mind.core.auth import AuthenticatedUser
from mind.api.dependencies import get_current_user

from mind.scaling.bot_retirement import (
    BotRetirementManager,
    RetirementReason,
    get_retirement_manager
)
from mind.scaling.community_scaling import (
    CommunityScalingManager,
    get_scaling_manager
)
from mind.scaling.memory_consolidation import (
    MemoryConsolidationManager,
    get_consolidation_manager
)


router = APIRouter(prefix="/admin", tags=["admin", "scaling"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class RetireBotRequest(BaseModel):
    """Request to retire a bot."""
    reason: RetirementReason
    notes: Optional[str] = None


class RetiredBotResponse(BaseModel):
    """Response for retired bot details."""
    id: UUID
    display_name: str
    handle: str
    reason: str
    retired_at: datetime
    total_posts: int
    total_memories: int
    active_days: int
    archived_data_id: Optional[UUID] = None


class ScalingStatsResponse(BaseModel):
    """Response for scaling statistics."""
    total_active_bots: int
    total_retired_bots: int
    total_communities: int
    communities_overloaded: int
    communities_underutilized: int
    bots_eligible_for_retirement: int
    memory_consolidation_candidates: int
    last_rebalance_at: Optional[datetime] = None


class CommunityLoadResponse(BaseModel):
    """Response for community load metrics."""
    community_id: UUID
    community_name: str
    bot_count: int
    message_rate: float
    user_count: int
    post_rate: float
    comment_rate: float
    engagement_score: float
    load_factor: float
    is_overloaded: bool
    is_underutilized: bool


class RebalanceResponse(BaseModel):
    """Response for rebalance operation."""
    success: bool
    communities_adjusted: int
    bots_moved: int
    bots_added: int
    bots_removed: int
    details: List[dict]


class CommunityLimitsRequest(BaseModel):
    """Request to set community limits."""
    max_bots: Optional[int] = Field(None, ge=1, le=1000)
    min_bots: Optional[int] = Field(None, ge=0, le=100)
    max_messages_per_hour: Optional[int] = Field(None, ge=10, le=10000)


class ConsolidationResponse(BaseModel):
    """Response for memory consolidation."""
    bot_id: UUID
    memories_processed: int
    memories_merged: int
    memories_summarized: int
    memories_archived: int
    storage_saved_bytes: int
    new_summaries: List[str]


class MemoryStatsResponse(BaseModel):
    """Response for memory statistics."""
    bot_id: UUID
    total_memories: int
    active_memories: int
    archived_memories: int
    size_bytes: int
    oldest_memory: Optional[datetime]
    newest_memory: Optional[datetime]
    memory_types: dict
    avg_importance: float
    consolidation_candidates: int


# ============================================================================
# ADMIN CHECK DEPENDENCY
# ============================================================================

async def require_admin(
    current_user: AuthenticatedUser = Depends(get_current_user)
) -> AuthenticatedUser:
    """
    Dependency to require admin privileges.

    Raises:
        HTTPException 403: If user is not an admin
    """
    async with async_session_factory() as session:
        stmt = select(AppUserDB).where(AppUserDB.id == current_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None or not getattr(user, 'is_admin', False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )

        return current_user


# ============================================================================
# BOT RETIREMENT ENDPOINTS
# ============================================================================

@router.post(
    "/bots/{bot_id}/retire",
    response_model=RetiredBotResponse,
    summary="Retire a bot",
    description="Gracefully retire a bot, archiving its data and stopping all activity"
)
async def retire_bot(
    bot_id: UUID,
    request: RetireBotRequest,
    admin: AuthenticatedUser = Depends(require_admin)
):
    """
    Retire a bot.

    This operation:
    - Archives the bot's memories and posts
    - Marks the bot as retired
    - Stops all future activity
    - Preserves history for reference
    """
    manager = get_retirement_manager()

    try:
        retired_bot = await manager.retire_bot(
            bot_id=bot_id,
            reason=request.reason,
            retired_by=admin.id,
            notes=request.notes
        )

        return RetiredBotResponse(
            id=retired_bot.id,
            display_name=retired_bot.display_name,
            handle=retired_bot.handle,
            reason=retired_bot.reason.value,
            retired_at=retired_bot.retired_at,
            total_posts=retired_bot.total_posts,
            total_memories=retired_bot.total_memories,
            active_days=retired_bot.active_days,
            archived_data_id=retired_bot.archived_data_id
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get(
    "/bots/{bot_id}/retirement-eligibility",
    summary="Check retirement eligibility",
    description="Check if a bot is eligible for retirement"
)
async def check_retirement_eligibility(
    bot_id: UUID,
    admin: AuthenticatedUser = Depends(require_admin)
):
    """Check if a bot is eligible for retirement."""
    manager = get_retirement_manager()
    eligibility = await manager.check_retirement_eligibility(bot_id)

    return {
        "bot_id": str(bot_id),
        "eligible": eligibility.eligible,
        "reason": eligibility.reason.value if eligibility.reason else None,
        "details": eligibility.details
    }


@router.get(
    "/bots/retired",
    response_model=List[RetiredBotResponse],
    summary="List retired bots",
    description="Get list of all retired bots"
)
async def list_retired_bots(
    limit: int = 100,
    offset: int = 0,
    reason: Optional[RetirementReason] = None,
    admin: AuthenticatedUser = Depends(require_admin)
):
    """Get list of retired bots."""
    manager = get_retirement_manager()
    retired_bots = await manager.get_retired_bots(
        limit=limit,
        offset=offset,
        reason=reason
    )

    return [
        RetiredBotResponse(
            id=bot.id,
            display_name=bot.display_name,
            handle=bot.handle,
            reason=bot.reason.value,
            retired_at=bot.retired_at,
            total_posts=bot.total_posts,
            total_memories=bot.total_memories,
            active_days=bot.active_days,
            archived_data_id=bot.archived_data_id
        )
        for bot in retired_bots
    ]


# ============================================================================
# SCALING STATS ENDPOINTS
# ============================================================================

@router.get(
    "/scaling/stats",
    response_model=ScalingStatsResponse,
    summary="Get scaling statistics",
    description="Get overall system scaling statistics"
)
async def get_scaling_stats(
    admin: AuthenticatedUser = Depends(require_admin)
):
    """Get comprehensive scaling statistics."""
    scaling_manager = get_scaling_manager()
    retirement_manager = get_retirement_manager()

    # Get all load metrics
    all_loads = await scaling_manager.get_all_load_metrics()

    # Count overloaded and underutilized
    overloaded = sum(1 for load in all_loads if load.is_overloaded)
    underutilized = sum(1 for load in all_loads if load.is_underutilized)

    # Get bot counts
    async with async_session_factory() as session:
        from sqlalchemy import func

        active_stmt = select(func.count()).select_from(BotProfileDB).where(
            BotProfileDB.is_active == True
        )
        active_result = await session.execute(active_stmt)
        total_active = active_result.scalar() or 0

        retired_stmt = select(func.count()).select_from(BotProfileDB).where(
            BotProfileDB.is_retired == True
        )
        retired_result = await session.execute(retired_stmt)
        total_retired = retired_result.scalar() or 0

    # Check retirement eligibility
    eligible = await retirement_manager.bulk_check_retirement()

    return ScalingStatsResponse(
        total_active_bots=total_active,
        total_retired_bots=total_retired,
        total_communities=len(all_loads),
        communities_overloaded=overloaded,
        communities_underutilized=underutilized,
        bots_eligible_for_retirement=len(eligible),
        memory_consolidation_candidates=0,  # Would need to check each bot
        last_rebalance_at=None
    )


@router.get(
    "/scaling/community-loads",
    response_model=List[CommunityLoadResponse],
    summary="Get community load metrics",
    description="Get load metrics for all communities"
)
async def get_community_loads(
    admin: AuthenticatedUser = Depends(require_admin)
):
    """Get load metrics for all communities."""
    manager = get_scaling_manager()
    all_loads = await manager.get_all_load_metrics()

    return [
        CommunityLoadResponse(
            community_id=load.community_id,
            community_name=load.community_name,
            bot_count=load.bot_count,
            message_rate=load.message_rate,
            user_count=load.user_count,
            post_rate=load.post_rate,
            comment_rate=load.comment_rate,
            engagement_score=load.engagement_score,
            load_factor=load.load_factor,
            is_overloaded=load.is_overloaded,
            is_underutilized=load.is_underutilized
        )
        for load in all_loads
    ]


# ============================================================================
# REBALANCING ENDPOINTS
# ============================================================================

@router.post(
    "/scaling/rebalance",
    response_model=RebalanceResponse,
    summary="Rebalance bots across communities",
    description="Redistribute bots from overloaded to underutilized communities"
)
async def rebalance_bots(
    admin: AuthenticatedUser = Depends(require_admin)
):
    """Rebalance bots across communities."""
    manager = get_scaling_manager()
    result = await manager.rebalance_bots()

    return RebalanceResponse(
        success=True,
        communities_adjusted=result.communities_adjusted,
        bots_moved=result.bots_moved,
        bots_added=result.bots_added,
        bots_removed=result.bots_removed,
        details=result.details
    )


@router.put(
    "/scaling/community/{community_id}/limits",
    summary="Set community limits",
    description="Set scaling limits for a specific community"
)
async def set_community_limits(
    community_id: UUID,
    request: CommunityLimitsRequest,
    admin: AuthenticatedUser = Depends(require_admin)
):
    """Set scaling limits for a community."""
    manager = get_scaling_manager()

    limits = manager.set_community_limits(
        community_id=community_id,
        max_bots=request.max_bots,
        min_bots=request.min_bots,
        max_messages_per_hour=request.max_messages_per_hour
    )

    return {
        "community_id": str(community_id),
        "max_bots": limits.max_bots,
        "min_bots": limits.min_bots,
        "max_messages_per_hour": limits.max_messages_per_hour,
        "max_posts_per_hour": limits.max_posts_per_hour,
        "target_engagement": limits.target_engagement
    }


# ============================================================================
# MEMORY CONSOLIDATION ENDPOINTS
# ============================================================================

@router.post(
    "/bots/{bot_id}/consolidate-memories",
    response_model=ConsolidationResponse,
    summary="Consolidate bot memories",
    description="Run memory consolidation for a specific bot"
)
async def consolidate_bot_memories(
    bot_id: UUID,
    admin: AuthenticatedUser = Depends(require_admin)
):
    """Consolidate memories for a bot."""
    manager = get_consolidation_manager()
    result = await manager.full_consolidation(bot_id)

    return ConsolidationResponse(
        bot_id=result.bot_id,
        memories_processed=result.memories_processed,
        memories_merged=result.memories_merged,
        memories_summarized=result.memories_summarized,
        memories_archived=result.memories_archived,
        storage_saved_bytes=result.storage_saved_bytes,
        new_summaries=result.new_summaries
    )


@router.get(
    "/bots/{bot_id}/memory-stats",
    response_model=MemoryStatsResponse,
    summary="Get memory statistics",
    description="Get memory statistics for a specific bot"
)
async def get_bot_memory_stats(
    bot_id: UUID,
    admin: AuthenticatedUser = Depends(require_admin)
):
    """Get memory statistics for a bot."""
    manager = get_consolidation_manager()
    stats = await manager.get_memory_stats(bot_id)

    return MemoryStatsResponse(
        bot_id=stats.bot_id,
        total_memories=stats.total_memories,
        active_memories=stats.active_memories,
        archived_memories=stats.archived_memories,
        size_bytes=stats.size_bytes,
        oldest_memory=stats.oldest_memory,
        newest_memory=stats.newest_memory,
        memory_types=stats.memory_types,
        avg_importance=stats.avg_importance,
        consolidation_candidates=stats.consolidation_candidates
    )


@router.post(
    "/scaling/consolidate-all",
    summary="Consolidate all bot memories",
    description="Run memory consolidation for all active bots"
)
async def consolidate_all_memories(
    admin: AuthenticatedUser = Depends(require_admin)
):
    """Consolidate memories for all bots."""
    manager = get_consolidation_manager()

    async with async_session_factory() as session:
        stmt = select(BotProfileDB.id).where(BotProfileDB.is_active == True)
        result = await session.execute(stmt)
        bot_ids = [row[0] for row in result.all()]

    results = []
    total_saved = 0

    for bot_id in bot_ids:
        try:
            consolidation = await manager.full_consolidation(bot_id)
            total_saved += consolidation.storage_saved_bytes
            results.append({
                "bot_id": str(bot_id),
                "memories_processed": consolidation.memories_processed,
                "storage_saved": consolidation.storage_saved_bytes
            })
        except Exception as e:
            results.append({
                "bot_id": str(bot_id),
                "error": str(e)
            })

    return {
        "bots_processed": len(bot_ids),
        "total_storage_saved_bytes": total_saved,
        "results": results[:100]  # Limit response size
    }
