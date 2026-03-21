"""
Analytics API routes - User and platform analytics endpoints.

Provides comprehensive analytics dashboard endpoints including:
- Overview metrics (users, bots, posts, engagement)
- Engagement metrics over time (likes, comments, shares)
- Bot performance metrics
- User activity metrics
- Content analytics (top posts, trending topics)
- Real-time metrics (active users, live stats)
"""

from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any, Literal
from uuid import UUID
from enum import Enum

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc, and_, extract

from mind.core.database import (
    async_session_factory,
    AppUserDB,
    BotProfileDB,
    PostDB,
    PostLikeDB,
    PostCommentDB,
    CommunityChatMessageDB,
    DirectMessageDB,
    CommunityDB,
    SessionDB,
    DailyMetricsDB,
)
from mind.api.dependencies import get_current_user, get_optional_user
from mind.core.auth import AuthenticatedUser
from mind.api.routes.admin import require_admin as require_admin_header
from mind.analytics import (
    AnalyticsTracker,
    AnalyticsAggregator,
    get_analytics_tracker,
    get_analytics_aggregator,
    BotPerformance,
    UserActivity,
    PlatformMetrics,
)


router = APIRouter(prefix="/analytics", tags=["analytics"])
admin_router = APIRouter(prefix="/admin/analytics", tags=["admin"])
dashboard_router = APIRouter(prefix="/analytics", tags=["analytics-dashboard"])


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================

class Granularity(str, Enum):
    """Time granularity options for analytics queries."""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class UserEngagementResponse(BaseModel):
    """Response model for user engagement stats."""
    user_id: UUID
    display_name: str

    # Activity counts
    posts_created: int = 0
    comments_made: int = 0
    likes_given: int = 0

    # Engagement received
    likes_received: int = 0
    comments_received: int = 0

    # Chat activity
    chat_messages_sent: int = 0
    dm_messages_sent: int = 0
    dm_conversations_active: int = 0

    # Session info
    total_sessions: int = 0
    avg_session_duration_minutes: float = 0.0

    # Bot interactions
    bots_interacted_with: int = 0
    communities_active_in: int = 0

    # Time info
    member_since: Optional[datetime] = None
    last_active: Optional[datetime] = None
    period_days: int = 7


class BotPerformanceResponse(BaseModel):
    """Response model for bot performance stats."""
    bot_id: UUID
    bot_handle: str
    bot_name: str

    # Content production
    posts_created: int = 0
    comments_created: int = 0
    chat_messages_sent: int = 0
    dm_responses: int = 0

    # Engagement received
    total_likes_received: int = 0
    total_comments_received: int = 0
    avg_engagement_per_post: float = 0.0

    # Activity
    last_active: Optional[datetime] = None
    period_days: int = 7


class PlatformMetricsResponse(BaseModel):
    """Response model for platform-wide metrics."""
    # User metrics
    total_users: int = 0
    active_users_today: int = 0
    active_users_week: int = 0
    new_users_today: int = 0
    new_users_week: int = 0

    # Bot metrics
    total_bots: int = 0
    active_bots: int = 0
    paused_bots: int = 0

    # Community metrics
    total_communities: int = 0

    # Content metrics
    total_posts: int = 0
    posts_today: int = 0
    posts_this_week: int = 0

    total_comments: int = 0
    comments_today: int = 0

    total_likes: int = 0
    likes_today: int = 0

    # Chat metrics
    total_chat_messages: int = 0
    chat_messages_today: int = 0

    total_dm_messages: int = 0
    dm_messages_today: int = 0

    # Averages
    avg_posts_per_day: float = 0.0
    avg_comments_per_post: float = 0.0
    avg_likes_per_post: float = 0.0

    # Session metrics
    total_sessions_today: int = 0
    avg_session_duration_minutes: float = 0.0

    # Meta
    period_days: int = 7
    generated_at: datetime


class TrendingContentResponse(BaseModel):
    """Response model for trending content."""
    content_id: UUID
    content_type: str
    author_id: UUID
    author_name: str
    author_handle: str
    is_bot: bool

    content_preview: str
    community_id: UUID
    community_name: str

    likes: int
    comments: int
    trending_score: float
    velocity: float

    created_at: datetime


class TimeSeriesDataResponse(BaseModel):
    """Response model for time series data."""
    metric_name: str
    granularity: str
    timestamps: List[str]
    values: List[float]
    labels: List[str]
    total: float
    average: float


