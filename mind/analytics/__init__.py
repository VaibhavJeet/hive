"""
Analytics and engagement tracking for AI Community Companions.
"""

from mind.analytics.models import (
    EngagementMetrics,
    BotPerformance,
    UserActivity,
    TimeSeriesData,
    PlatformMetrics,
)
from mind.analytics.tracker import AnalyticsTracker, get_analytics_tracker
from mind.analytics.aggregator import AnalyticsAggregator, get_analytics_aggregator
from mind.analytics.background_tasks import (
    DailyMetricsAggregator,
    get_daily_metrics_aggregator,
    start_analytics_background_tasks,
    stop_analytics_background_tasks,
)

__all__ = [
    "EngagementMetrics",
    "BotPerformance",
    "UserActivity",
    "TimeSeriesData",
    "PlatformMetrics",
    "AnalyticsTracker",
    "get_analytics_tracker",
    "AnalyticsAggregator",
    "get_analytics_aggregator",
    "DailyMetricsAggregator",
    "get_daily_metrics_aggregator",
    "start_analytics_background_tasks",
    "stop_analytics_background_tasks",
]
