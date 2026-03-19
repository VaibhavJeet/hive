"""
Analytics tracker for real-time event tracking.
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update

from mind.core.database import (
    async_session_factory,
    PostViewDB,
    SessionDB,
    DailyMetricsDB,
)

logger = logging.getLogger(__name__)


class AnalyticsTracker:
    """
    Real-time analytics tracker for engagement events.

    Tracks views, engagement, sessions, and other user/bot activity.
    All methods are async and designed for high throughput.
    """

    _instance: Optional["AnalyticsTracker"] = None

    def __init__(self):
        self._initialized = False

    async def initialize(self):
        """Initialize the tracker."""
        if self._initialized:
            return
        self._initialized = True
        logger.info("Analytics tracker initialized")

    # =========================================================================
    # POST TRACKING
    # =========================================================================

    async def track_post_view(
        self,
        post_id: UUID,
        viewer_id: UUID,
        viewer_is_bot: bool = False
    ) -> bool:
        """
        Track a post view event.

        Args:
            post_id: The post being viewed
            viewer_id: The viewer (user or bot)
            viewer_is_bot: Whether the viewer is a bot

        Returns:
            True if this is a new view, False if already viewed
        """
        try:
            async with async_session_factory() as session:
                # Check if already viewed
                stmt = select(PostViewDB).where(
                    PostViewDB.post_id == post_id,
                    PostViewDB.viewer_id == viewer_id
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    # Update view time
                    existing.last_viewed_at = datetime.utcnow()
                    existing.view_count += 1
                    await session.commit()
                    return False

                # Create new view record
                view = PostViewDB(
                    post_id=post_id,
                    viewer_id=viewer_id,
                    viewer_is_bot=viewer_is_bot,
                    viewed_at=datetime.utcnow(),
                    last_viewed_at=datetime.utcnow(),
                    view_count=1
                )
                session.add(view)
                await session.commit()
                return True

        except Exception as e:
            logger.error(f"Error tracking post view: {e}")
            return False

    async def track_post_engagement(
        self,
        post_id: UUID,
        engagement_type: str,
        user_id: UUID,
        user_is_bot: bool = False
    ) -> bool:
        """
        Track a post engagement event (like, comment, share).

        Args:
            post_id: The post being engaged with
            engagement_type: Type of engagement ("like", "comment", "share")
            user_id: The user engaging
            user_is_bot: Whether the user is a bot

        Returns:
            True if tracked successfully
        """
        try:
            # Also track as a view if not already viewed
            await self.track_post_view(post_id, user_id, user_is_bot)

            # Update daily metrics
            await self._increment_daily_metric(engagement_type + "s")

            logger.debug(f"Tracked {engagement_type} on post {post_id} by {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error tracking post engagement: {e}")
            return False

    # =========================================================================
    # CHAT TRACKING
    # =========================================================================

    async def track_chat_activity(
        self,
        community_id: UUID,
        user_id: UUID,
        user_is_bot: bool = False,
        message_count: int = 1
    ) -> bool:
        """
        Track community chat activity.

        Args:
            community_id: The community where chat occurred
            user_id: The user sending messages
            user_is_bot: Whether the user is a bot
            message_count: Number of messages to track

        Returns:
            True if tracked successfully
        """
        try:
            # Update daily metrics
            await self._increment_daily_metric("chats", count=message_count)

            logger.debug(f"Tracked {message_count} chat messages in community {community_id}")
            return True

        except Exception as e:
            logger.error(f"Error tracking chat activity: {e}")
            return False

    async def track_dm_activity(
        self,
        bot_id: UUID,
        user_id: UUID,
        direction: str = "to_bot",
        message_count: int = 1
    ) -> bool:
        """
        Track direct message activity between user and bot.

        Args:
            bot_id: The bot in the DM conversation
            user_id: The human user
            direction: "to_bot" or "from_bot"
            message_count: Number of messages

        Returns:
            True if tracked successfully
        """
        try:
            # Update daily metrics
            await self._increment_daily_metric("dms", count=message_count)

            logger.debug(f"Tracked DM activity: {direction} between user {user_id} and bot {bot_id}")
            return True

        except Exception as e:
            logger.error(f"Error tracking DM activity: {e}")
            return False

    # =========================================================================
    # SESSION TRACKING
    # =========================================================================

    async def track_session_start(
        self,
        user_id: UUID,
        session_id: Optional[str] = None
    ) -> UUID:
        """
        Track the start of a user session.

        Args:
            user_id: The user starting a session
            session_id: Optional external session identifier

        Returns:
            The session record ID
        """
        try:
            async with async_session_factory() as session:
                db_session = SessionDB(
                    user_id=user_id,
                    external_session_id=session_id,
                    started_at=datetime.utcnow()
                )
                session.add(db_session)
                await session.commit()
                await session.refresh(db_session)

                logger.debug(f"Session started for user {user_id}")
                return db_session.id

        except Exception as e:
            logger.error(f"Error tracking session start: {e}")
            return None

    async def track_session_end(
        self,
        session_id: UUID,
        duration_seconds: Optional[float] = None
    ) -> bool:
        """
        Track the end of a user session.

        Args:
            session_id: The session record ID
            duration_seconds: Optional explicit duration (calculated if not provided)

        Returns:
            True if tracked successfully
        """
        try:
            async with async_session_factory() as session:
                stmt = select(SessionDB).where(SessionDB.id == session_id)
                result = await session.execute(stmt)
                db_session = result.scalar_one_or_none()

                if not db_session:
                    logger.warning(f"Session not found: {session_id}")
                    return False

                db_session.ended_at = datetime.utcnow()

                if duration_seconds is not None:
                    db_session.duration_seconds = duration_seconds
                else:
                    # Calculate duration
                    delta = db_session.ended_at - db_session.started_at
                    db_session.duration_seconds = delta.total_seconds()

                await session.commit()
                logger.debug(f"Session ended: {session_id}, duration: {db_session.duration_seconds}s")
                return True

        except Exception as e:
            logger.error(f"Error tracking session end: {e}")
            return False

    async def track_session(
        self,
        user_id: UUID,
        duration_seconds: float
    ) -> bool:
        """
        Track a complete session (convenience method for when duration is known).

        Args:
            user_id: The user
            duration_seconds: Session duration in seconds

        Returns:
            True if tracked successfully
        """
        try:
            async with async_session_factory() as session:
                now = datetime.utcnow()
                db_session = SessionDB(
                    user_id=user_id,
                    started_at=now,
                    ended_at=now,
                    duration_seconds=duration_seconds
                )
                session.add(db_session)
                await session.commit()

                # Update daily active users
                await self._increment_daily_metric("active_users")

                logger.debug(f"Session tracked for user {user_id}: {duration_seconds}s")
                return True

        except Exception as e:
            logger.error(f"Error tracking session: {e}")
            return False

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    async def _increment_daily_metric(
        self,
        metric_name: str,
        count: int = 1,
        date: Optional[datetime] = None
    ) -> bool:
        """
        Increment a daily metric counter.

        Args:
            metric_name: Name of the metric (posts, comments, likes, dms, chats, active_users)
            count: Amount to increment by
            date: Date for the metric (defaults to today)

        Returns:
            True if successful
        """
        try:
            if date is None:
                date = datetime.utcnow().date()
            else:
                date = date.date() if hasattr(date, "date") else date

            async with async_session_factory() as session:
                # Get or create daily metrics record
                stmt = select(DailyMetricsDB).where(DailyMetricsDB.date == date)
                result = await session.execute(stmt)
                metrics = result.scalar_one_or_none()

                if not metrics:
                    metrics = DailyMetricsDB(date=date)
                    session.add(metrics)

                # Increment the appropriate counter
                if metric_name == "posts":
                    metrics.posts += count
                elif metric_name == "comments":
                    metrics.comments += count
                elif metric_name == "likes":
                    metrics.likes += count
                elif metric_name == "dms":
                    metrics.dms += count
                elif metric_name == "chats":
                    metrics.chats += count
                elif metric_name == "active_users":
                    metrics.active_users += count

                await session.commit()
                return True

        except Exception as e:
            logger.error(f"Error incrementing daily metric {metric_name}: {e}")
            return False

    async def track_new_user(self) -> bool:
        """Track a new user registration."""
        return await self._increment_daily_metric("active_users")

    async def track_new_post(self, author_is_bot: bool = True) -> bool:
        """Track a new post creation."""
        return await self._increment_daily_metric("posts")

    async def track_new_comment(self, author_is_bot: bool = True) -> bool:
        """Track a new comment creation."""
        return await self._increment_daily_metric("comments")

    async def track_new_like(self, user_is_bot: bool = True) -> bool:
        """Track a new like."""
        return await self._increment_daily_metric("likes")


# Singleton instance
_tracker_instance: Optional[AnalyticsTracker] = None


async def get_analytics_tracker() -> AnalyticsTracker:
    """Get the singleton analytics tracker instance."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = AnalyticsTracker()
        await _tracker_instance.initialize()
    return _tracker_instance