class SentimentCategory(str, Enum):
    """Sentiment categories for content analysis."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class SentimentSample(BaseModel):
    """A sample of content with its sentiment."""
    content_id: UUID
    content_preview: str
    sentiment: SentimentCategory
    confidence: float
    author_handle: Optional[str] = None
    created_at: datetime


class SentimentDistribution(BaseModel):
    """Distribution of sentiment across content."""
    positive_count: int = 0
    positive_percentage: float = 0.0
    neutral_count: int = 0
    neutral_percentage: float = 0.0
    negative_count: int = 0
    negative_percentage: float = 0.0
    total_analyzed: int = 0


class SentimentTrend(BaseModel):
    """Sentiment trend over a time period."""
    timestamp: str
    label: str
    positive: int = 0
    neutral: int = 0
    negative: int = 0
    dominant_sentiment: SentimentCategory


class SentimentAnalysisResponse(BaseModel):
    """Response model for sentiment analysis."""
    distribution: SentimentDistribution
    trends: List[SentimentTrend] = []
    top_positive: List[SentimentSample] = []
    top_negative: List[SentimentSample] = []
    analysis_method: str  # "keyword" or "llm"
    start_date: str
    end_date: str
    content_type: str  # "posts", "messages", "all"


class DailyMetricsResponse(BaseModel):
    """Response model for daily metrics."""
    date: str
    posts: int
    comments: int
    likes: int
    dms: int
    chats: int
    active_users: int


# ============================================================================
# DASHBOARD RESPONSE MODELS
# ============================================================================

class OverviewMetrics(BaseModel):
    """Overview metrics for the analytics dashboard."""
    # User metrics
    total_users: int = 0
    new_users_period: int = 0
    active_users_period: int = 0
    user_growth_rate: float = 0.0  # Percentage change from previous period

    # Bot metrics
    total_bots: int = 0
    active_bots: int = 0
    paused_bots: int = 0

    # Post metrics
    total_posts: int = 0
    new_posts_period: int = 0
    post_growth_rate: float = 0.0

    # Engagement metrics
    total_engagement: int = 0  # likes + comments + shares
    avg_engagement_per_post: float = 0.0
    engagement_rate: float = 0.0  # engagement / views

    # Period info
    start_date: str
    end_date: str
    granularity: str


class EngagementDataPoint(BaseModel):
    """Single data point for engagement time series."""
    timestamp: str
    label: str
    likes: int = 0
    comments: int = 0
    shares: int = 0
    total: int = 0


class EngagementMetricsResponse(BaseModel):
    """Engagement metrics over time for charting."""
    data_points: List[EngagementDataPoint]
    summary: Dict[str, Any]
    granularity: str
    start_date: str
    end_date: str


class BotMetricsItem(BaseModel):
    """Individual bot metrics for the dashboard."""
    bot_id: UUID
    bot_handle: str
    bot_name: str
    avatar_url: Optional[str] = None

    # Content metrics
    posts_created: int = 0
    comments_created: int = 0
    chat_messages_sent: int = 0
    dm_responses: int = 0
    total_content: int = 0

    # Engagement received
    likes_received: int = 0
    comments_received: int = 0
    engagement_rate: float = 0.0

    # Activity
    is_active: bool = True
    is_paused: bool = False
    last_active: Optional[datetime] = None


class BotMetricsResponse(BaseModel):
    """Bot performance metrics response."""
    bots: List[BotMetricsItem]
    total_bots: int
    summary: Dict[str, Any]
    start_date: str
    end_date: str
    granularity: str


class UserMetricsItem(BaseModel):
    """Individual user activity metrics."""
    user_id: UUID
    display_name: str
    avatar_url: Optional[str] = None

    # Activity metrics
    posts_created: int = 0
    comments_made: int = 0
    likes_given: int = 0
    chat_messages: int = 0
    dm_messages: int = 0
    total_activity: int = 0

    # Session info
    session_count: int = 0
    total_time_minutes: float = 0.0
    avg_session_minutes: float = 0.0

    # Timestamps
    joined_at: Optional[datetime] = None
    last_active: Optional[datetime] = None


class UserMetricsResponse(BaseModel):
    """User activity metrics response."""
    users: List[UserMetricsItem]
    total_users: int
    active_users_count: int
    summary: Dict[str, Any]
    start_date: str
    end_date: str
    granularity: str


class TopPostItem(BaseModel):
    """Top performing post item."""
    post_id: UUID
    content_preview: str
    author_id: UUID
    author_name: str
    author_handle: str
    is_bot_author: bool
    community_id: UUID
    community_name: str

    likes: int = 0
    comments: int = 0
    views: int = 0
    engagement_score: float = 0.0

    created_at: datetime


class TrendingTopicItem(BaseModel):
    """Trending topic/hashtag item."""
    topic: str
    mention_count: int = 0
    post_count: int = 0
    engagement_total: int = 0
    trend_velocity: float = 0.0  # Rate of increase


class ContentMetricsResponse(BaseModel):
    """Content analytics response."""
    top_posts: List[TopPostItem]
    trending_topics: List[TrendingTopicItem]
    content_summary: Dict[str, Any]
    start_date: str
    end_date: str
    granularity: str


class RealtimeMetrics(BaseModel):
    """Real-time live metrics."""
    # Current active
    active_users_now: int = 0
    active_bots_now: int = 0
    active_sessions: int = 0

    # Last hour metrics
    posts_last_hour: int = 0
    comments_last_hour: int = 0
    likes_last_hour: int = 0
    dms_last_hour: int = 0
    chats_last_hour: int = 0

    # Last 5 minutes
    events_last_5min: int = 0

    # Trending now
    trending_communities: List[Dict[str, Any]] = []
    recent_activity: List[Dict[str, Any]] = []

    # Timestamp
    timestamp: datetime
    server_time: str


class HeatmapCell(BaseModel):
    """Single cell in the activity heatmap."""
    hour: int = Field(..., ge=0, le=23, description="Hour of day (0-23)")
    day_of_week: int = Field(..., ge=0, le=6, description="Day of week (0=Monday, 6=Sunday)")
    day_name: str = Field(..., description="Day name (e.g., 'Monday')")
    value: int = Field(..., ge=0, description="Activity count for this cell")
    normalized: float = Field(..., ge=0.0, le=1.0, description="Normalized value (0-1)")


class ActivityHeatmapResponse(BaseModel):
    """Activity heatmap data for visualization (hour of day vs day of week)."""
    cells: List[HeatmapCell] = Field(..., description="Heatmap cell data")
    max_value: int = Field(..., description="Maximum activity count in any cell")
    total_activity: int = Field(..., description="Total activity across all cells")
    peak_hour: int = Field(..., ge=0, le=23, description="Hour with most activity")
    peak_day: int = Field(..., ge=0, le=6, description="Day with most activity")
    peak_day_name: str = Field(..., description="Name of peak day")
    metric_type: str = Field(..., description="Type of activity measured (e.g., 'posts', 'all')")
    days_analyzed: int = Field(..., description="Number of days of data analyzed")
    generated_at: datetime = Field(..., description="When this data was generated")


# ============================================================================
# USER ANALYTICS ENDPOINTS
# ============================================================================

@router.get("/me", response_model=UserEngagementResponse)
async def get_my_engagement(
    current_user: AuthenticatedUser = Depends(get_current_user),
    days: int = Query(default=7, ge=1, le=90, description="Analysis period in days")
):
    """
    Get engagement analytics for the current authenticated user.

    Returns activity metrics including posts, comments, likes, and session data.
    """
    aggregator = await get_analytics_aggregator()
    activity = await aggregator.get_user_engagement(current_user.id, days)

    return UserEngagementResponse(
        user_id=activity.user_id,
        display_name=activity.display_name or current_user.display_name,
        posts_created=activity.posts_created,
        comments_made=activity.comments_made,
        likes_given=activity.likes_given,
        likes_received=activity.likes_received,
        comments_received=activity.comments_received,
        chat_messages_sent=activity.chat_messages_sent,
        dm_messages_sent=activity.dm_messages_sent,
        dm_conversations_active=activity.dm_conversations_active,
        total_sessions=activity.total_sessions,
        avg_session_duration_minutes=round(activity.avg_session_duration / 60, 2),
        bots_interacted_with=activity.bots_interacted_with,
        communities_active_in=activity.communities_active_in,
        member_since=activity.first_seen,
        last_active=activity.last_seen,
        period_days=days
    )


# ============================================================================
# BOT ANALYTICS ENDPOINTS (PUBLIC)
# ============================================================================

@router.get("/bots/{bot_id}", response_model=BotPerformanceResponse)
async def get_bot_performance(
    bot_id: UUID,
    days: int = Query(default=7, ge=1, le=30, description="Analysis period in days")
):
    """
    Get public performance metrics for a specific bot.

    Returns content production and engagement metrics.
    """
    async with async_session_factory() as session:
        # Verify bot exists
        stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
        result = await session.execute(stmt)
        bot = result.scalar_one_or_none()

        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")

    aggregator = await get_analytics_aggregator()
    perf = await aggregator.get_bot_performance(bot_id, days)

    return BotPerformanceResponse(
        bot_id=perf.bot_id,
        bot_handle=perf.bot_handle,
        bot_name=perf.bot_name,
        posts_created=perf.posts_created,
        comments_created=perf.comments_created,
        chat_messages_sent=perf.chat_messages_sent,
        dm_responses=perf.dm_responses,
        total_likes_received=perf.total_likes_received,
        total_comments_received=perf.total_comments_received,
        avg_engagement_per_post=perf.avg_engagement_per_post,
        last_active=perf.last_active,
        period_days=days
    )


# ============================================================================
# ADMIN ANALYTICS ENDPOINTS
# ============================================================================

async def verify_admin(user: AuthenticatedUser) -> AuthenticatedUser:
    """Verify the user is an admin."""
    async with async_session_factory() as session:
        stmt = select(AppUserDB).where(AppUserDB.id == user.id)
        result = await session.execute(stmt)
        db_user = result.scalar_one_or_none()

        if not db_user or not db_user.is_admin:
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )
    return user


@admin_router.get("/platform", response_model=PlatformMetricsResponse)
async def get_platform_metrics(
    admin_user: AppUserDB = Depends(require_admin_header),
    days: int = Query(default=7, ge=1, le=90, description="Analysis period in days")
):
    """
    Get platform-wide analytics metrics.

    Requires admin access. Returns comprehensive platform statistics.
    """

    aggregator = await get_analytics_aggregator()
    metrics = await aggregator.get_platform_metrics(days)

    return PlatformMetricsResponse(
        total_users=metrics.total_users,
        active_users_today=metrics.active_users_today,
        active_users_week=metrics.active_users_week,
        new_users_today=metrics.new_users_today,
        new_users_week=metrics.new_users_week,
        total_bots=metrics.total_bots,
        active_bots=metrics.active_bots,
        paused_bots=metrics.paused_bots,
        total_communities=metrics.total_communities,
        total_posts=metrics.total_posts,
        posts_today=metrics.posts_today,
        posts_this_week=metrics.posts_this_week,
        total_comments=metrics.total_comments,
        comments_today=metrics.comments_today,
        total_likes=metrics.total_likes,
        likes_today=metrics.likes_today,
        total_chat_messages=metrics.total_chat_messages,
        chat_messages_today=metrics.chat_messages_today,
        total_dm_messages=metrics.total_dm_messages,
        dm_messages_today=metrics.dm_messages_today,
        avg_posts_per_day=metrics.avg_posts_per_day,
        avg_comments_per_post=metrics.avg_comments_per_post,
        avg_likes_per_post=metrics.avg_likes_per_post,
        total_sessions_today=metrics.total_sessions_today,
        avg_session_duration_minutes=round(metrics.avg_session_duration / 60, 2),
        period_days=days,
        generated_at=metrics.generated_at or datetime.utcnow()
    )


@admin_router.get("/bots", response_model=List[BotPerformanceResponse])
async def get_all_bot_analytics(
    admin_user: AppUserDB = Depends(require_admin_header),
    days: int = Query(default=7, ge=1, le=30, description="Analysis period in days"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum bots to return")
):
    """
    Get comparative analytics for all bots.

    Requires admin access. Returns performance metrics sorted by engagement.
    """

    aggregator = await get_analytics_aggregator()
    performances = await aggregator.get_bot_comparison(limit, days)

    return [
        BotPerformanceResponse(
            bot_id=perf.bot_id,
            bot_handle=perf.bot_handle,
            bot_name=perf.bot_name,
            posts_created=perf.posts_created,
            comments_created=perf.comments_created,
            chat_messages_sent=perf.chat_messages_sent,
            dm_responses=perf.dm_responses,
            total_likes_received=perf.total_likes_received,
            total_comments_received=perf.total_comments_received,
            avg_engagement_per_post=perf.avg_engagement_per_post,
            last_active=perf.last_active,
            period_days=days
        )
        for perf in performances
    ]


@admin_router.get("/trends", response_model=List[TrendingContentResponse])
async def get_trending_content(
    admin_user: AppUserDB = Depends(require_admin_header),
    hours: int = Query(default=24, ge=1, le=168, description="Timeframe in hours"),
    limit: int = Query(default=20, ge=1, le=50, description="Maximum items to return")
):
    """
    Get trending content analysis.

    Requires admin access. Returns content sorted by trending score.
    """

    aggregator = await get_analytics_aggregator()
    trending = await aggregator.get_trending_content(hours, limit)

    return [
        TrendingContentResponse(
            content_id=item.content_id,
            content_type=item.content_type,
            author_id=item.author_id,
            author_name=item.author_name,
            author_handle=item.author_handle,
            is_bot=item.is_bot,
            content_preview=item.content_preview,
            community_id=item.community_id,
            community_name=item.community_name,
            likes=item.likes,
            comments=item.comments,
            trending_score=item.trending_score,
            velocity=item.velocity,
            created_at=item.created_at
        )
        for item in trending
    ]


@admin_router.get("/engagement-by-hour", response_model=TimeSeriesDataResponse)
async def get_engagement_by_hour(
    admin_user: AppUserDB = Depends(require_admin_header),
    days: int = Query(default=7, ge=1, le=30, description="Analysis period in days")
):
    """
    Get engagement distribution by hour of day.

    Requires admin access. Useful for understanding peak activity times.
    """

    aggregator = await get_analytics_aggregator()
    ts = await aggregator.get_engagement_by_hour(days)

    return TimeSeriesDataResponse(
        metric_name=ts.metric_name,
        granularity=ts.granularity,
        timestamps=[t.isoformat() for t in ts.timestamps],
        values=ts.values,
        labels=ts.labels,
        total=ts.total,
        average=ts.average
    )


@admin_router.get("/daily", response_model=List[DailyMetricsResponse])
async def get_daily_metrics(
    admin_user: AppUserDB = Depends(require_admin_header),
    days: int = Query(default=30, ge=1, le=90, description="Number of days to retrieve")
):
    """
    Get daily aggregated metrics history.

    Requires admin access. Returns daily metrics for charting.
    """

    aggregator = await get_analytics_aggregator()
    metrics = await aggregator.get_daily_metrics(days)

    return [
        DailyMetricsResponse(**m)
        for m in metrics
    ]


# ============================================================================
# ANALYTICS DASHBOARD ENDPOINTS
# ============================================================================

def parse_date_range(
    start_date: Optional[str],
    end_date: Optional[str],
    default_days: int = 30
) -> tuple[datetime, datetime]:
    """Parse date range from query parameters."""
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        end_dt = datetime.utcnow()

    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except ValueError:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        start_dt = end_dt - timedelta(days=default_days)

    return start_dt, end_dt


def get_time_buckets(
    start_dt: datetime,
    end_dt: datetime,
    granularity: Granularity
) -> List[tuple[datetime, datetime, str]]:
    """Generate time buckets based on granularity."""
    buckets = []
    current = start_dt

    while current < end_dt:
        if granularity == Granularity.HOUR:
            next_dt = current + timedelta(hours=1)
            label = current.strftime("%Y-%m-%d %H:00")
        elif granularity == Granularity.DAY:
            next_dt = current + timedelta(days=1)
            label = current.strftime("%Y-%m-%d")
        elif granularity == Granularity.WEEK:
            next_dt = current + timedelta(weeks=1)
            label = f"Week of {current.strftime('%Y-%m-%d')}"
        elif granularity == Granularity.MONTH:
            # Move to first of next month
            if current.month == 12:
                next_dt = current.replace(year=current.year + 1, month=1, day=1)
            else:
                next_dt = current.replace(month=current.month + 1, day=1)
            label = current.strftime("%Y-%m")
        else:
            next_dt = current + timedelta(days=1)
            label = current.strftime("%Y-%m-%d")

        buckets.append((current, min(next_dt, end_dt), label))
        current = next_dt

    return buckets


@dashboard_router.get("/overview", response_model=OverviewMetrics)
async def get_analytics_overview(
    current_user: AuthenticatedUser = Depends(get_current_user),
    start_date: Optional[str] = Query(None, description="Start date (ISO format or YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format or YYYY-MM-DD)"),
    granularity: Granularity = Query(Granularity.DAY, description="Time granularity")
):
    """
    Get overview analytics for the dashboard.

    Returns total users, bots, posts, and engagement metrics for the specified period.
    Useful for summary cards and KPI displays.
    """
    await verify_admin(current_user)

    start_dt, end_dt = parse_date_range(start_date, end_date)
    period_days = (end_dt - start_dt).days or 1

    # Calculate previous period for growth comparison
    prev_start_dt = start_dt - timedelta(days=period_days)
    prev_end_dt = start_dt

    async with async_session_factory() as session:
        # Current period metrics
        total_users = (await session.execute(
            select(func.count(AppUserDB.id))
        )).scalar() or 0

        new_users_period = (await session.execute(
            select(func.count(AppUserDB.id)).where(
                AppUserDB.created_at >= start_dt,
                AppUserDB.created_at <= end_dt
            )
        )).scalar() or 0

        active_users_period = (await session.execute(
            select(func.count(AppUserDB.id)).where(
                AppUserDB.last_active >= start_dt,
                AppUserDB.last_active <= end_dt
            )
        )).scalar() or 0

        # Previous period for growth calculation
        prev_new_users = (await session.execute(
            select(func.count(AppUserDB.id)).where(
                AppUserDB.created_at >= prev_start_dt,
                AppUserDB.created_at < prev_end_dt
            )
        )).scalar() or 0

        user_growth_rate = 0.0
        if prev_new_users > 0:
            user_growth_rate = round(((new_users_period - prev_new_users) / prev_new_users) * 100, 2)
        elif new_users_period > 0:
            user_growth_rate = 100.0

        # Bot metrics
        total_bots = (await session.execute(
            select(func.count(BotProfileDB.id))
        )).scalar() or 0

        active_bots = (await session.execute(
            select(func.count(BotProfileDB.id)).where(
                BotProfileDB.is_active == True,
                BotProfileDB.is_paused == False
            )
        )).scalar() or 0

        paused_bots = (await session.execute(
            select(func.count(BotProfileDB.id)).where(
                BotProfileDB.is_paused == True
            )
        )).scalar() or 0

        # Post metrics
        total_posts = (await session.execute(
            select(func.count(PostDB.id)).where(PostDB.is_deleted == False)
        )).scalar() or 0

        new_posts_period = (await session.execute(
            select(func.count(PostDB.id)).where(
                PostDB.created_at >= start_dt,
                PostDB.created_at <= end_dt,
                PostDB.is_deleted == False
            )
        )).scalar() or 0

        prev_new_posts = (await session.execute(
            select(func.count(PostDB.id)).where(
                PostDB.created_at >= prev_start_dt,
                PostDB.created_at < prev_end_dt,
                PostDB.is_deleted == False
            )
        )).scalar() or 0

        post_growth_rate = 0.0
        if prev_new_posts > 0:
            post_growth_rate = round(((new_posts_period - prev_new_posts) / prev_new_posts) * 100, 2)
        elif new_posts_period > 0:
            post_growth_rate = 100.0

        # Engagement metrics
        likes_period = (await session.execute(
            select(func.count(PostLikeDB.id)).where(
                PostLikeDB.created_at >= start_dt,
                PostLikeDB.created_at <= end_dt
            )
        )).scalar() or 0

        comments_period = (await session.execute(
            select(func.count(PostCommentDB.id)).where(
                PostCommentDB.created_at >= start_dt,
                PostCommentDB.created_at <= end_dt,
                PostCommentDB.is_deleted == False
            )
        )).scalar() or 0

        total_engagement = likes_period + comments_period

        avg_engagement_per_post = 0.0
        if new_posts_period > 0:
            avg_engagement_per_post = round(total_engagement / new_posts_period, 2)

    return OverviewMetrics(
        total_users=total_users,
        new_users_period=new_users_period,
        active_users_period=active_users_period,
        user_growth_rate=user_growth_rate,
        total_bots=total_bots,
        active_bots=active_bots,
        paused_bots=paused_bots,
        total_posts=total_posts,
        new_posts_period=new_posts_period,
        post_growth_rate=post_growth_rate,
        total_engagement=total_engagement,
        avg_engagement_per_post=avg_engagement_per_post,
        engagement_rate=0.0,  # Would need view tracking for this
        start_date=start_dt.isoformat(),
        end_date=end_dt.isoformat(),
        granularity=granularity.value
    )


@dashboard_router.get("/engagement", response_model=EngagementMetricsResponse)
async def get_engagement_metrics(
    current_user: AuthenticatedUser = Depends(get_current_user),
    start_date: Optional[str] = Query(None, description="Start date (ISO format or YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format or YYYY-MM-DD)"),
    granularity: Granularity = Query(Granularity.DAY, description="Time granularity")
):
    """
    Get engagement metrics over time for charting.

    Returns likes, comments, and shares aggregated by the specified granularity.
    Ideal for line charts and trend visualization.
    """
    await verify_admin(current_user)

    start_dt, end_dt = parse_date_range(start_date, end_date)
    buckets = get_time_buckets(start_dt, end_dt, granularity)

    data_points = []
    total_likes = 0
    total_comments = 0
    total_shares = 0

    async with async_session_factory() as session:
        for bucket_start, bucket_end, label in buckets:
            # Likes in this bucket
            likes = (await session.execute(
                select(func.count(PostLikeDB.id)).where(
                    PostLikeDB.created_at >= bucket_start,
                    PostLikeDB.created_at < bucket_end
                )
            )).scalar() or 0

            # Comments in this bucket
            comments = (await session.execute(
                select(func.count(PostCommentDB.id)).where(
                    PostCommentDB.created_at >= bucket_start,
                    PostCommentDB.created_at < bucket_end,
                    PostCommentDB.is_deleted == False
                )
            )).scalar() or 0

            # Shares (not implemented, using 0)
            shares = 0

            total = likes + comments + shares
            total_likes += likes
            total_comments += comments
            total_shares += shares

            data_points.append(EngagementDataPoint(
                timestamp=bucket_start.isoformat(),
                label=label,
                likes=likes,
                comments=comments,
                shares=shares,
                total=total
            ))

    return EngagementMetricsResponse(
        data_points=data_points,
        summary={
            "total_likes": total_likes,
            "total_comments": total_comments,
            "total_shares": total_shares,
            "total_engagement": total_likes + total_comments + total_shares,
            "avg_likes_per_period": round(total_likes / len(buckets), 2) if buckets else 0,
            "avg_comments_per_period": round(total_comments / len(buckets), 2) if buckets else 0,
        },
        granularity=granularity.value,
        start_date=start_dt.isoformat(),
        end_date=end_dt.isoformat()
    )


@dashboard_router.get("/bots", response_model=BotMetricsResponse)
async def get_bot_metrics(
    current_user: AuthenticatedUser = Depends(get_current_user),
    start_date: Optional[str] = Query(None, description="Start date (ISO format or YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format or YYYY-MM-DD)"),
    granularity: Granularity = Query(Granularity.DAY, description="Time granularity"),
    limit: int = Query(50, ge=1, le=200, description="Maximum bots to return"),
    sort_by: str = Query("engagement", description="Sort by: engagement, posts, activity")
):
    """
    Get bot performance metrics for the dashboard.

    Returns metrics for all bots including content production, engagement received,
    and activity status. Supports sorting by different criteria.
    """
    await verify_admin(current_user)

    start_dt, end_dt = parse_date_range(start_date, end_date)

    bot_items = []
    total_posts_all = 0
    total_engagement_all = 0

    async with async_session_factory() as session:
        # Get all bots
        bots_result = await session.execute(
            select(BotProfileDB).order_by(desc(BotProfileDB.last_active)).limit(limit)
        )
        bots = bots_result.scalars().all()

        for bot in bots:
            # Posts created in period
            posts_created = (await session.execute(
                select(func.count(PostDB.id)).where(
                    PostDB.author_id == bot.id,
                    PostDB.created_at >= start_dt,
                    PostDB.created_at <= end_dt
                )
            )).scalar() or 0

            # Comments created
            comments_created = (await session.execute(
                select(func.count(PostCommentDB.id)).where(
                    PostCommentDB.author_id == bot.id,
                    PostCommentDB.created_at >= start_dt,
                    PostCommentDB.created_at <= end_dt
                )
            )).scalar() or 0

            # Chat messages sent
            chat_messages = (await session.execute(
                select(func.count(CommunityChatMessageDB.id)).where(
                    CommunityChatMessageDB.author_id == bot.id,
                    CommunityChatMessageDB.created_at >= start_dt,
                    CommunityChatMessageDB.created_at <= end_dt
                )
            )).scalar() or 0

            # DM responses
            dm_responses = (await session.execute(
                select(func.count(DirectMessageDB.id)).where(
                    DirectMessageDB.sender_id == bot.id,
                    DirectMessageDB.sender_is_bot == True,
                    DirectMessageDB.created_at >= start_dt,
                    DirectMessageDB.created_at <= end_dt
                )
            )).scalar() or 0

            # Likes received on bot's posts
            bot_posts_subq = select(PostDB.id).where(PostDB.author_id == bot.id).subquery()
            likes_received = (await session.execute(
                select(func.count(PostLikeDB.id)).where(
                    PostLikeDB.post_id.in_(select(bot_posts_subq)),
                    PostLikeDB.created_at >= start_dt,
                    PostLikeDB.created_at <= end_dt
                )
            )).scalar() or 0

            # Comments received on bot's posts
            comments_received = (await session.execute(
                select(func.count(PostCommentDB.id)).where(
                    PostCommentDB.post_id.in_(select(bot_posts_subq)),
                    PostCommentDB.author_id != bot.id,
                    PostCommentDB.created_at >= start_dt,
                    PostCommentDB.created_at <= end_dt
                )
            )).scalar() or 0

            total_content = posts_created + comments_created + chat_messages + dm_responses
            total_engagement = likes_received + comments_received
            engagement_rate = round(total_engagement / posts_created, 2) if posts_created > 0 else 0.0

            total_posts_all += posts_created
            total_engagement_all += total_engagement

            bot_items.append(BotMetricsItem(
                bot_id=bot.id,
                bot_handle=bot.handle,
                bot_name=bot.display_name,
                avatar_url=bot.avatar_url if hasattr(bot, 'avatar_url') else None,
                posts_created=posts_created,
                comments_created=comments_created,
                chat_messages_sent=chat_messages,
                dm_responses=dm_responses,
                total_content=total_content,
                likes_received=likes_received,
                comments_received=comments_received,
                engagement_rate=engagement_rate,
                is_active=bot.is_active,
                is_paused=bot.is_paused,
                last_active=bot.last_active
            ))

        # Sort based on criteria
        if sort_by == "engagement":
            bot_items.sort(key=lambda x: x.likes_received + x.comments_received, reverse=True)
        elif sort_by == "posts":
            bot_items.sort(key=lambda x: x.posts_created, reverse=True)
        elif sort_by == "activity":
            bot_items.sort(key=lambda x: x.last_active or datetime.min, reverse=True)

    return BotMetricsResponse(
        bots=bot_items,
        total_bots=len(bots),
        summary={
            "total_posts": total_posts_all,
            "total_engagement": total_engagement_all,
            "avg_posts_per_bot": round(total_posts_all / len(bots), 2) if bots else 0,
            "avg_engagement_per_bot": round(total_engagement_all / len(bots), 2) if bots else 0,
            "active_bots": sum(1 for b in bot_items if b.is_active and not b.is_paused),
            "paused_bots": sum(1 for b in bot_items if b.is_paused),
        },
        start_date=start_dt.isoformat(),
        end_date=end_dt.isoformat(),
        granularity=granularity.value
    )


@dashboard_router.get("/users", response_model=UserMetricsResponse)
async def get_user_metrics(
    current_user: AuthenticatedUser = Depends(get_current_user),
    start_date: Optional[str] = Query(None, description="Start date (ISO format or YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format or YYYY-MM-DD)"),
    granularity: Granularity = Query(Granularity.DAY, description="Time granularity"),
    limit: int = Query(50, ge=1, le=200, description="Maximum users to return"),
    sort_by: str = Query("activity", description="Sort by: activity, engagement, sessions")
):
    """
    Get user activity metrics for the dashboard.

    Returns activity metrics for users including posts, comments, likes,
    messages, and session information.
    """
    await verify_admin(current_user)

    start_dt, end_dt = parse_date_range(start_date, end_date)

    user_items = []
    total_activity = 0
    active_count = 0

    async with async_session_factory() as session:
        # Get users active in period
        users_result = await session.execute(
            select(AppUserDB)
            .where(AppUserDB.last_active >= start_dt)
            .order_by(desc(AppUserDB.last_active))
            .limit(limit)
        )
        users = users_result.scalars().all()

        for user in users:
            # Posts created (users don't typically create posts, but check anyway)
            posts_created = (await session.execute(
                select(func.count(PostDB.id)).where(
                    PostDB.author_id == user.id,
                    PostDB.created_at >= start_dt,
                    PostDB.created_at <= end_dt
                )
            )).scalar() or 0

            # Comments made
            comments_made = (await session.execute(
                select(func.count(PostCommentDB.id)).where(
                    PostCommentDB.author_id == user.id,
                    PostCommentDB.is_bot == False,
                    PostCommentDB.created_at >= start_dt,
                    PostCommentDB.created_at <= end_dt
                )
            )).scalar() or 0

            # Likes given
            likes_given = (await session.execute(
                select(func.count(PostLikeDB.id)).where(
                    PostLikeDB.user_id == user.id,
                    PostLikeDB.is_bot == False,
                    PostLikeDB.created_at >= start_dt,
                    PostLikeDB.created_at <= end_dt
                )
            )).scalar() or 0

            # Chat messages
            chat_messages = (await session.execute(
                select(func.count(CommunityChatMessageDB.id)).where(
                    CommunityChatMessageDB.author_id == user.id,
                    CommunityChatMessageDB.is_bot == False,
                    CommunityChatMessageDB.created_at >= start_dt,
                    CommunityChatMessageDB.created_at <= end_dt
                )
            )).scalar() or 0

            # DM messages
            dm_messages = (await session.execute(
                select(func.count(DirectMessageDB.id)).where(
                    DirectMessageDB.sender_id == user.id,
                    DirectMessageDB.sender_is_bot == False,
                    DirectMessageDB.created_at >= start_dt,
                    DirectMessageDB.created_at <= end_dt
                )
            )).scalar() or 0

            # Session metrics
            session_result = await session.execute(
                select(
                    func.count(SessionDB.id),
                    func.sum(SessionDB.duration_seconds),
                    func.avg(SessionDB.duration_seconds)
                ).where(
                    SessionDB.user_id == user.id,
                    SessionDB.started_at >= start_dt,
                    SessionDB.started_at <= end_dt
                )
            )
            session_row = session_result.first()
            session_count = session_row[0] or 0
            total_time_seconds = session_row[1] or 0.0
            avg_session_seconds = session_row[2] or 0.0

            user_total_activity = (
                posts_created + comments_made + likes_given +
                chat_messages + dm_messages
            )
            total_activity += user_total_activity

            if user_total_activity > 0 or session_count > 0:
                active_count += 1

            user_items.append(UserMetricsItem(
                user_id=user.id,
                display_name=user.display_name,
                avatar_url=user.avatar_url if hasattr(user, 'avatar_url') else None,
                posts_created=posts_created,
                comments_made=comments_made,
                likes_given=likes_given,
                chat_messages=chat_messages,
                dm_messages=dm_messages,
                total_activity=user_total_activity,
                session_count=session_count,
                total_time_minutes=round(float(total_time_seconds) / 60, 2),
                avg_session_minutes=round(float(avg_session_seconds) / 60, 2),
                joined_at=user.created_at,
                last_active=user.last_active
            ))

        # Sort based on criteria
        if sort_by == "activity":
            user_items.sort(key=lambda x: x.total_activity, reverse=True)
        elif sort_by == "engagement":
            user_items.sort(key=lambda x: x.comments_made + x.likes_given, reverse=True)
        elif sort_by == "sessions":
            user_items.sort(key=lambda x: x.total_time_minutes, reverse=True)

    return UserMetricsResponse(
        users=user_items,
        total_users=len(users),
        active_users_count=active_count,
        summary={
            "total_activity": total_activity,
            "avg_activity_per_user": round(total_activity / len(users), 2) if users else 0,
            "total_comments": sum(u.comments_made for u in user_items),
            "total_likes": sum(u.likes_given for u in user_items),
            "total_messages": sum(u.chat_messages + u.dm_messages for u in user_items),
            "total_session_time_hours": round(sum(u.total_time_minutes for u in user_items) / 60, 2),
        },
        start_date=start_dt.isoformat(),
        end_date=end_dt.isoformat(),
        granularity=granularity.value
    )


@dashboard_router.get("/content", response_model=ContentMetricsResponse)
async def get_content_metrics(
    current_user: AuthenticatedUser = Depends(get_current_user),
    start_date: Optional[str] = Query(None, description="Start date (ISO format or YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format or YYYY-MM-DD)"),
    granularity: Granularity = Query(Granularity.DAY, description="Time granularity"),
    top_posts_limit: int = Query(20, ge=1, le=100, description="Number of top posts to return"),
    trending_topics_limit: int = Query(10, ge=1, le=50, description="Number of trending topics")
):
    """
    Get content analytics including top posts and trending topics.

    Returns the best performing posts and most discussed topics
    within the specified time period.
    """
    await verify_admin(current_user)

    start_dt, end_dt = parse_date_range(start_date, end_date)

    top_posts = []
    trending_topics = []
    total_posts = 0
    total_engagement = 0

    async with async_session_factory() as session:
        # Get top posts by engagement
        posts_query = (
            select(PostDB, BotProfileDB, CommunityDB)
            .join(BotProfileDB, PostDB.author_id == BotProfileDB.id)
            .join(CommunityDB, PostDB.community_id == CommunityDB.id)
            .where(
                PostDB.created_at >= start_dt,
                PostDB.created_at <= end_dt,
                PostDB.is_deleted == False
            )
            .order_by(desc(PostDB.like_count + PostDB.comment_count))
            .limit(top_posts_limit)
        )
        posts_result = await session.execute(posts_query)
        posts_rows = posts_result.all()

        for post, author, community in posts_rows:
            engagement_score = post.like_count + (post.comment_count * 2)

            top_posts.append(TopPostItem(
                post_id=post.id,
                content_preview=post.content[:200] if post.content else "",
                author_id=author.id,
                author_name=author.display_name,
                author_handle=author.handle,
                is_bot_author=True,
                community_id=community.id,
                community_name=community.name,
                likes=post.like_count,
                comments=post.comment_count,
                views=0,  # Would need view tracking
                engagement_score=engagement_score,
                created_at=post.created_at
            ))

            total_engagement += post.like_count + post.comment_count

        # Count total posts in period
        total_posts = (await session.execute(
            select(func.count(PostDB.id)).where(
                PostDB.created_at >= start_dt,
                PostDB.created_at <= end_dt,
                PostDB.is_deleted == False
            )
        )).scalar() or 0

        # Extract trending topics from post content
        # This is a simplified approach - in production you'd use proper NLP/hashtag extraction
        # For now, we'll look for hashtags in post content
        posts_for_topics = await session.execute(
            select(PostDB.content).where(
                PostDB.created_at >= start_dt,
                PostDB.created_at <= end_dt,
                PostDB.is_deleted == False,
                PostDB.content.isnot(None)
            )
        )
        topic_counts: Dict[str, Dict[str, int]] = {}

        for (content,) in posts_for_topics:
            if content:
                # Simple hashtag extraction
                import re
                hashtags = re.findall(r'#(\w+)', content.lower())
                for tag in hashtags:
                    if tag not in topic_counts:
                        topic_counts[tag] = {"count": 0, "posts": 0}
                    topic_counts[tag]["count"] += 1
                    topic_counts[tag]["posts"] += 1

        # Sort and limit trending topics
        sorted_topics = sorted(
            topic_counts.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )[:trending_topics_limit]

        for topic, counts in sorted_topics:
            trending_topics.append(TrendingTopicItem(
                topic=f"#{topic}",
                mention_count=counts["count"],
                post_count=counts["posts"],
                engagement_total=0,  # Would need more complex query
                trend_velocity=0.0
            ))

    return ContentMetricsResponse(
        top_posts=top_posts,
        trending_topics=trending_topics,
        content_summary={
            "total_posts": total_posts,
            "total_engagement": total_engagement,
            "avg_engagement_per_post": round(total_engagement / total_posts, 2) if total_posts > 0 else 0,
            "unique_topics": len(topic_counts),
            "posts_with_hashtags": sum(1 for t in topic_counts.values() if t["posts"] > 0),
        },
        start_date=start_dt.isoformat(),
        end_date=end_dt.isoformat(),
        granularity=granularity.value
    )


@dashboard_router.get("/realtime", response_model=RealtimeMetrics)
async def get_realtime_metrics(
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Get real-time live metrics for the dashboard.

    Returns current active users, live session counts, and recent activity.
    Designed for live dashboard updates.
    """
    await verify_admin(current_user)

    now = datetime.utcnow()
    one_hour_ago = now - timedelta(hours=1)
    five_min_ago = now - timedelta(minutes=5)
    fifteen_min_ago = now - timedelta(minutes=15)

    async with async_session_factory() as session:
        # Active users (active in last 15 minutes)
        active_users_now = (await session.execute(
            select(func.count(AppUserDB.id)).where(
                AppUserDB.last_active >= fifteen_min_ago
            )
        )).scalar() or 0

        # Active bots (not paused and active recently)
        active_bots_now = (await session.execute(
            select(func.count(BotProfileDB.id)).where(
                BotProfileDB.is_active == True,
                BotProfileDB.is_paused == False,
                BotProfileDB.last_active >= fifteen_min_ago
            )
        )).scalar() or 0

        # Active sessions (started within last hour, not ended)
        active_sessions = (await session.execute(
            select(func.count(SessionDB.id)).where(
                SessionDB.started_at >= one_hour_ago,
                SessionDB.ended_at.is_(None)
            )
        )).scalar() or 0

        # Last hour metrics
        posts_last_hour = (await session.execute(
            select(func.count(PostDB.id)).where(
                PostDB.created_at >= one_hour_ago
            )
        )).scalar() or 0

        comments_last_hour = (await session.execute(
            select(func.count(PostCommentDB.id)).where(
                PostCommentDB.created_at >= one_hour_ago
            )
        )).scalar() or 0

        likes_last_hour = (await session.execute(
            select(func.count(PostLikeDB.id)).where(
                PostLikeDB.created_at >= one_hour_ago
            )
        )).scalar() or 0

        dms_last_hour = (await session.execute(
            select(func.count(DirectMessageDB.id)).where(
                DirectMessageDB.created_at >= one_hour_ago
            )
        )).scalar() or 0

        chats_last_hour = (await session.execute(
            select(func.count(CommunityChatMessageDB.id)).where(
                CommunityChatMessageDB.created_at >= one_hour_ago
            )
        )).scalar() or 0

        # Events in last 5 minutes
        events_last_5min = (
            (await session.execute(
                select(func.count(PostDB.id)).where(PostDB.created_at >= five_min_ago)
            )).scalar() or 0
        ) + (
            (await session.execute(
                select(func.count(PostCommentDB.id)).where(PostCommentDB.created_at >= five_min_ago)
            )).scalar() or 0
        ) + (
            (await session.execute(
                select(func.count(PostLikeDB.id)).where(PostLikeDB.created_at >= five_min_ago)
            )).scalar() or 0
        )

        # Trending communities (most activity in last hour)
        community_activity = await session.execute(
            select(
                CommunityDB.id,
                CommunityDB.name,
                func.count(PostDB.id).label("post_count")
            )
            .join(PostDB, PostDB.community_id == CommunityDB.id)
            .where(PostDB.created_at >= one_hour_ago)
            .group_by(CommunityDB.id, CommunityDB.name)
            .order_by(desc("post_count"))
            .limit(5)
        )
        trending_communities = [
            {"id": str(row[0]), "name": row[1], "activity": row[2]}
            for row in community_activity
        ]

        # Recent activity feed
        recent_posts = await session.execute(
            select(PostDB, BotProfileDB)
            .join(BotProfileDB, PostDB.author_id == BotProfileDB.id)
            .where(PostDB.created_at >= five_min_ago)
            .order_by(desc(PostDB.created_at))
            .limit(5)
        )
        recent_activity = [
            {
                "type": "post",
                "author": row[1].display_name,
                "preview": row[0].content[:50] if row[0].content else "",
                "timestamp": row[0].created_at.isoformat()
            }
            for row in recent_posts
        ]

    return RealtimeMetrics(
        active_users_now=active_users_now,
        active_bots_now=active_bots_now,
        active_sessions=active_sessions,
        posts_last_hour=posts_last_hour,
        comments_last_hour=comments_last_hour,
        likes_last_hour=likes_last_hour,
        dms_last_hour=dms_last_hour,
        chats_last_hour=chats_last_hour,
        events_last_5min=events_last_5min,
        trending_communities=trending_communities,
        recent_activity=recent_activity,
        timestamp=now,
        server_time=now.isoformat()
    )


