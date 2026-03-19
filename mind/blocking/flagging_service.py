"""
Flagging Service for AI Community Companions.
Handles behavior flagging and auto-moderation of bots.
"""

from datetime import datetime
from typing import List, Optional, Literal
from uuid import UUID
from enum import Enum

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import (
    async_session_factory, BotBehaviorFlagDB, BotProfileDB, AppUserDB
)


class FlagType(str, Enum):
    """Types of behavior flags."""
    INAPPROPRIATE = "inappropriate"
    SPAM = "spam"
    HARASSMENT = "harassment"
    IMPERSONATION = "impersonation"
    MISINFORMATION = "misinformation"
    OTHER = "other"


class FlagStatus(str, Enum):
    """Status of a behavior flag."""
    PENDING = "pending"
    REVIEWED = "reviewed"
    RESOLVED = "resolved"


# Auto-pause threshold - bots with this many pending flags get auto-paused
AUTO_PAUSE_THRESHOLD = 5


class FlaggingService:
    """
    Service for managing bot behavior flags.

    Provides methods to:
    - Flag bot behavior
    - Get flags for a bot
    - Resolve flags (admin)
    - Get flagged bots (admin)
    - Auto-pause bots with excessive flags
    """

    def __init__(self, auto_pause_threshold: int = AUTO_PAUSE_THRESHOLD):
        self.auto_pause_threshold = auto_pause_threshold

    async def flag_behavior(
        self,
        bot_id: UUID,
        reporter_id: UUID,
        flag_type: str,
        description: Optional[str] = None,
        content_type: Optional[str] = None,
        content_id: Optional[UUID] = None
    ) -> dict:
        """
        Flag a bot's behavior.

        Args:
            bot_id: The bot being flagged
            reporter_id: The user reporting the behavior
            flag_type: Type of flag (inappropriate, spam, harassment, other)
            description: Optional description of the issue
            content_type: Optional type of content being flagged
            content_id: Optional ID of the specific content

        Returns:
            Dict with flag details and any auto-moderation actions
        """
        # Validate flag type
        try:
            FlagType(flag_type)
        except ValueError:
            flag_type = FlagType.OTHER.value

        async with async_session_factory() as session:
            # Check if bot exists
            bot_stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
            bot_result = await session.execute(bot_stmt)
            bot = bot_result.scalar_one_or_none()

            if not bot:
                return {"status": "error", "message": "Bot not found"}

            # Check if reporter exists
            reporter_stmt = select(AppUserDB).where(AppUserDB.id == reporter_id)
            reporter_result = await session.execute(reporter_stmt)
            reporter = reporter_result.scalar_one_or_none()

            if not reporter:
                return {"status": "error", "message": "Reporter not found"}

            # Create flag record
            flag = BotBehaviorFlagDB(
                bot_id=bot_id,
                reporter_id=reporter_id,
                flag_type=flag_type,
                description=description,
                context_content_type=content_type,
                context_content_id=content_id,
                status=FlagStatus.PENDING.value
            )
            session.add(flag)
            await session.commit()
            await session.refresh(flag)

            result = {
                "status": "flagged",
                "flag_id": str(flag.id),
                "bot_id": str(bot_id),
                "bot_name": bot.display_name,
                "flag_type": flag_type,
                "created_at": flag.created_at
            }

            # Check if auto-pause should be triggered
            pending_count = await self._get_pending_flag_count(session, bot_id)
            if pending_count >= self.auto_pause_threshold and not bot.is_paused:
                bot.is_paused = True
                bot.paused_at = datetime.utcnow()
                # System auto-pause
                await session.commit()
                result["auto_paused"] = True
                result["pending_flag_count"] = pending_count
                result["message"] = f"Bot has been auto-paused due to {pending_count} pending flags"

            return result

    async def _get_pending_flag_count(self, session: AsyncSession, bot_id: UUID) -> int:
        """Get count of pending flags for a bot."""
        stmt = select(func.count(BotBehaviorFlagDB.id)).where(
            BotBehaviorFlagDB.bot_id == bot_id,
            BotBehaviorFlagDB.status == FlagStatus.PENDING.value
        )
        result = await session.execute(stmt)
        return result.scalar() or 0

    async def get_flags(
        self,
        bot_id: UUID,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[dict]:
        """
        Get flags for a bot.

        Args:
            bot_id: The bot to get flags for
            status: Optional status filter
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            List of flag details
        """
        async with async_session_factory() as session:
            stmt = (
                select(BotBehaviorFlagDB, AppUserDB)
                .join(AppUserDB, BotBehaviorFlagDB.reporter_id == AppUserDB.id)
                .where(BotBehaviorFlagDB.bot_id == bot_id)
                .order_by(BotBehaviorFlagDB.created_at.desc())
                .limit(limit)
                .offset(offset)
            )

            if status:
                stmt = stmt.where(BotBehaviorFlagDB.status == status)

            result = await session.execute(stmt)
            rows = result.all()

            flags = []
            for flag, reporter in rows:
                flags.append({
                    "id": flag.id,
                    "flag_type": flag.flag_type,
                    "description": flag.description,
                    "status": flag.status,
                    "created_at": flag.created_at,
                    "reporter": {
                        "id": reporter.id,
                        "display_name": reporter.display_name
                    },
                    "content_type": flag.context_content_type,
                    "content_id": flag.context_content_id,
                    "resolution": flag.resolution,
                    "resolved_at": flag.resolved_at
                })

            return flags

    async def resolve_flag(
        self,
        flag_id: UUID,
        resolution: str,
        admin_id: UUID
    ) -> dict:
        """
        Resolve a behavior flag.

        Args:
            flag_id: The flag to resolve
            resolution: Resolution description
            admin_id: The admin resolving the flag

        Returns:
            Dict with resolution status
        """
        async with async_session_factory() as session:
            # Verify admin
            admin_stmt = select(AppUserDB).where(
                AppUserDB.id == admin_id,
                AppUserDB.is_admin == True
            )
            admin_result = await session.execute(admin_stmt)
            admin = admin_result.scalar_one_or_none()

            if not admin:
                return {"status": "error", "message": "Unauthorized - admin access required"}

            # Get flag
            flag_stmt = select(BotBehaviorFlagDB).where(BotBehaviorFlagDB.id == flag_id)
            flag_result = await session.execute(flag_stmt)
            flag = flag_result.scalar_one_or_none()

            if not flag:
                return {"status": "error", "message": "Flag not found"}

            if flag.status == FlagStatus.RESOLVED.value:
                return {"status": "already_resolved", "resolved_at": flag.resolved_at}

            # Update flag
            flag.status = FlagStatus.RESOLVED.value
            flag.resolution = resolution
            flag.resolved_by = admin_id
            flag.resolved_at = datetime.utcnow()

            await session.commit()

            return {
                "status": "resolved",
                "flag_id": str(flag_id),
                "resolution": resolution,
                "resolved_at": flag.resolved_at,
                "resolved_by": str(admin_id)
            }

    async def get_flagged_bots(
        self,
        min_flags: int = 3,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[dict]:
        """
        Get bots with multiple flags.

        Args:
            min_flags: Minimum number of flags
            status: Optional status filter
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            List of flagged bot details with flag counts
        """
        async with async_session_factory() as session:
            # Build subquery for flag counts
            flag_count_subq = (
                select(
                    BotBehaviorFlagDB.bot_id,
                    func.count(BotBehaviorFlagDB.id).label("flag_count")
                )
                .group_by(BotBehaviorFlagDB.bot_id)
            )

            if status:
                flag_count_subq = flag_count_subq.where(
                    BotBehaviorFlagDB.status == status
                )

            flag_count_subq = flag_count_subq.having(
                func.count(BotBehaviorFlagDB.id) >= min_flags
            ).subquery()

            # Join with bot profiles
            stmt = (
                select(BotProfileDB, flag_count_subq.c.flag_count)
                .join(flag_count_subq, BotProfileDB.id == flag_count_subq.c.bot_id)
                .order_by(flag_count_subq.c.flag_count.desc())
                .limit(limit)
                .offset(offset)
            )

            result = await session.execute(stmt)
            rows = result.all()

            flagged_bots = []
            for bot, flag_count in rows:
                flagged_bots.append({
                    "id": bot.id,
                    "display_name": bot.display_name,
                    "handle": bot.handle,
                    "avatar_seed": bot.avatar_seed,
                    "is_paused": bot.is_paused,
                    "is_active": bot.is_active,
                    "flag_count": flag_count,
                    "created_at": bot.created_at,
                    "last_active": bot.last_active
                })

            return flagged_bots

    async def get_flag_statistics(self, bot_id: Optional[UUID] = None) -> dict:
        """
        Get flag statistics.

        Args:
            bot_id: Optional specific bot to get stats for

        Returns:
            Dict with flag statistics
        """
        async with async_session_factory() as session:
            base_stmt = select(BotBehaviorFlagDB)
            if bot_id:
                base_stmt = base_stmt.where(BotBehaviorFlagDB.bot_id == bot_id)

            # Total flags
            total_stmt = select(func.count(BotBehaviorFlagDB.id))
            if bot_id:
                total_stmt = total_stmt.where(BotBehaviorFlagDB.bot_id == bot_id)
            total_result = await session.execute(total_stmt)
            total_flags = total_result.scalar() or 0

            # By status
            status_counts = {}
            for status in FlagStatus:
                status_stmt = select(func.count(BotBehaviorFlagDB.id)).where(
                    BotBehaviorFlagDB.status == status.value
                )
                if bot_id:
                    status_stmt = status_stmt.where(BotBehaviorFlagDB.bot_id == bot_id)
                status_result = await session.execute(status_stmt)
                status_counts[status.value] = status_result.scalar() or 0

            # By type
            type_counts = {}
            for flag_type in FlagType:
                type_stmt = select(func.count(BotBehaviorFlagDB.id)).where(
                    BotBehaviorFlagDB.flag_type == flag_type.value
                )
                if bot_id:
                    type_stmt = type_stmt.where(BotBehaviorFlagDB.bot_id == bot_id)
                type_result = await session.execute(type_stmt)
                type_counts[flag_type.value] = type_result.scalar() or 0

            return {
                "total_flags": total_flags,
                "by_status": status_counts,
                "by_type": type_counts
            }

    async def unpause_bot_if_resolved(self, bot_id: UUID) -> dict:
        """
        Check if all flags are resolved and unpause bot if so.

        Args:
            bot_id: The bot to check

        Returns:
            Dict with unpause status
        """
        async with async_session_factory() as session:
            # Get bot
            bot_stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
            bot_result = await session.execute(bot_stmt)
            bot = bot_result.scalar_one_or_none()

            if not bot:
                return {"status": "error", "message": "Bot not found"}

            if not bot.is_paused:
                return {"status": "not_paused"}

            # Check pending flags
            pending_count = await self._get_pending_flag_count(session, bot_id)

            if pending_count > 0:
                return {
                    "status": "still_flagged",
                    "pending_flags": pending_count
                }

            # Unpause the bot
            bot.is_paused = False
            bot.paused_at = None
            bot.paused_by = None
            await session.commit()

            return {
                "status": "unpaused",
                "bot_id": str(bot_id)
            }


# Singleton instance
flagging_service = FlaggingService()
