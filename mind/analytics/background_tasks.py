"""
Background tasks for analytics aggregation.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func

from mind.core.database import (
    async_session_factory,
    DailyMetricsDB,
    PostDB,
    PostCommentDB,
    PostLikeDB,
    DirectMessageDB,
    CommunityChatMessageDB,
    AppUserDB,
    BotProfileDB,
)

logger = logging.getLogger(__name__)


class DailyMetricsAggregator:
    """
    Background service to aggregate daily metrics.

    Runs periodically to compute and store daily aggregate metrics
    for efficient retrieval and historical analysis.
    """

    def __init__(self, interval_hours: int = 1):
        """
        Initialize the aggregator.

        Args:
            interval_hours: Hours between aggregation runs
        """
        self.interval_hours = interval_hours
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the background aggregation task."""
        if self._running:
            logger.warning("Daily metrics aggregator already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Daily metrics aggregator started")

    async def stop(self):
        """Stop the background aggregation task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Daily metrics aggregator stopped")

    async def _run_loop(self):
        """Main loop for periodic aggregation."""
        while self._running:
            try:
                await self.aggregate_daily_metrics()
                await asyncio.sleep(self.interval_hours * 3600)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in daily metrics aggregation: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error

    async def aggregate_daily_metrics(self, date: Optional[datetime] = None):
        """
        Aggregate metrics for a specific date.

        Args:
            date: Date to aggregate (defaults to today)
        """
        if date is None:
            date = datetime.utcnow().date()
        else:
            date = date.date() if hasattr(date, "date") else date

        day_start = datetime.combine(date, datetime.min.time())
        day_end = datetime.combine(date, datetime.max.time())

        logger.info(f"Aggregating metrics for {date}")

        async with async_session_factory() as session:
            # Count posts
            posts_stmt = select(func.count(PostDB.id)).where(
                PostDB.created_at >= day_start,
                PostDB.created_at <= day_end,
                PostDB.is_deleted == False
            )
            posts_count = (await session.execute(posts_stmt)).scalar() or 0

            # Count comments
            comments_stmt = select(func.count(PostCommentDB.id)).where(
                PostCommentDB.created_at >= day_start,
                PostCommentDB.created_at <= day_end,
                PostCommentDB.is_deleted == False
            )
            comments_count = (await session.execute(comments_stmt)).scalar() or 0

            # Count likes
            likes_stmt = select(func.count(PostLikeDB.id)).where(
                PostLikeDB.created_at >= day_start,
                PostLikeDB.created_at <= day_end
            )
            likes_count = (await session.execute(likes_stmt)).scalar() or 0

            # Count DMs
            dms_stmt = select(func.count(DirectMessageDB.id)).where(
                DirectMessageDB.created_at >= day_start,
                DirectMessageDB.created_at <= day_end
            )
            dms_count = (await session.execute(dms_stmt)).scalar() or 0

            # Count chat messages
            chats_stmt = select(func.count(CommunityChatMessageDB.id)).where(
                CommunityChatMessageDB.created_at >= day_start,
                CommunityChatMessageDB.created_at <= day_end,
                CommunityChatMessageDB.is_deleted == False
            )
            chats_count = (await session.execute(chats_stmt)).scalar() or 0

            # Count active users
            active_users_stmt = select(func.count(AppUserDB.id)).where(
                AppUserDB.last_active >= day_start,
                AppUserDB.last_active <= day_end
            )
            active_users_count = (await session.execute(active_users_stmt)).scalar() or 0

            # Count new users
            new_users_stmt = select(func.count(AppUserDB.id)).where(
                AppUserDB.created_at >= day_start,
                AppUserDB.created_at <= day_end
            )
            new_users_count = (await session.execute(new_users_stmt)).scalar() or 0

            # Count active bots
            active_bots_stmt = select(func.count(BotProfileDB.id)).where(
                BotProfileDB.last_active >= day_start,
                BotProfileDB.last_active <= day_end,
                BotProfileDB.is_active == True
            )
            active_bots_count = (await session.execute(active_bots_stmt)).scalar() or 0

            # Count bot posts
            bot_posts_stmt = select(func.count(PostDB.id)).where(
                PostDB.created_at >= day_start,
                PostDB.created_at <= day_end,
                PostDB.is_deleted == False
            )
            bot_posts_count = (await session.execute(bot_posts_stmt)).scalar() or 0

            # Count bot comments
            bot_comments_stmt = select(func.count(PostCommentDB.id)).where(
                PostCommentDB.created_at >= day_start,
                PostCommentDB.created_at <= day_end,
                PostCommentDB.is_deleted == False,
                PostCommentDB.is_bot == True
            )
            bot_comments_count = (await session.execute(bot_comments_stmt)).scalar() or 0

            # Get or create daily metrics record
            existing_stmt = select(DailyMetricsDB).where(DailyMetricsDB.date == day_start)
            result = await session.execute(existing_stmt)
            metrics = result.scalar_one_or_none()

            if metrics:
                # Update existing record
                metrics.posts = posts_count
                metrics.comments = comments_count
                metrics.likes = likes_count
                metrics.dms = dms_count
                metrics.chats = chats_count
                metrics.active_users = active_users_count
                metrics.new_users = new_users_count
                metrics.active_bots = active_bots_count
                metrics.bot_posts = bot_posts_count
                metrics.bot_comments = bot_comments_count
                metrics.updated_at = datetime.utcnow()
            else:
                # Create new record
                metrics = DailyMetricsDB(
                    date=day_start,
                    posts=posts_count,
                    comments=comments_count,
                    likes=likes_count,
                    dms=dms_count,
                    chats=chats_count,
                    active_users=active_users_count,
                    new_users=new_users_count,
                    active_bots=active_bots_count,
                    bot_posts=bot_posts_count,
                    bot_comments=bot_comments_count
                )
                session.add(metrics)

            await session.commit()
            logger.info(
                f"Daily metrics for {date}: "
                f"posts={posts_count}, comments={comments_count}, likes={likes_count}, "
                f"active_users={active_users_count}"
            )

    async def backfill_metrics(self, days: int = 30):
        """
        Backfill daily metrics for the past N days.

        Args:
            days: Number of days to backfill
        """
        logger.info(f"Backfilling metrics for past {days} days")

        for i in range(days):
            date = datetime.utcnow().date() - timedelta(days=i)
            await self.aggregate_daily_metrics(datetime.combine(date, datetime.min.time()))

        logger.info("Backfill complete")


# Singleton instance
_aggregator_instance: Optional[DailyMetricsAggregator] = None


async def get_daily_metrics_aggregator() -> DailyMetricsAggregator:
    """Get the singleton daily metrics aggregator instance."""
    global _aggregator_instance
    if _aggregator_instance is None:
        _aggregator_instance = DailyMetricsAggregator()
    return _aggregator_instance


async def start_analytics_background_tasks():
    """Start all analytics background tasks."""
    aggregator = await get_daily_metrics_aggregator()
    await aggregator.start()


async def stop_analytics_background_tasks():
    """Stop all analytics background tasks."""
    aggregator = await get_daily_metrics_aggregator()
    await aggregator.stop()
