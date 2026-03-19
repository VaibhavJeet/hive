"""API Routes for AI Community Companions."""

from mind.api.routes.feed import router as feed_router
from mind.api.routes.chat import router as chat_router
from mind.api.routes.users import router as users_router
from mind.api.routes.auth import router as auth_router
from mind.api.routes.metrics import router as metrics_router
from mind.api.routes.search import router as search_router
from mind.api.routes.admin import router as admin_router
from mind.api.routes.notifications import router as notifications_router
from mind.api.routes.blocking import router as blocking_router
from mind.api.routes.moderation import router as moderation_router
from mind.api.routes.hashtags import router as hashtags_router
from mind.api.routes.media import router as media_router
from mind.api.routes.analytics import router as analytics_router
from mind.api.routes.analytics import admin_router as analytics_admin_router
from mind.api.routes.analytics import dashboard_router as analytics_dashboard_router
from mind.api.routes.stories import router as stories_router
from mind.api.routes.scaling import router as scaling_router
from mind.api.routes.civilization import router as civilization_router

__all__ = [
    "feed_router", "chat_router", "users_router",
    "auth_router", "metrics_router", "search_router", "admin_router",
    "notifications_router", "blocking_router", "moderation_router",
    "hashtags_router", "media_router", "analytics_router", "analytics_admin_router",
    "analytics_dashboard_router", "stories_router", "scaling_router", "civilization_router"
]
