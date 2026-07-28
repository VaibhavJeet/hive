"""
Settings API routes - System configuration management.
Provides endpoints for reading and updating platform settings.
"""

from datetime import datetime

from mind.core.time import utcnow
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mind.api.routes.admin import require_admin
from mind.core.database import async_session_factory, AppUserDB, get_session


router = APIRouter(prefix="/settings", tags=["settings"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class GeneralSettings(BaseModel):
    """General platform settings."""
    site_name: str = Field(default="Hive", max_length=100)
    site_description: str = Field(default="Digital civilization observation portal", max_length=500)
    maintenance_mode: bool = Field(default=False)
    debug_mode: bool = Field(default=False)


class BotSettings(BaseModel):
    """Bot configuration settings."""
    max_active_bots: int = Field(default=25, ge=1, le=100)
    response_delay: int = Field(default=3, ge=1, le=30)
    activity_level: int = Field(default=75, ge=0, le=100)
    auto_learning: bool = Field(default=True)
    emotional_engine: bool = Field(default=True)
    context_memory: bool = Field(default=True)


class AuthSettings(BaseModel):
    """Authentication and security settings."""
    jwt_expiry_hours: int = Field(default=24, ge=1, le=168)
    refresh_token_expiry_days: int = Field(default=7, ge=1, le=30)
    max_login_attempts: int = Field(default=5, ge=1, le=10)
    lockout_duration_minutes: int = Field(default=15, ge=5, le=60)
    two_factor_enabled: bool = Field(default=True)
    session_timeout_minutes: int = Field(default=30, ge=5, le=120)


class ModerationSettings(BaseModel):
    """Content moderation settings."""
    auto_flag_threshold: int = Field(default=70, ge=0, le=100)
    toxicity_threshold: int = Field(default=60, ge=0, le=100)
    spam_detection: bool = Field(default=True)
    profanity_filter: bool = Field(default=True)
    image_moderation: bool = Field(default=True)
    link_scanning: bool = Field(default=True)


class NotificationSettings(BaseModel):
    """Notification settings."""
    email_notifications: bool = Field(default=True)
    push_notifications: bool = Field(default=True)
    sms_notifications: bool = Field(default=False)
    admin_alerts: bool = Field(default=True)
    report_digest: str = Field(default="daily", pattern="^(hourly|daily|weekly)$")
    critical_alerts_email: str = Field(default="admin@hive.local", max_length=255)


class AllSettings(BaseModel):
    """Complete settings object."""
    general: GeneralSettings = Field(default_factory=GeneralSettings)
    bot: BotSettings = Field(default_factory=BotSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    moderation: ModerationSettings = Field(default_factory=ModerationSettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    updated_at: Optional[str] = None


class UpdateSettingsRequest(BaseModel):
    """Request to update settings."""
    general: Optional[GeneralSettings] = None
    bot: Optional[BotSettings] = None
    auth: Optional[AuthSettings] = None
    moderation: Optional[ModerationSettings] = None
    notifications: Optional[NotificationSettings] = None


# ============================================================================
# IN-MEMORY SETTINGS STORE
# ============================================================================

# For now, we use an in-memory store. In production, this would be persisted
# to the database. This approach allows the settings to work without requiring
# a database migration immediately.

# ⚠️ HIVE-136: this is a module-level dict, not storage.
#   - it resets to defaults on every restart
#   - with API_WORKERS=4 each worker holds its own copy, so a PUT lands on one
#     worker and a subsequent GET may read another
#   - nothing outside this file reads it: no engine, loop, or middleware consumes
#     any of these values, so changing them has no effect on the platform
# The endpoints below are correctly gated (HIVE-007); the feature underneath is not
# implemented. See HIVE-136.
_settings_store: Dict[str, Any] = {
    "general": GeneralSettings().model_dump(),
    "bot": BotSettings().model_dump(),
    "auth": AuthSettings().model_dump(),
    "moderation": ModerationSettings().model_dump(),
    "notifications": NotificationSettings().model_dump(),
    "updated_at": utcnow().isoformat(),
}


def get_all_settings() -> AllSettings:
    """Get all settings from the store."""
    return AllSettings(
        general=GeneralSettings(**_settings_store["general"]),
        bot=BotSettings(**_settings_store["bot"]),
        auth=AuthSettings(**_settings_store["auth"]),
        moderation=ModerationSettings(**_settings_store["moderation"]),
        notifications=NotificationSettings(**_settings_store["notifications"]),
        updated_at=_settings_store.get("updated_at"),
    )


def update_settings(updates: UpdateSettingsRequest) -> AllSettings:
    """Update settings in the store."""
    if updates.general:
        _settings_store["general"] = updates.general.model_dump()
    if updates.bot:
        _settings_store["bot"] = updates.bot.model_dump()
    if updates.auth:
        _settings_store["auth"] = updates.auth.model_dump()
    if updates.moderation:
        _settings_store["moderation"] = updates.moderation.model_dump()
    if updates.notifications:
        _settings_store["notifications"] = updates.notifications.model_dump()

    _settings_store["updated_at"] = utcnow().isoformat()

    return get_all_settings()


def reset_settings() -> AllSettings:
    """Reset all settings to defaults."""
    global _settings_store
    _settings_store = {
        "general": GeneralSettings().model_dump(),
        "bot": BotSettings().model_dump(),
        "auth": AuthSettings().model_dump(),
        "moderation": ModerationSettings().model_dump(),
        "notifications": NotificationSettings().model_dump(),
        "updated_at": utcnow().isoformat(),
    }
    return get_all_settings()


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("", response_model=AllSettings)
async def get_settings(admin: AppUserDB = Depends(require_admin)):
    """
    Get all platform settings.

    Returns the current configuration for all setting categories:
    - General: Site name, description, maintenance mode
    - Bot: Bot behavior configuration
    - Auth: Authentication and security settings
    - Moderation: Content moderation thresholds
    - Notifications: Alert and notification preferences
    """
    return get_all_settings()


@router.put("", response_model=AllSettings)
async def update_all_settings(
    request: UpdateSettingsRequest,
    admin: AppUserDB = Depends(require_admin),
):
    """
    Update platform settings.

    Only the provided sections will be updated. Omitted sections
    will retain their current values.
    """
    return update_settings(request)


@router.post("/reset", response_model=AllSettings)
async def reset_all_settings(admin: AppUserDB = Depends(require_admin)):
    """
    Reset all settings to their default values.
    """
    return reset_settings()


@router.get("/general", response_model=GeneralSettings)
async def get_general_settings(admin: AppUserDB = Depends(require_admin)):
    """Get general platform settings."""
    return GeneralSettings(**_settings_store["general"])


@router.put("/general", response_model=GeneralSettings)
async def update_general_settings(
    settings: GeneralSettings,
    admin: AppUserDB = Depends(require_admin),
):
    """Update general platform settings."""
    _settings_store["general"] = settings.model_dump()
    _settings_store["updated_at"] = utcnow().isoformat()
    return settings


@router.get("/bot", response_model=BotSettings)
async def get_bot_settings(admin: AppUserDB = Depends(require_admin)):
    """Get bot configuration settings."""
    return BotSettings(**_settings_store["bot"])


@router.put("/bot", response_model=BotSettings)
async def update_bot_settings(
    settings: BotSettings,
    admin: AppUserDB = Depends(require_admin),
):
    """Update bot configuration settings."""
    _settings_store["bot"] = settings.model_dump()
    _settings_store["updated_at"] = utcnow().isoformat()
    return settings


@router.get("/auth", response_model=AuthSettings)
async def get_auth_settings(admin: AppUserDB = Depends(require_admin)):
    """Get authentication settings."""
    return AuthSettings(**_settings_store["auth"])


@router.put("/auth", response_model=AuthSettings)
async def update_auth_settings(
    settings: AuthSettings,
    admin: AppUserDB = Depends(require_admin),
):
    """Update authentication settings."""
    _settings_store["auth"] = settings.model_dump()
    _settings_store["updated_at"] = utcnow().isoformat()
    return settings


@router.get("/moderation", response_model=ModerationSettings)
async def get_moderation_settings(admin: AppUserDB = Depends(require_admin)):
    """Get content moderation settings."""
    return ModerationSettings(**_settings_store["moderation"])


@router.put("/moderation", response_model=ModerationSettings)
async def update_moderation_settings(
    settings: ModerationSettings,
    admin: AppUserDB = Depends(require_admin),
):
    """Update content moderation settings."""
    _settings_store["moderation"] = settings.model_dump()
    _settings_store["updated_at"] = utcnow().isoformat()
    return settings


@router.get("/notifications", response_model=NotificationSettings)
async def get_notification_settings(admin: AppUserDB = Depends(require_admin)):
    """Get notification settings."""
    return NotificationSettings(**_settings_store["notifications"])


@router.put("/notifications", response_model=NotificationSettings)
async def update_notification_settings(
    settings: NotificationSettings,
    admin: AppUserDB = Depends(require_admin),
):
    """Update notification settings."""
    _settings_store["notifications"] = settings.model_dump()
    _settings_store["updated_at"] = utcnow().isoformat()
    return settings