# ============================================================================
# HEATMAP ENDPOINTS
# ============================================================================

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@dashboard_router.get("/heatmap", response_model=ActivityHeatmapResponse)
async def get_activity_heatmap(
    days: int = Query(default=30, ge=7, le=90, description="Number of days to analyze"),
    metric: Literal["posts", "comments", "likes", "all"] = Query(
        default="posts",
        description="Type of activity to measure"
    )
):
    """
    Get activity heatmap data showing activity patterns by hour of day and day of week.

    Returns a grid of activity counts suitable for heatmap visualization.
    Each cell represents the activity count for a specific hour (0-23) and day of week (0-6).

    The data includes:
    - cells: Array of heatmap cells with hour, day, value, and normalized value
    - max_value: Maximum activity count in any cell (for color scaling)
    - peak_hour: Hour with highest overall activity
    - peak_day: Day of week with highest overall activity
    """
    now = datetime.utcnow()
    cutoff = now - timedelta(days=days)

    # Initialize heatmap grid: heatmap[day_of_week][hour] = count
    heatmap_data: Dict[int, Dict[int, int]] = {
        dow: {hour: 0 for hour in range(24)}
        for dow in range(7)
    }

    async with async_session_factory() as session:
        # Query activity counts grouped by day of week and hour
        # PostgreSQL: extract(dow from timestamp) returns 0=Sunday, 1=Monday, etc.
        # We convert to Python convention: 0=Monday, 6=Sunday

        if metric in ("posts", "all"):
            # Get posts by hour and day of week
            posts_stmt = select(
                func.extract("dow", PostDB.created_at).label("dow"),
                func.extract("hour", PostDB.created_at).label("hour"),
                func.count(PostDB.id).label("count")
            ).where(
                and_(
                    PostDB.created_at >= cutoff,
                    PostDB.is_deleted == False
                )
            ).group_by(
                func.extract("dow", PostDB.created_at),
                func.extract("hour", PostDB.created_at)
            )
            posts_result = await session.execute(posts_stmt)
            for row in posts_result:
                # Convert PostgreSQL dow (0=Sunday) to Python (0=Monday)
                pg_dow = int(row.dow)
                py_dow = (pg_dow - 1) % 7 if pg_dow > 0 else 6
                hour = int(row.hour)
                heatmap_data[py_dow][hour] += row.count

        if metric in ("comments", "all"):
            # Get comments by hour and day of week
            comments_stmt = select(
                func.extract("dow", PostCommentDB.created_at).label("dow"),
                func.extract("hour", PostCommentDB.created_at).label("hour"),
                func.count(PostCommentDB.id).label("count")
            ).where(
                and_(
                    PostCommentDB.created_at >= cutoff,
                    PostCommentDB.is_deleted == False
                )
            ).group_by(
                func.extract("dow", PostCommentDB.created_at),
                func.extract("hour", PostCommentDB.created_at)
            )
            comments_result = await session.execute(comments_stmt)
            for row in comments_result:
                pg_dow = int(row.dow)
                py_dow = (pg_dow - 1) % 7 if pg_dow > 0 else 6
                hour = int(row.hour)
                heatmap_data[py_dow][hour] += row.count

        if metric in ("likes", "all"):
            # Get likes by hour and day of week
            likes_stmt = select(
                func.extract("dow", PostLikeDB.created_at).label("dow"),
                func.extract("hour", PostLikeDB.created_at).label("hour"),
                func.count(PostLikeDB.id).label("count")
            ).where(
                PostLikeDB.created_at >= cutoff
            ).group_by(
                func.extract("dow", PostLikeDB.created_at),
                func.extract("hour", PostLikeDB.created_at)
            )
            likes_result = await session.execute(likes_stmt)
            for row in likes_result:
                pg_dow = int(row.dow)
                py_dow = (pg_dow - 1) % 7 if pg_dow > 0 else 6
                hour = int(row.hour)
                heatmap_data[py_dow][hour] += row.count

    # Calculate statistics
    max_value = 0
    total_activity = 0
    hour_totals: Dict[int, int] = {h: 0 for h in range(24)}
    day_totals: Dict[int, int] = {d: 0 for d in range(7)}

    for dow in range(7):
        for hour in range(24):
            value = heatmap_data[dow][hour]
            total_activity += value
            hour_totals[hour] += value
            day_totals[dow] += value
            if value > max_value:
                max_value = value

    # Find peaks
    peak_hour = max(hour_totals, key=lambda h: hour_totals[h]) if hour_totals else 0
    peak_day = max(day_totals, key=lambda d: day_totals[d]) if day_totals else 0

    # Build response cells with normalization
    cells: List[HeatmapCell] = []
    for dow in range(7):
        for hour in range(24):
            value = heatmap_data[dow][hour]
            normalized = value / max_value if max_value > 0 else 0.0
            cells.append(HeatmapCell(
                hour=hour,
                day_of_week=dow,
                day_name=DAY_NAMES[dow],
                value=value,
                normalized=round(normalized, 4)
            ))

    return ActivityHeatmapResponse(
        cells=cells,
        max_value=max_value,
        total_activity=total_activity,
        peak_hour=peak_hour,
        peak_day=peak_day,
        peak_day_name=DAY_NAMES[peak_day],
        metric_type=metric,
        days_analyzed=days,
        generated_at=now
    )


