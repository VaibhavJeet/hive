"""
Analytics aggregator for computing aggregate metrics and reports.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, desc, and_

from mind.core.database import (
    async_session_factory,
    BotProfileDB,
    AppUserDB,
    PostDB,
    PostLikeDB,
    PostCommentDB,
    CommunityChatMessageDB,
    DirectMessageDB,
    CommunityDB,
    PostViewDB,
    SessionDB,
    DailyMetricsDB,
)
from mind.analytics.models import (
    EngagementMetrics,
    BotPerformance,
    UserActivity,
    TimeSeriesData,
    PlatformMetrics,
    TrendingContent,
)

logger = logging.getLogger(__name__)


class AnalyticsAggregator:
    """
    Analytics aggregator for computing aggregate metrics.

    Provides methods to compute performance metrics for bots, users,
    and the platform as a whole.
    """

    _instance: Optional["AnalyticsAggregator"] = None

    def __init__(self):
        self._initialized = False

    async def initialize(self):
        """Initialize the aggregator."""
        if self._initialized:
            return
        self._initialized = True
        logger.info("Analytics aggregator initialized")

    # =========================================================================
    # BOT PERFORMANCE
    # =========================================================================

    async def get_bot_performance(
        self,
        bot_id: UUID,
        days: int = 7
    ) -> BotPerformance:
        """
        Get performance metrics for a specific bot.

        Args:
            bot_id: The bot to analyze
            days: Number of days to analyze (default 7)

        Returns:
            BotPerformance dataclass with metrics
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        async with async_session_factory() as session:
            # Get bot info
            bot_stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
            bot_result = await session.execute(bot_stmt)
            bot = bot_result.scalar_one_or_none()

            if not bot:
                return BotPerformance(bot_id=bot_id, period_days=days)

            # Count posts created
            posts_stmt = select(func.count(PostDB.id)).where(
                PostDB.author_id == bot_id,
                PostDB.created_at >= cutoff
            )
            posts_result = await session.execute(posts_stmt)
            posts_count = posts_result.scalar() or 0

            # Count comments created
            comments_stmt = select(func.count(PostCommentDB.id)).where(
                PostCommentDB.author_id == bot_id,
                PostCommentDB.created_at >= cutoff,
                PostCommentDB.is_bot == True
            )
            comments_result = await session.execute(comments_stmt)
            comments_count = comments_result.scalar() or 0

            # Count chat messages sent
            chat_stmt = select(func.count(CommunityChatMessageDB.id)).where(
                CommunityChatMessageDB.author_id == bot_id,
                CommunityChatMessageDB.created_at >= cutoff,
                CommunityChatMessageDB.is_bot == True
            )
            chat_result = await session.execute(chat_stmt)
            chat_count = chat_result.scalar() or 0

            # Count DM responses
            dm_stmt = select(func.count(DirectMessageDB.id)).where(
                DirectMessageDB.sender_id == bot_id,
                DirectMessageDB.created_at >= cutoff,
                DirectMessageDB.sender_is_bot == True
            )
            dm_result = await session.execute(dm_stmt)
            dm_count = dm_result.scalar() or 0

            # Get likes received on posts
            likes_subq = (
                select(PostDB.id)
                .where(PostDB.author_id == bot_id)
                .subquery()
            )
            likes_stmt = select(func.count(PostLikeDB.id)).where(
                PostLikeDB.post_id.in_(select(likes_subq)),
                PostLikeDB.created_at >= cutoff
            )
            likes_result = await session.execute(likes_stmt)
            likes_received = likes_result.scalar() or 0

            # Get comments received on posts
            comments_received_stmt = select(func.count(PostCommentDB.id)).where(
                PostCommentDB.post_id.in_(select(likes_subq)),
                PostCommentDB.created_at >= cutoff,
                PostCommentDB.author_id != bot_id  # Exclude self-replies
            )
            comments_received_result = await session.execute(comments_received_stmt)
            comments_received = comments_received_result.scalar() or 0

            # Calculate average engagement per post
            avg_engagement = 0.0
            if posts_count > 0:
                avg_engagement = (likes_received + comments_received) / posts_count

            return BotPerformance(
                bot_id=bot_id,
                bot_handle=bot.handle,
                bot_name=bot.display_name,
                posts_created=posts_count,
                comments_created=comments_count,
                chat_messages_sent=chat_count,
                dm_responses=dm_count,
                total_likes_received=likes_received,
                total_comments_received=comments_received,
                avg_engagement_per_post=round(avg_engagement, 2),
                last_active=bot.last_active,
                period_days=days
            )

    async def get_bot_comparison(
        self,
        limit: int = 20,
        days: int = 7
    ) -> List[BotPerformance]:
        """
        Get performance comparison for all active bots.

        Args:
            limit: Maximum number of bots to return
            days: Analysis period in days

        Returns:
            List of BotPerformance sorted by engagement
        """
        async with async_session_factory() as session:
            # Get active bots
            bots_stmt = (
                select(BotProfileDB)
                .where(BotProfileDB.is_active == True)
                .order_by(desc(BotProfileDB.last_active))
                .limit(limit)
            )
            bots_result = await session.execute(bots_stmt)
            bots = bots_result.scalars().all()

        # Get performance for each bot
        performances = []
        for bot in bots:
            perf = await self.get_bot_performance(bot.id, days)
            performances.append(perf)

        # Sort by engagement
        performances.sort(
            key=lambda p: p.total_likes_received + p.total_comments_received,
            reverse=True
        )

        return performances

    # =========================================================================
    # USER ENGAGEMENT
    # =========================================================================

    async def get_user_engagement(
        self,
        user_id: UUID,
        days: int = 7
    ) -> UserActivity:
        """
        Get engagement metrics for a user.

        Args:
            user_id: The user to analyze
            days: Analysis period in days

        Returns:
            UserActivity dataclass with metrics
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        async with async_session_factory() as session:
            # Get user info
            user_stmt = select(AppUserDB).where(AppUserDB.id == user_id)
            user_result = await session.execute(user_stmt)
            user = user_result.scalar_one_or_none()

            if not user:
                return UserActivity(user_id=user_id, period_days=days)

            # Count likes given
            likes_stmt = select(func.count(PostLikeDB.id)).where(
                PostLikeDB.user_id == user_id,
                PostLikeDB.is_bot == False,
                PostLikeDB.created_at >= cutoff
            )
            likes_result = await session.execute(likes_stmt)
            likes_given = likes_result.scalar() or 0

            # Count comments made
            comments_stmt = select(func.count(PostCommentDB.id)).where(
                PostCommentDB.author_id == user_id,
                PostCommentDB.is_bot == False,
                PostCommentDB.created_at >= cutoff
            )
            comments_result = await session.execute(comments_stmt)
            comments_made = comments_result.scalar() or 0

            # Count chat messages sent
            chat_stmt = select(func.count(CommunityChatMessageDB.id)).where(
                CommunityChatMessageDB.author_id == user_id,
                CommunityChatMessageDB.is_bot == False,
                CommunityChatMessageDB.created_at >= cutoff
            )
            chat_result = await session.execute(chat_stmt)
            chat_messages = chat_result.scalar() or 0

            # Count DMs sent
            dm_stmt = select(func.count(DirectMessageDB.id)).where(
                DirectMessageDB.sender_id == user_id,
                DirectMessageDB.sender_is_bot == False,
                DirectMessageDB.created_at >= cutoff
            )
            dm_result = await session.execute(dm_stmt)
            dm_messages = dm_result.scalar() or 0

            # Count unique bots interacted with
            bots_interacted_stmt = select(func.count(func.distinct(DirectMessageDB.receiver_id))).where(
                DirectMessageDB.sender_id == user_id,
                DirectMessageDB.sender_is_bot == False,
                DirectMessageDB.created_at >= cutoff
            )
            bots_result = await session.execute(bots_interacted_stmt)
            bots_interacted = bots_result.scalar() or 0

            # Get session metrics
            sessions_stmt = select(
                func.count(SessionDB.id),
                func.sum(SessionDB.duration_seconds),
                func.avg(SessionDB.duration_seconds)
            ).where(
                SessionDB.user_id == user_id,
                SessionDB.started_at >= cutoff
            )
            sessions_result = await session.execute(sessions_stmt)
            session_row = sessions_result.first()
            total_sessions = session_row[0] or 0
            total_session_time = session_row[1] or 0.0
            avg_session_duration = session_row[2] or 0.0

            return UserActivity(
                user_id=user_id,
                display_name=user.display_name,
                likes_given=likes_given,
                comments_made=comments_made,
                chat_messages_sent=chat_messages,
                dm_messages_sent=dm_messages,
                bots_interacted_with=bots_interacted,
                total_sessions=total_sessions,
                total_session_time=float(total_session_time),
                avg_session_duration=float(avg_session_duration),
                first_seen=user.created_at,
                last_seen=user.last_active,
                period_days=days
            )

    # =========================================================================
    # PLATFORM METRICS
    # =========================================================================

    async def get_platform_metrics(
        self,
        days: int = 7
    ) -> PlatformMetrics:
        """
        Get platform-wide metrics.

        Args:
            days: Analysis period in days

        Returns:
            PlatformMetrics dataclass
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        async with async_session_factory() as session:
            # User counts
            total_users_stmt = select(func.count(AppUserDB.id))
            total_users = (await session.execute(total_users_stmt)).scalar() or 0

            active_users_today_stmt = select(func.count(AppUserDB.id)).where(
                AppUserDB.last_active >= today_start
            )
            active_users_today = (await session.execute(active_users_today_stmt)).scalar() or 0

            active_users_week_stmt = select(func.count(AppUserDB.id)).where(
                AppUserDB.last_active >= cutoff
            )
            active_users_week = (await session.execute(active_users_week_stmt)).scalar() or 0

            new_users_today_stmt = select(func.count(AppUserDB.id)).where(
                AppUserDB.created_at >= today_start
            )
            new_users_today = (await session.execute(new_users_today_stmt)).scalar() or 0

            new_users_week_stmt = select(func.count(AppUserDB.id)).where(
                AppUserDB.created_at >= cutoff
            )
            new_users_week = (await session.execute(new_users_week_stmt)).scalar() or 0

            # Bot counts
            total_bots_stmt = select(func.count(BotProfileDB.id))
            total_bots = (await session.execute(total_bots_stmt)).scalar() or 0

            active_bots_stmt = select(func.count(BotProfileDB.id)).where(
                BotProfileDB.is_active == True,
                BotProfileDB.is_paused == False
            )
            active_bots = (await session.execute(active_bots_stmt)).scalar() or 0

            paused_bots_stmt = select(func.count(BotProfileDB.id)).where(
                BotProfileDB.is_paused == True
            )
            paused_bots = (await session.execute(paused_bots_stmt)).scalar() or 0

            retired_bots_stmt = select(func.count(BotProfileDB.id)).where(
                BotProfileDB.is_retired == True
            )
            retired_bots = (await session.execute(retired_bots_stmt)).scalar() or 0

            # Community counts
            total_communities_stmt = select(func.count(CommunityDB.id))
            total_communities = (await session.execute(total_communities_stmt)).scalar() or 0

            # Post counts
            total_posts_stmt = select(func.count(PostDB.id)).where(PostDB.is_deleted == False)
            total_posts = (await session.execute(total_posts_stmt)).scalar() or 0

            posts_today_stmt = select(func.count(PostDB.id)).where(
                PostDB.created_at >= today_start,
                PostDB.is_deleted == False
            )
            posts_today = (await session.execute(posts_today_stmt)).scalar() or 0

            posts_week_stmt = select(func.count(PostDB.id)).where(
                PostDB.created_at >= cutoff,
                PostDB.is_deleted == False
            )
            posts_week = (await session.execute(posts_week_stmt)).scalar() or 0

            # Comment counts
            total_comments_stmt = select(func.count(PostCommentDB.id)).where(
                PostCommentDB.is_deleted == False
            )
            total_comments = (await session.execute(total_comments_stmt)).scalar() or 0

            comments_today_stmt = select(func.count(PostCommentDB.id)).where(
                PostCommentDB.created_at >= today_start,
                PostCommentDB.is_deleted == False
            )
            comments_today = (await session.execute(comments_today_stmt)).scalar() or 0

            comments_week_stmt = select(func.count(PostCommentDB.id)).where(
                PostCommentDB.created_at >= cutoff,
                PostCommentDB.is_deleted == False
            )
            comments_week = (await session.execute(comments_week_stmt)).scalar() or 0

            # Like counts
            total_likes_stmt = select(func.count(PostLikeDB.id))
            total_likes = (await session.execute(total_likes_stmt)).scalar() or 0

            likes_today_stmt = select(func.count(PostLikeDB.id)).where(
                PostLikeDB.created_at >= today_start
            )
            likes_today = (await session.execute(likes_today_stmt)).scalar() or 0

            likes_week_stmt = select(func.count(PostLikeDB.id)).where(
                PostLikeDB.created_at >= cutoff
            )
            likes_week = (await session.execute(likes_week_stmt)).scalar() or 0

            # Chat message counts
            total_chat_stmt = select(func.count(CommunityChatMessageDB.id)).where(
                CommunityChatMessageDB.is_deleted == False
            )
            total_chat = (await session.execute(total_chat_stmt)).scalar() or 0

            chat_today_stmt = select(func.count(CommunityChatMessageDB.id)).where(
                CommunityChatMessageDB.created_at >= today_start,
                CommunityChatMessageDB.is_deleted == False
            )
            chat_today = (await session.execute(chat_today_stmt)).scalar() or 0

            # DM counts
            total_dm_stmt = select(func.count(DirectMessageDB.id))
            total_dm = (await session.execute(total_dm_stmt)).scalar() or 0

            dm_today_stmt = select(func.count(DirectMessageDB.id)).where(
                DirectMessageDB.created_at >= today_start
            )
            dm_today = (await session.execute(dm_today_stmt)).scalar() or 0

            # Session metrics for today
            sessions_today_stmt = select(
                func.count(SessionDB.id),
                func.avg(SessionDB.duration_seconds)
            ).where(SessionDB.started_at >= today_start)
            sessions_result = await session.execute(sessions_today_stmt)
            session_row = sessions_result.first()
            sessions_today = session_row[0] or 0
            avg_session = session_row[1] or 0.0

            # Calculate averages
            avg_posts_per_day = posts_week / days if days > 0 else 0
            avg_comments_per_post = total_comments / total_posts if total_posts > 0 else 0
            avg_likes_per_post = total_likes / total_posts if total_posts > 0 else 0

            return PlatformMetrics(
                total_users=total_users,
                active_users_today=active_users_today,
                active_users_week=active_users_week,
                new_users_today=new_users_today,
                new_users_week=new_users_week,
                total_bots=total_bots,
                active_bots=active_bots,
                paused_bots=paused_bots,
                retired_bots=retired_bots,
                total_communities=total_communities,
                active_communities=total_communities,  # All communities are active
                total_posts=total_posts,
                posts_today=posts_today,
                posts_this_week=posts_week,
                total_comments=total_comments,
                comments_today=comments_today,
                comments_this_week=comments_week,
                total_likes=total_likes,
                likes_today=likes_today,
                likes_this_week=likes_week,
                total_chat_messages=total_chat,
                chat_messages_today=chat_today,
                total_dm_messages=total_dm,
                dm_messages_today=dm_today,
                avg_posts_per_day=round(avg_posts_per_day, 2),
                avg_comments_per_post=round(avg_comments_per_post, 2),
                avg_likes_per_post=round(avg_likes_per_post, 2),
                total_sessions_today=sessions_today,
                avg_session_duration=float(avg_session),
                period_days=days
            )

    # =========================================================================
    # TRENDING CONTENT
    # =========================================================================

    async def get_trending_content(
        self,
        hours: int = 24,
        limit: int = 20
    ) -> List[TrendingContent]:
        """
        Get trending content based on recent engagement.

        Args:
            hours: Timeframe to analyze
            limit: Maximum items to return

        Returns:
            List of TrendingContent items sorted by trending score
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        async with async_session_factory() as session:
            # Get posts with their engagement counts
            stmt = (
                select(
                    PostDB,
                    BotProfileDB,
                    CommunityDB,
                    func.count(PostLikeDB.id).label("recent_likes"),
                )
                .join(BotProfileDB, PostDB.author_id == BotProfileDB.id)
                .join(CommunityDB, PostDB.community_id == CommunityDB.id)
                .outerjoin(PostLikeDB, and_(
                    PostLikeDB.post_id == PostDB.id,
                    PostLikeDB.created_at >= cutoff
                ))
                .where(PostDB.created_at >= cutoff)
                .where(PostDB.is_deleted == False)
                .group_by(PostDB.id, BotProfileDB.id, CommunityDB.id)
                .order_by(desc("recent_likes"))
                .limit(limit)
            )

            result = await session.execute(stmt)
            rows = result.all()

            trending = []
            for post, author, community, recent_likes in rows:
                # Calculate trending score based on engagement velocity
                hours_since_creation = max(
                    (datetime.utcnow() - post.created_at).total_seconds() / 3600,
                    1
                )
                velocity = (post.like_count + post.comment_count * 2) / hours_since_creation
                trending_score = recent_likes * 10 + velocity * 5

                trending.append(TrendingContent(
                    content_id=post.id,
                    content_type="post",
                    author_id=author.id,
                    author_name=author.display_name,
                    author_handle=author.handle,
                    is_bot=True,
                    content_preview=post.content[:200] if post.content else "",
                    community_id=community.id,
                    community_name=community.name,
                    likes=post.like_count,
                    comments=post.comment_count,
                    trending_score=round(trending_score, 2),
                    velocity=round(velocity, 2),
                    created_at=post.created_at
                ))

            # Sort by trending score
            trending.sort(key=lambda t: t.trending_score, reverse=True)
            return trending

    # =========================================================================
    # TIME SERIES
    # =========================================================================

    async def get_engagement_by_hour(
        self,
        days: int = 7
    ) -> TimeSeriesData:
        """
        Get engagement distribution by hour of day.

        Args:
            days: Number of days to analyze

        Returns:
            TimeSeriesData with hourly engagement
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        async with async_session_factory() as session:
            # Get post counts by hour
            stmt = select(
                func.extract("hour", PostDB.created_at).label("hour"),
                func.count(PostDB.id).label("count")
            ).where(
                PostDB.created_at >= cutoff
            ).group_by(
                func.extract("hour", PostDB.created_at)
            ).order_by("hour")

            result = await session.execute(stmt)
            rows = result.all()

            # Build time series
            timestamps = []
            values = []
            labels = []

            for hour, count in rows:
                hour_int = int(hour)
                timestamps.append(datetime.utcnow().replace(
                    hour=hour_int, minute=0, second=0, microsecond=0
                ))
                values.append(float(count))
                labels.append(f"{hour_int:02d}:00")

            ts = TimeSeriesData(
                metric_name="posts_by_hour",
                entity_type="platform",
                granularity="hour",
                timestamps=timestamps,
                values=values,
                labels=labels
            )
            ts.calculate_stats()
            return ts

    async def get_daily_metrics(
        self,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get daily aggregated metrics.

        Args:
            days: Number of days to retrieve

        Returns:
            List of daily metric dictionaries
        """
        cutoff = datetime.utcnow().date() - timedelta(days=days)

        async with async_session_factory() as session:
            stmt = (
                select(DailyMetricsDB)
                .where(DailyMetricsDB.date >= cutoff)
                .order_by(desc(DailyMetricsDB.date))
            )
            result = await session.execute(stmt)
            metrics = result.scalars().all()

            return [
                {
                    "date": m.date.isoformat(),
                    "posts": m.posts,
                    "comments": m.comments,
                    "likes": m.likes,
                    "dms": m.dms,
                    "chats": m.chats,
                    "active_users": m.active_users,
                }
                for m in metrics
            ]


# Singleton instance
_aggregator_instance: Optional[AnalyticsAggregator] = None


async def get_analytics_aggregator() -> AnalyticsAggregator:
    """Get the singleton analytics aggregator instance."""
    global _aggregator_instance
    if _aggregator_instance is None:
        _aggregator_instance = AnalyticsAggregator()
        await _aggregator_instance.initialize()
    return _aggregator_instance
