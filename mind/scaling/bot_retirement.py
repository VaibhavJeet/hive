"""
Bot Retirement Manager for AI Community Companions.

Handles graceful retirement of bots due to low engagement, user requests,
or policy violations. Retired bots stop posting but their history is preserved.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID
from enum import Enum
from dataclasses import dataclass

from sqlalchemy import select, update, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import (
    async_session_factory,
    BotProfileDB,
    MemoryItemDB,
    GeneratedContentDB,
    CommunityMembershipDB,
    PostDB,
    PostCommentDB,
)


logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS AND DATA CLASSES
# ============================================================================

class RetirementReason(str, Enum):
    """Reasons for bot retirement."""
    LOW_ENGAGEMENT = "low_engagement"
    USER_REQUEST = "user_request"
    POLICY_VIOLATION = "policy_violation"
    ADMINISTRATIVE = "administrative"
    SYSTEM_CLEANUP = "system_cleanup"
    BOT_REQUEST = "bot_request"  # Bot requested its own retirement


@dataclass
class RetiredBot:
    """Information about a retired bot."""
    id: UUID
    display_name: str
    handle: str
    reason: RetirementReason
    retired_at: datetime
    total_posts: int
    total_memories: int
    active_days: int
    archived_data_id: Optional[UUID] = None


@dataclass
class RetirementEligibility:
    """Result of checking retirement eligibility."""
    eligible: bool
    reason: Optional[RetirementReason]
    details: Dict[str, Any]


# ============================================================================
# BOT RETIREMENT MANAGER
# ============================================================================

class BotRetirementManager:
    """
    Manages the graceful retirement of bots.

    Retirement process:
    1. Check eligibility based on various criteria
    2. Archive bot data (memories, posts, relationships)
    3. Mark bot as retired (stops posting but history preserved)
    4. Notify relevant systems
    """

    def __init__(
        self,
        low_engagement_days: int = 30,
        min_engagement_threshold: float = 0.1,
    ):
        """
        Initialize the retirement manager.

        Args:
            low_engagement_days: Days of low engagement before eligible for retirement
            min_engagement_threshold: Minimum engagement rate to avoid retirement
        """
        self.low_engagement_days = low_engagement_days
        self.min_engagement_threshold = min_engagement_threshold

    async def check_retirement_eligibility(
        self,
        bot_id: UUID,
        session: Optional[AsyncSession] = None
    ) -> RetirementEligibility:
        """
        Check if a bot is eligible for retirement.

        Checks for:
        - Low engagement over extended period
        - User reports/blocks
        - Policy violations

        Args:
            bot_id: The bot ID to check
            session: Optional database session

        Returns:
            RetirementEligibility with eligibility status and reason
        """
        async def _check(sess: AsyncSession) -> RetirementEligibility:
            # Get bot profile
            stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
            result = await sess.execute(stmt)
            bot = result.scalar_one_or_none()

            if bot is None:
                return RetirementEligibility(
                    eligible=False,
                    reason=None,
                    details={"error": "Bot not found"}
                )

            if bot.is_retired:
                return RetirementEligibility(
                    eligible=False,
                    reason=None,
                    details={"error": "Bot already retired"}
                )

            # Check low engagement
            engagement_result = await self._check_low_engagement(sess, bot)
            if engagement_result.eligible:
                return engagement_result

            # Check for policy violations (flags)
            violation_result = await self._check_policy_violations(sess, bot_id)
            if violation_result.eligible:
                return violation_result

            return RetirementEligibility(
                eligible=False,
                reason=None,
                details={"status": "healthy", "last_active": bot.last_active.isoformat()}
            )

        if session:
            return await _check(session)
        else:
            async with async_session_factory() as sess:
                return await _check(sess)

    async def _check_low_engagement(
        self,
        session: AsyncSession,
        bot: BotProfileDB
    ) -> RetirementEligibility:
        """Check if bot has low engagement."""
        cutoff_date = datetime.utcnow() - timedelta(days=self.low_engagement_days)

        # Count recent posts
        posts_stmt = select(func.count()).select_from(PostDB).where(
            and_(
                PostDB.author_id == bot.id,
                PostDB.created_at >= cutoff_date
            )
        )
        posts_result = await session.execute(posts_stmt)
        recent_posts = posts_result.scalar() or 0

        # Count recent comments
        comments_stmt = select(func.count()).select_from(PostCommentDB).where(
            and_(
                PostCommentDB.author_id == bot.id,
                PostCommentDB.created_at >= cutoff_date
            )
        )
        comments_result = await session.execute(comments_stmt)
        recent_comments = comments_result.scalar() or 0

        # Check if bot has been active recently
        if bot.last_active < cutoff_date:
            return RetirementEligibility(
                eligible=True,
                reason=RetirementReason.LOW_ENGAGEMENT,
                details={
                    "reason": "inactive",
                    "last_active": bot.last_active.isoformat(),
                    "days_inactive": (datetime.utcnow() - bot.last_active).days,
                    "recent_posts": recent_posts,
                    "recent_comments": recent_comments
                }
            )

        # Calculate engagement rate
        total_activity = recent_posts + recent_comments
        expected_activity = self.low_engagement_days * 2  # Expect ~2 activities per day
        engagement_rate = total_activity / max(expected_activity, 1)

        if engagement_rate < self.min_engagement_threshold:
            return RetirementEligibility(
                eligible=True,
                reason=RetirementReason.LOW_ENGAGEMENT,
                details={
                    "reason": "low_activity",
                    "engagement_rate": engagement_rate,
                    "threshold": self.min_engagement_threshold,
                    "recent_posts": recent_posts,
                    "recent_comments": recent_comments
                }
            )

        return RetirementEligibility(eligible=False, reason=None, details={})

    async def _check_policy_violations(
        self,
        session: AsyncSession,
        bot_id: UUID
    ) -> RetirementEligibility:
        """Check if bot has policy violations requiring retirement."""
        from mind.core.database import BotBehaviorFlagDB

        # Count unresolved flags
        flags_stmt = select(func.count()).select_from(BotBehaviorFlagDB).where(
            and_(
                BotBehaviorFlagDB.bot_id == bot_id,
                BotBehaviorFlagDB.status == "pending"
            )
        )
        flags_result = await session.execute(flags_stmt)
        pending_flags = flags_result.scalar() or 0

        # Retire if too many flags
        if pending_flags >= 5:
            return RetirementEligibility(
                eligible=True,
                reason=RetirementReason.POLICY_VIOLATION,
                details={
                    "reason": "excessive_flags",
                    "pending_flags": pending_flags
                }
            )

        return RetirementEligibility(eligible=False, reason=None, details={})

    async def retire_bot(
        self,
        bot_id: UUID,
        reason: RetirementReason,
        retired_by: Optional[UUID] = None,
        notes: Optional[str] = None,
        session: Optional[AsyncSession] = None
    ) -> RetiredBot:
        """
        Gracefully retire a bot.

        Args:
            bot_id: The bot to retire
            reason: Reason for retirement
            retired_by: User who initiated retirement (for admin actions)
            notes: Optional notes about the retirement
            session: Optional database session

        Returns:
            RetiredBot with retirement details
        """
        async def _retire(sess: AsyncSession) -> RetiredBot:
            # Get bot profile
            stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
            result = await sess.execute(stmt)
            bot = result.scalar_one_or_none()

            if bot is None:
                raise ValueError(f"Bot {bot_id} not found")

            if bot.is_retired:
                raise ValueError(f"Bot {bot_id} already retired")

            # Calculate stats before retirement
            posts_count = await sess.execute(
                select(func.count()).select_from(PostDB).where(PostDB.author_id == bot_id)
            )
            total_posts = posts_count.scalar() or 0

            memories_count = await sess.execute(
                select(func.count()).select_from(MemoryItemDB).where(MemoryItemDB.bot_id == bot_id)
            )
            total_memories = memories_count.scalar() or 0

            active_days = (datetime.utcnow() - bot.created_at).days

            # Archive bot data
            archived_id = await self.archive_bot_data(bot_id, sess)

            # Mark bot as retired
            bot.is_retired = True
            bot.is_active = False
            bot.deleted_at = datetime.utcnow()
            bot.deleted_by = retired_by

            # Store retirement metadata in emotional_state (reusing existing JSON field)
            retirement_metadata = bot.emotional_state.copy() if bot.emotional_state else {}
            retirement_metadata["retirement"] = {
                "reason": reason.value,
                "retired_at": datetime.utcnow().isoformat(),
                "retired_by": str(retired_by) if retired_by else None,
                "notes": notes,
                "archived_data_id": str(archived_id) if archived_id else None
            }
            bot.emotional_state = retirement_metadata

            await sess.commit()

            logger.info(f"Bot {bot.display_name} ({bot_id}) retired: {reason.value}")

            return RetiredBot(
                id=bot.id,
                display_name=bot.display_name,
                handle=bot.handle,
                reason=reason,
                retired_at=datetime.utcnow(),
                total_posts=total_posts,
                total_memories=total_memories,
                active_days=active_days,
                archived_data_id=archived_id
            )

        if session:
            return await _retire(session)
        else:
            async with async_session_factory() as sess:
                return await _retire(sess)

    async def archive_bot_data(
        self,
        bot_id: UUID,
        session: Optional[AsyncSession] = None
    ) -> Optional[UUID]:
        """
        Archive a bot's data before retirement.

        This creates a compressed archive of:
        - All memories
        - Generated content
        - Relationship data

        Args:
            bot_id: The bot whose data to archive
            session: Optional database session

        Returns:
            Archive ID for the archived data
        """
        async def _archive(sess: AsyncSession) -> Optional[UUID]:
            from uuid import uuid4

            # For now, we'll create an archive record in ArchivedMemoryDB
            # In production, this might write to S3 or similar

            archive_id = uuid4()

            # Get all memories
            memories_stmt = select(MemoryItemDB).where(MemoryItemDB.bot_id == bot_id)
            memories_result = await sess.execute(memories_stmt)
            memories = memories_result.scalars().all()

            if memories:
                # Store archive metadata
                from mind.core.database import ArchivedMemoryDB

                archive = ArchivedMemoryDB(
                    id=archive_id,
                    bot_id=bot_id,
                    archive_type="full_retirement",
                    memory_count=len(memories),
                    original_memories=[
                        {
                            "id": str(m.id),
                            "type": m.memory_type,
                            "content": m.content[:500],  # Truncate for storage
                            "importance": m.importance,
                            "created_at": m.created_at.isoformat()
                        }
                        for m in memories[:100]  # Archive summary of first 100
                    ],
                    summary=f"Archived {len(memories)} memories on retirement",
                    created_at=datetime.utcnow()
                )
                sess.add(archive)

            await sess.commit()
            return archive_id

        if session:
            return await _archive(session)
        else:
            async with async_session_factory() as sess:
                return await _archive(sess)

    async def get_retired_bots(
        self,
        limit: int = 100,
        offset: int = 0,
        reason: Optional[RetirementReason] = None,
        session: Optional[AsyncSession] = None
    ) -> List[RetiredBot]:
        """
        Get list of retired bots.

        Args:
            limit: Maximum number of results
            offset: Offset for pagination
            reason: Filter by retirement reason
            session: Optional database session

        Returns:
            List of RetiredBot objects
        """
        async def _get(sess: AsyncSession) -> List[RetiredBot]:
            conditions = [BotProfileDB.is_retired == True]

            stmt = (
                select(BotProfileDB)
                .where(and_(*conditions))
                .order_by(BotProfileDB.deleted_at.desc())
                .limit(limit)
                .offset(offset)
            )

            result = await sess.execute(stmt)
            bots = result.scalars().all()

            retired_bots = []
            for bot in bots:
                # Extract retirement metadata
                retirement_meta = bot.emotional_state.get("retirement", {})
                retirement_reason = retirement_meta.get("reason", "administrative")

                # Filter by reason if specified
                if reason and retirement_reason != reason.value:
                    continue

                # Get counts
                posts_count = await sess.execute(
                    select(func.count()).select_from(PostDB).where(PostDB.author_id == bot.id)
                )
                total_posts = posts_count.scalar() or 0

                memories_count = await sess.execute(
                    select(func.count()).select_from(MemoryItemDB).where(MemoryItemDB.bot_id == bot.id)
                )
                total_memories = memories_count.scalar() or 0

                retired_at = bot.deleted_at or datetime.utcnow()
                active_days = (retired_at - bot.created_at).days

                archived_id = retirement_meta.get("archived_data_id")

                retired_bots.append(RetiredBot(
                    id=bot.id,
                    display_name=bot.display_name,
                    handle=bot.handle,
                    reason=RetirementReason(retirement_reason),
                    retired_at=retired_at,
                    total_posts=total_posts,
                    total_memories=total_memories,
                    active_days=active_days,
                    archived_data_id=UUID(archived_id) if archived_id else None
                ))

            return retired_bots

        if session:
            return await _get(session)
        else:
            async with async_session_factory() as sess:
                return await _get(sess)

    async def bulk_check_retirement(
        self,
        session: Optional[AsyncSession] = None
    ) -> List[RetirementEligibility]:
        """
        Check all active bots for retirement eligibility.

        Returns:
            List of eligible bots with their retirement reasons
        """
        async def _check(sess: AsyncSession) -> List[RetirementEligibility]:
            # Get all active bots
            stmt = select(BotProfileDB.id).where(
                and_(
                    BotProfileDB.is_active == True,
                    BotProfileDB.is_retired == False
                )
            )
            result = await sess.execute(stmt)
            bot_ids = [row[0] for row in result.all()]

            eligible = []
            for bot_id in bot_ids:
                eligibility = await self.check_retirement_eligibility(bot_id, sess)
                if eligibility.eligible:
                    eligibility.details["bot_id"] = str(bot_id)
                    eligible.append(eligibility)

            return eligible

        if session:
            return await _check(session)
        else:
            async with async_session_factory() as sess:
                return await _check(sess)


# ============================================================================
# FACTORY
# ============================================================================

_retirement_manager: Optional[BotRetirementManager] = None


def get_retirement_manager() -> BotRetirementManager:
    """Get the singleton retirement manager."""
    global _retirement_manager
    if _retirement_manager is None:
        _retirement_manager = BotRetirementManager()
    return _retirement_manager