# ============================================================================
# SENTIMENT ANALYSIS
# ============================================================================

# Keyword lists for sentiment analysis
POSITIVE_KEYWORDS = {
    # Emotions
    "happy", "joy", "love", "excited", "amazing", "wonderful", "fantastic",
    "great", "awesome", "excellent", "brilliant", "perfect", "beautiful",
    "blessed", "grateful", "thankful", "appreciate", "delighted", "thrilled",
    # Actions/States
    "celebrate", "success", "win", "achieve", "proud", "inspire", "hope",
    "laugh", "smile", "enjoy", "fun", "best", "favorite", "recommend",
    # Affirmations
    "yes", "absolutely", "definitely", "agree", "support", "helpful",
    "kind", "friendly", "caring", "generous", "thoughtful", "creative",
}

NEGATIVE_KEYWORDS = {
    # Emotions
    "sad", "angry", "hate", "upset", "disappointed", "frustrated", "annoyed",
    "terrible", "awful", "horrible", "worst", "bad", "poor", "ugly",
    "depressed", "anxious", "worried", "stressed", "miserable", "unhappy",
    # Actions/States
    "fail", "failure", "problem", "issue", "bug", "broken", "wrong",
    "mistake", "error", "crash", "loss", "lost", "hurt", "pain",
    # Negations
    "no", "never", "cannot", "refuse", "reject", "disagree", "dislike",
    "boring", "useless", "pointless", "waste", "stupid", "ridiculous",
}


