"""
Analytics data models for AI Community Companions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Any
from uuid import UUID


@dataclass
class EngagementMetrics:
    """Engagement metrics for a specific entity (post, bot, user)."""

    # View metrics
    total_views: int = 0
    unique_viewers: int = 0

    # Interaction metrics
    likes: int = 0
    comments: int = 0
    shares: int = 0

    # Chat metrics
    chat_messages: int = 0
    dm_messages: int = 0

    # Calculated metrics
    engagement_rate: float = 0.0  # (likes + comments + shares) / views
    avg_session_duration: float = 0.0  # in seconds

    # Time-based
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None

    def calculate_engagement_rate(self) -> float:
        """Calculate engagement rate from metrics."""
        if self.total_views == 0:
            return 0.0
        total_interactions = self.likes + self.comments + self.shares
        return round(total_interactions / self.total_views * 100, 2)


@dataclass
class BotPerformance:
    """Performance metrics for an AI bot."""

    # Identity
    bot_id: UUID = None
    bot_handle: str = ""
    bot_name: str = ""

    # Content production
    posts_created: int = 0
    comments_created: int = 0
    chat_messages_sent: int = 0
    dm_responses: int = 0

    # Engagement received
    total_likes_received: int = 0
    total_comments_received: int = 0
    avg_engagement_per_post: float = 0.0

    # Quality metrics
    avg_response_time_ms: float = 0.0
    user_satisfaction_score: float = 0.0  # Based on continued engagement
    naturalness_score: float = 0.0

    # Relationship metrics
    total_relationships: int = 0
    positive_relationships: int = 0
    negative_relationships: int = 0

    # Activity
    active_hours_per_day: float = 0.0
    last_active: Optional[datetime] = None

    # Period
    period_days: int = 7

    def calculate_avg_engagement(self) -> float:
        """Calculate average engagement per post."""
        if self.posts_created == 0:
            return 0.0
        return round(
            (self.total_likes_received + self.total_comments_received) / self.posts_created,
            2
        )


@dataclass
class UserActivity:
    """Activity metrics for a human user."""

    # Identity
    user_id: UUID = None
    display_name: str = ""

    # Content creation
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

    # Session metrics
    total_sessions: int = 0
    total_session_time: float = 0.0  # in seconds
    avg_session_duration: float = 0.0  # in seconds

    # Bot interactions
    bots_interacted_with: int = 0
    favorite_bot_id: Optional[UUID] = None
    favorite_bot_handle: str = ""

    # Community engagement
    communities_active_in: int = 0
    most_active_community_id: Optional[UUID] = None

    # Time tracking
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    period_days: int = 7


@dataclass
class TimeSeriesData:
    """Time series data for analytics charts."""

    # Series identification
    metric_name: str = ""
    entity_type: str = ""  # "platform", "bot", "user", "community"
    entity_id: Optional[UUID] = None

    # Time granularity
    granularity: str = "hour"  # "minute", "hour", "day", "week", "month"

    # Data points
    timestamps: List[datetime] = field(default_factory=list)
    values: List[float] = field(default_factory=list)

    # Optional metadata
    labels: List[str] = field(default_factory=list)

    # Calculated
    total: float = 0.0
    average: float = 0.0
    min_value: float = 0.0
    max_value: float = 0.0

    def calculate_stats(self):
        """Calculate summary statistics from values."""
        if not self.values:
            return
        self.total = sum(self.values)
        self.average = round(self.total / len(self.values), 2)
        self.min_value = min(self.values)
        self.max_value = max(self.values)


@dataclass
class PlatformMetrics:
    """Platform-wide metrics and analytics."""

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
    retired_bots: int = 0

    # Community metrics
    total_communities: int = 0
    active_communities: int = 0

    # Content metrics
    total_posts: int = 0
    posts_today: int = 0
    posts_this_week: int = 0

    total_comments: int = 0
    comments_today: int = 0
    comments_this_week: int = 0

    total_likes: int = 0
    likes_today: int = 0
    likes_this_week: int = 0

    # Chat metrics
    total_chat_messages: int = 0
    chat_messages_today: int = 0

    total_dm_messages: int = 0
    dm_messages_today: int = 0

    # Engagement metrics
    avg_posts_per_day: float = 0.0
    avg_comments_per_post: float = 0.0
    avg_likes_per_post: float = 0.0
    platform_engagement_rate: float = 0.0

    # Session metrics
    total_sessions_today: int = 0
    avg_session_duration: float = 0.0

    # Time info
    period_days: int = 7
    generated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.generated_at is None:
            self.generated_at = datetime.utcnow()


@dataclass
class TrendingContent:
    """Trending content item."""

    content_id: UUID = None
    content_type: str = ""  # "post", "comment"
    author_id: UUID = None
    author_name: str = ""
    author_handle: str = ""
    is_bot: bool = True

    content_preview: str = ""
    community_id: UUID = None
    community_name: str = ""

    # Engagement
    likes: int = 0
    comments: int = 0
    views: int = 0

    # Trend score
    trending_score: float = 0.0
    velocity: float = 0.0  # Rate of engagement increase

    created_at: Optional[datetime] = None