def analyze_sentiment_keywords(text: str) -> tuple[SentimentCategory, float]:
    """
    Analyze sentiment using keyword matching.

    Returns a tuple of (sentiment_category, confidence_score).
    Confidence is based on keyword density and strength.
    """
    if not text:
        return SentimentCategory.NEUTRAL, 0.5

    words = set(text.lower().split())
    # Also check for partial matches (e.g., "loving" contains "love")
    text_lower = text.lower()

    positive_count = 0
    negative_count = 0

    for word in POSITIVE_KEYWORDS:
        if word in words or word in text_lower:
            positive_count += 1

    for word in NEGATIVE_KEYWORDS:
        if word in words or word in text_lower:
            negative_count += 1

    total_sentiment_words = positive_count + negative_count

    if total_sentiment_words == 0:
        return SentimentCategory.NEUTRAL, 0.5

    # Calculate sentiment based on ratio
    positive_ratio = positive_count / total_sentiment_words
    negative_ratio = negative_count / total_sentiment_words

    # Determine confidence based on how many sentiment words were found
    word_count = len(words)
    keyword_density = min(total_sentiment_words / max(word_count, 1), 1.0)
    base_confidence = 0.5 + (keyword_density * 0.3)

    if positive_ratio > 0.6:
        confidence = base_confidence + (positive_ratio - 0.5) * 0.4
        return SentimentCategory.POSITIVE, min(confidence, 0.95)
    elif negative_ratio > 0.6:
        confidence = base_confidence + (negative_ratio - 0.5) * 0.4
        return SentimentCategory.NEGATIVE, min(confidence, 0.95)
    else:
        # Mixed or neutral
        return SentimentCategory.NEUTRAL, base_confidence


async def analyze_sentiment_llm(
    texts: List[str],
    llm_client
) -> List[tuple[SentimentCategory, float]]:
    """
    Analyze sentiment using LLM for more accurate results.
    Falls back to keyword analysis if LLM fails.
    """
    from mind.core.llm_client import LLMRequest

    results = []

    for text in texts:
        try:
            prompt = f"""Analyze the sentiment of the following text and respond with ONLY one word: POSITIVE, NEUTRAL, or NEGATIVE.

Text: "{text[:500]}"

Sentiment:"""

            response = await llm_client.generate(LLMRequest(
                prompt=prompt,
                max_tokens=10,
                temperature=0.1
            ))

            sentiment_text = response.text.strip().upper()

            if "POSITIVE" in sentiment_text:
                results.append((SentimentCategory.POSITIVE, 0.85))
            elif "NEGATIVE" in sentiment_text:
                results.append((SentimentCategory.NEGATIVE, 0.85))
            else:
                results.append((SentimentCategory.NEUTRAL, 0.85))

        except Exception:
            # Fall back to keyword analysis
            results.append(analyze_sentiment_keywords(text))

    return results


@dashboard_router.get("/sentiment", response_model=SentimentAnalysisResponse)
async def get_sentiment_analysis(
    current_user: AuthenticatedUser = Depends(get_current_user),
    start_date: Optional[str] = Query(None, description="Start date (ISO format or YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format or YYYY-MM-DD)"),
    content_type: Literal["posts", "messages", "all"] = Query("posts", description="Type of content to analyze"),
    use_llm: bool = Query(False, description="Use LLM for more accurate sentiment analysis"),
    limit: int = Query(100, ge=10, le=500, description="Maximum items to analyze"),
    granularity: Granularity = Query(Granularity.DAY, description="Time granularity for trends")
):
    """
    Analyze sentiment of bot posts and messages.

    Returns sentiment distribution (positive/neutral/negative), trends over time,
    and samples of the most positive and negative content.

    Uses keyword-based analysis by default. Set use_llm=true for more accurate
    but slower LLM-based analysis.
    """
    await verify_admin(current_user)

    start_dt, end_dt = parse_date_range(start_date, end_date)

    # Collect content to analyze
    content_items: List[Dict[str, Any]] = []

    async with async_session_factory() as session:
        # Get posts if requested
        if content_type in ("posts", "all"):
            posts_stmt = (
                select(PostDB, BotProfileDB.handle)
                .join(BotProfileDB, PostDB.author_id == BotProfileDB.id)
                .where(
                    PostDB.created_at >= start_dt,
                    PostDB.created_at <= end_dt,
                    PostDB.is_deleted == False
                )
                .order_by(desc(PostDB.created_at))
                .limit(limit if content_type == "posts" else limit // 2)
            )
            posts_result = await session.execute(posts_stmt)
            posts = posts_result.all()

            for post, author_handle in posts:
                content_items.append({
                    "id": post.id,
                    "content": post.content,
                    "author_handle": author_handle,
                    "created_at": post.created_at,
                    "type": "post"
                })

        # Get messages if requested
        if content_type in ("messages", "all"):
            # Community chat messages from bots
            messages_stmt = (
                select(CommunityChatMessageDB, BotProfileDB.handle)
                .join(BotProfileDB, CommunityChatMessageDB.author_id == BotProfileDB.id)
                .where(
                    CommunityChatMessageDB.created_at >= start_dt,
                    CommunityChatMessageDB.created_at <= end_dt,
                    CommunityChatMessageDB.is_deleted == False,
                    CommunityChatMessageDB.is_bot == True
                )
                .order_by(desc(CommunityChatMessageDB.created_at))
                .limit(limit if content_type == "messages" else limit // 2)
            )
            messages_result = await session.execute(messages_stmt)
            messages = messages_result.all()

            for msg, author_handle in messages:
                content_items.append({
                    "id": msg.id,
                    "content": msg.content,
                    "author_handle": author_handle,
                    "created_at": msg.created_at,
                    "type": "message"
                })

    if not content_items:
        return SentimentAnalysisResponse(
            distribution=SentimentDistribution(),
            trends=[],
            top_positive=[],
            top_negative=[],
            analysis_method="keyword",
            start_date=start_dt.isoformat(),
            end_date=end_dt.isoformat(),
            content_type=content_type
        )

    # Analyze sentiment
    analyzed_items: List[Dict[str, Any]] = []

    if use_llm:
        try:
            from mind.core.llm_client import get_cached_client
            llm_client = await get_cached_client()
            texts = [item["content"] for item in content_items]
            sentiments = await analyze_sentiment_llm(texts, llm_client)
            analysis_method = "llm"
        except Exception:
            # Fall back to keyword analysis
            sentiments = [analyze_sentiment_keywords(item["content"]) for item in content_items]
            analysis_method = "keyword"
    else:
        sentiments = [analyze_sentiment_keywords(item["content"]) for item in content_items]
        analysis_method = "keyword"

    for item, (sentiment, confidence) in zip(content_items, sentiments):
        analyzed_items.append({
            **item,
            "sentiment": sentiment,
            "confidence": confidence
        })

    # Calculate distribution
    positive_count = sum(1 for item in analyzed_items if item["sentiment"] == SentimentCategory.POSITIVE)
    neutral_count = sum(1 for item in analyzed_items if item["sentiment"] == SentimentCategory.NEUTRAL)
    negative_count = sum(1 for item in analyzed_items if item["sentiment"] == SentimentCategory.NEGATIVE)
    total = len(analyzed_items)

    distribution = SentimentDistribution(
        positive_count=positive_count,
        positive_percentage=round((positive_count / total) * 100, 2) if total > 0 else 0,
        neutral_count=neutral_count,
        neutral_percentage=round((neutral_count / total) * 100, 2) if total > 0 else 0,
        negative_count=negative_count,
        negative_percentage=round((negative_count / total) * 100, 2) if total > 0 else 0,
        total_analyzed=total
    )

    # Calculate trends by time buckets
    buckets = get_time_buckets(start_dt, end_dt, granularity)
    trends = []

    for bucket_start, bucket_end, label in buckets:
        bucket_items = [
            item for item in analyzed_items
            if bucket_start <= item["created_at"] < bucket_end
        ]

        bucket_positive = sum(1 for item in bucket_items if item["sentiment"] == SentimentCategory.POSITIVE)
        bucket_neutral = sum(1 for item in bucket_items if item["sentiment"] == SentimentCategory.NEUTRAL)
        bucket_negative = sum(1 for item in bucket_items if item["sentiment"] == SentimentCategory.NEGATIVE)

        # Determine dominant sentiment
        if bucket_positive >= bucket_neutral and bucket_positive >= bucket_negative:
            dominant = SentimentCategory.POSITIVE
        elif bucket_negative >= bucket_neutral:
            dominant = SentimentCategory.NEGATIVE
        else:
            dominant = SentimentCategory.NEUTRAL

        trends.append(SentimentTrend(
            timestamp=bucket_start.isoformat(),
            label=label,
            positive=bucket_positive,
            neutral=bucket_neutral,
            negative=bucket_negative,
            dominant_sentiment=dominant
        ))

    # Get top positive and negative samples
    positive_items = sorted(
        [item for item in analyzed_items if item["sentiment"] == SentimentCategory.POSITIVE],
        key=lambda x: x["confidence"],
        reverse=True
    )[:5]

    negative_items = sorted(
        [item for item in analyzed_items if item["sentiment"] == SentimentCategory.NEGATIVE],
        key=lambda x: x["confidence"],
        reverse=True
    )[:5]

    top_positive = [
        SentimentSample(
            content_id=item["id"],
            content_preview=item["content"][:100] + "..." if len(item["content"]) > 100 else item["content"],
            sentiment=item["sentiment"],
            confidence=round(item["confidence"], 3),
            author_handle=item["author_handle"],
            created_at=item["created_at"]
        )
        for item in positive_items
    ]

    top_negative = [
        SentimentSample(
            content_id=item["id"],
            content_preview=item["content"][:100] + "..." if len(item["content"]) > 100 else item["content"],
            sentiment=item["sentiment"],
            confidence=round(item["confidence"], 3),
            author_handle=item["author_handle"],
            created_at=item["created_at"]
        )
        for item in negative_items
    ]

    return SentimentAnalysisResponse(
        distribution=distribution,
        trends=trends,
        top_positive=top_positive,
        top_negative=top_negative,
        analysis_method=analysis_method,
        start_date=start_dt.isoformat(),
        end_date=end_dt.isoformat(),
        content_type=content_type
    )


# ============================================================================
# TRACKING ENDPOINTS
# ============================================================================

@router.post("/track/view")
async def track_post_view(
    post_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Track a post view event.

    Called when a user views a post in detail.
    """
    tracker = await get_analytics_tracker()
    is_new = await tracker.track_post_view(
        post_id=post_id,
        viewer_id=current_user.id,
        viewer_is_bot=False
    )

    return {"tracked": True, "is_new_view": is_new}


@router.post("/track/session")
async def track_session(
    duration_seconds: float,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """
    Track a user session.

    Called when a user's session ends to record duration.
    """
    tracker = await get_analytics_tracker()
    success = await tracker.track_session(
        user_id=current_user.id,
        duration_seconds=duration_seconds
    )

    return {"tracked": success}
