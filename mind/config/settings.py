"""
Configuration settings for AI Community Companions.

This module provides a unified interface to all configuration through the
`settings` singleton. It uses the new centralized config system with
validation and hot-reload capability.

Usage:
    from mind.config.settings import settings

    # Access config values
    database_url = settings.DATABASE_URL
    max_bots = settings.MAX_ACTIVE_BOTS

    # Or access the full config
    from mind.config.settings import get_app_config
    config = get_app_config()
    print(config.database.pool_size)
"""

import logging
from pathlib import Path
from typing import Optional, List, Callable, Any
from functools import lru_cache
from enum import Enum

from pydantic_settings import BaseSettings
from pydantic import Field, computed_field

from mind.config.constants import (
    TIMING,
    CONTENT,
    POSTING,
    EMOTION,
    MEMORY,
    SCHEDULER,
    API,
    INFERENCE,
)

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS (kept for backward compatibility)
# =============================================================================

class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OLLAMA = "ollama"
    LLAMACPP = "llamacpp"
    OPENAI = "openai"


# =============================================================================
# SETTINGS CLASS
# =============================================================================

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    This class provides backward compatibility with the old settings interface
    while using the new centralized config system under the hood.
    """

    # Internal tracking for hot-reload
    _change_callbacks: List[Callable] = []

    # -------------------------------------------------------------------------
    # DATABASE
    # -------------------------------------------------------------------------

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://localhost:5432/mind",
        description="PostgreSQL connection string"
    )

    DATABASE_POOL_SIZE: int = Field(
        default=10,
        description="Database connection pool size"
    )

    DATABASE_MAX_OVERFLOW: int = Field(
        default=20,
        description="Maximum overflow connections"
    )

    # -------------------------------------------------------------------------
    # REDIS
    # -------------------------------------------------------------------------

    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection string for caching and pub/sub"
    )

    REDIS_MAX_CONNECTIONS: int = Field(
        default=10,
        description="Maximum number of Redis connections in pool"
    )

    REDIS_ENABLED: bool = Field(
        default=True,
        description="Enable Redis integration (gracefully degrades if unavailable)"
    )

    # -------------------------------------------------------------------------
    # CACHE
    # -------------------------------------------------------------------------

    CACHE_DEFAULT_TTL: int = Field(
        default=300,
        description="Default cache TTL in seconds (5 minutes)"
    )

    CACHE_LLM_RESPONSE_TTL: int = Field(
        default=3600,
        description="LLM response cache TTL in seconds (1 hour)"
    )

    CACHE_BOT_PROFILE_TTL: int = Field(
        default=300,
        description="Bot profile cache TTL in seconds (5 minutes)"
    )

    # -------------------------------------------------------------------------
    # LLM
    # -------------------------------------------------------------------------

    LLM_PROVIDER: LLMProvider = Field(default=LLMProvider.OLLAMA)
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434")
    OLLAMA_MODEL: str = Field(default="phi4-mini")  # Lightweight, fast for conversation
    OLLAMA_EMBEDDING_MODEL: str = Field(default="nomic-embed-text")

    # Multi-instance Ollama Configuration
    OLLAMA_INSTANCES: str = Field(
        default="http://localhost:11434",
        description="Comma-separated list of Ollama instance URLs"
    )
    LOAD_BALANCING_STRATEGY: str = Field(
        default="round_robin",
        description="Load balancing strategy: round_robin, least_loaded, random"
    )

    # Embedding Batch Configuration
    EMBEDDING_BATCH_SIZE: int = Field(
        default=32,
        description="Maximum batch size for embedding requests"
    )
    EMBEDDING_BATCH_INTERVAL: float = Field(
        default=5.0,
        description="Maximum seconds to wait before processing embedding batch"
    )

    # Inference Optimization
    LLM_MAX_CONCURRENT_REQUESTS: int = Field(default=8)
    LLM_REQUEST_TIMEOUT: int = Field(default=30)
    LLM_MAX_TOKENS: int = Field(default=512)
    LLM_TEMPERATURE: float = Field(default=0.8)
    INFERENCE_BATCH_SIZE: int = Field(default=4)

    # -------------------------------------------------------------------------
    # BOT ENGINE
    # -------------------------------------------------------------------------

    MAX_ACTIVE_BOTS: int = Field(
        default=12,
        description="Maximum number of active bots in the simulation (for performance)"
    )

    MAX_BOTS_PER_COMMUNITY: int = Field(default=150)
    MIN_BOTS_PER_COMMUNITY: int = Field(default=30)
    BOT_ACTIVITY_CHECK_INTERVAL: int = Field(default=60)  # seconds

    # Authenticity Mode
    AUTHENTICITY_DEMO_MODE: bool = Field(
        default=True,
        description="Demo mode: 10x faster timing for testing. Production: realistic human-like timing (minutes/hours)"
    )

    # Advanced Authenticity Settings
    AUTHENTICITY_TYPING_INDICATORS: bool = Field(
        default=True,
        description="Enable realistic typing indicators with personality-based duration"
    )
    AUTHENTICITY_READ_RECEIPTS: bool = Field(
        default=True,
        description="Enable gradual read receipts (seen status)"
    )
    AUTHENTICITY_DAILY_MOOD: bool = Field(
        default=True,
        description="Enable daily mood variations that affect bot behavior"
    )
    AUTHENTICITY_SOCIAL_PROOF: bool = Field(
        default=True,
        description="Enable social proof (bots more likely to engage with popular content)"
    )
    AUTHENTICITY_CONVERSATION_CALLBACKS: bool = Field(
        default=True,
        description="Enable bots to reference past conversations naturally"
    )
    AUTHENTICITY_GRADUAL_ENGAGEMENT: bool = Field(
        default=True,
        description="Enable gradual engagement curves (reactions spread over time, not instant)"
    )
    AUTHENTICITY_REACTION_VARIETY: bool = Field(
        default=True,
        description="Enable varied reactions (love, haha, wow) instead of just likes"
    )

    # -------------------------------------------------------------------------
    # TIMING
    # -------------------------------------------------------------------------

    MIN_TYPING_DELAY_MS: int = Field(default=500)
    MAX_TYPING_DELAY_MS: int = Field(default=3000)
    MIN_RESPONSE_DELAY_MS: int = Field(default=1000)
    MAX_RESPONSE_DELAY_MS: int = Field(default=30000)

    # -------------------------------------------------------------------------
    # MEMORY
    # -------------------------------------------------------------------------

    VECTOR_DIMENSION: int = Field(default=768)
    MAX_MEMORY_ITEMS: int = Field(default=1000)
    MEMORY_RETRIEVAL_LIMIT: int = Field(default=10)

    # -------------------------------------------------------------------------
    # API
    # -------------------------------------------------------------------------

    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)
    API_WORKERS: int = Field(default=4)
    API_DEBUG: bool = Field(default=False)

    # -------------------------------------------------------------------------
    # SECURITY
    # -------------------------------------------------------------------------

    CORS_ORIGINS: str = Field(
        default="*",
        description="Comma-separated list of allowed origins, or * for all"
    )

    JWT_SECRET_KEY: str = Field(
        default="your-super-secret-key-change-in-production",
        description="Secret key for JWT token signing (CHANGE IN PRODUCTION!)"
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="Algorithm used for JWT signing"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        description="Access token expiration time in minutes"
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7,
        description="Refresh token expiration time in days"
    )

    # -------------------------------------------------------------------------
    # MONITORING
    # -------------------------------------------------------------------------

    METRICS_ENABLED: bool = Field(default=True)
    METRICS_PORT: int = Field(default=9090)
    HEALTH_CHECK_TIMEOUT: float = Field(
        default=5.0,
        description="Timeout in seconds for health check probes"
    )
    LOG_LEVEL: str = Field(default="INFO")

    # -------------------------------------------------------------------------
    # GITHUB
    # -------------------------------------------------------------------------

    GITHUB_TOKEN: Optional[str] = Field(
        default=None,
        description="GitHub Personal Access Token for bot development capabilities"
    )
    GITHUB_BOT_REPO_PREFIX: str = Field(
        default="bot-evolution",
        description="Prefix for repositories created by bots"
    )

    # -------------------------------------------------------------------------
    # PUSH NOTIFICATIONS
    # -------------------------------------------------------------------------

    VAPID_PUBLIC_KEY: Optional[str] = Field(
        default=None,
        description="VAPID public key for Web Push notifications"
    )
    VAPID_PRIVATE_KEY: Optional[str] = Field(
        default=None,
        description="VAPID private key for Web Push notifications"
    )
    VAPID_CLAIMS_EMAIL: str = Field(
        default="mailto:admin@example.com",
        description="Contact email for VAPID claims"
    )

    # Firebase Cloud Messaging (FCM)
    FCM_CREDENTIALS_PATH: Optional[str] = Field(
        default=None,
        description="Path to Firebase Admin SDK service account credentials JSON file"
    )
    FCM_PROJECT_ID: Optional[str] = Field(
        default=None,
        description="Firebase project ID"
    )

    # -------------------------------------------------------------------------
    # AI CAPABILITIES (Optional external APIs)
    # -------------------------------------------------------------------------

    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="OpenAI API key for DALL-E and other OpenAI services (optional)"
    )
    IMAGE_GENERATION_ENABLED: bool = Field(
        default=False,
        description="Enable AI image generation for posts"
    )
    IMAGE_GENERATION_PROVIDER: str = Field(
        default="openai",
        description="Image generation provider: openai, stability, together, replicate, local"
    )
    IMAGE_GENERATION_MODEL: Optional[str] = Field(
        default=None,
        description="Specific model to use (e.g., 'dall-e-3', 'flux-schnell', 'stable-diffusion-xl')"
    )
    IMAGE_GENERATION_API_KEY: Optional[str] = Field(
        default=None,
        description="API key for image generation provider (falls back to OPENAI_API_KEY for OpenAI)"
    )
    IMAGE_GENERATION_PROBABILITY: float = Field(
        default=0.1,
        description="Probability (0-1) that a bot will generate an image with their post"
    )

    # -------------------------------------------------------------------------
    # TEXT-TO-SPEECH (default: Edge TTS - free, no API key required)
    # -------------------------------------------------------------------------

    TTS_ENABLED: bool = Field(
        default=False,
        description="Enable text-to-speech for bot responses"
    )
    TTS_PROVIDER: str = Field(
        default="edge",
        description="TTS provider: edge (free), openai, elevenlabs"
    )
    TTS_API_KEY: Optional[str] = Field(
        default=None,
        description="API key for paid TTS providers (OpenAI, ElevenLabs)"
    )

    # -------------------------------------------------------------------------
    # WEB SEARCH (default: DuckDuckGo - free, no API key required)
    # -------------------------------------------------------------------------

    WEB_SEARCH_ENABLED: bool = Field(
        default=True,
        description="Enable web search capability for bots"
    )
    WEB_SEARCH_PROVIDER: str = Field(
        default="duckduckgo",
        description="Search provider: duckduckgo (free), tavily, serper, brave, bing"
    )
    WEB_SEARCH_API_KEY: Optional[str] = Field(
        default=None,
        description="API key for paid search providers (Tavily, Serper, etc.)"
    )

    # -------------------------------------------------------------------------
    # EXTERNAL CHANNELS (Telegram, Discord) - disabled by default
    # -------------------------------------------------------------------------

    TELEGRAM_BOT_TOKEN: Optional[str] = Field(
        default=None,
        description="Telegram Bot API token for external messaging"
    )
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = Field(
        default=None,
        description="Secret token for Telegram webhook verification"
    )
    DISCORD_BOT_TOKEN: Optional[str] = Field(
        default=None,
        description="Discord bot token for full bot features"
    )
    DISCORD_WEBHOOK_URL: Optional[str] = Field(
        default=None,
        description="Discord webhook URL for simple outgoing messages"
    )
    EXTERNAL_CHANNELS_ENABLED: bool = Field(
        default=True,
        description="Enable external channel integrations (Telegram, Discord) - requires tokens to be set"
    )

    # -------------------------------------------------------------------------
    # OBJECT STORAGE - Configurable provider (default: local filesystem)
    # Supports: local, minio, seaweedfs, garage, s3
    # -------------------------------------------------------------------------

    # Storage provider configuration
    STORAGE_PROVIDER: str = Field(
        default="local",
        description="Object storage provider: local, minio, seaweedfs, garage, s3"
    )
    STORAGE_ENDPOINT: Optional[str] = Field(
        default=None,
        description="Endpoint URL for S3-compatible services (e.g., http://localhost:9000 for MinIO)"
    )
    STORAGE_ACCESS_KEY: Optional[str] = Field(
        default=None,
        description="Access key for object storage (not needed for local)"
    )
    STORAGE_SECRET_KEY: Optional[str] = Field(
        default=None,
        description="Secret key for object storage (not needed for local)"
    )
    STORAGE_BUCKET: str = Field(
        default="hive-media",
        description="Bucket name for object storage"
    )
    STORAGE_REGION: str = Field(
        default="us-east-1",
        description="Region for AWS S3 (ignored for other providers)"
    )
    STORAGE_PUBLIC_URL: Optional[str] = Field(
        default=None,
        description="Public URL base for accessing stored files (e.g., https://cdn.example.com)"
    )
    STORAGE_USE_SSL: bool = Field(
        default=True,
        description="Use SSL/HTTPS for object storage connections"
    )

    # Local filesystem storage (used when STORAGE_PROVIDER=local)
    MEDIA_STORAGE_PATH: str = Field(
        default="./media",
        description="Base path for local filesystem storage"
    )

    # File size and type limits
    MAX_IMAGE_SIZE_MB: float = Field(
        default=10.0,
        description="Maximum allowed image file size in MB"
    )
    MAX_VIDEO_SIZE_MB: float = Field(
        default=100.0,
        description="Maximum allowed video file size in MB"
    )
    ALLOWED_IMAGE_TYPES: list = Field(
        default=[
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
        ],
        description="List of allowed image MIME types"
    )
    ALLOWED_VIDEO_TYPES: list = Field(
        default=[
            "video/mp4",
            "video/webm",
            "video/quicktime",
        ],
        description="List of allowed video MIME types"
    )

    # -------------------------------------------------------------------------
    # ENVIRONMENT
    # -------------------------------------------------------------------------

    ENVIRONMENT: str = Field(default="development")

    class Config:
        env_file = ".env"
        env_prefix = "AIC_"
        extra = "ignore"

    # -------------------------------------------------------------------------
    # COMPUTED PROPERTIES
    # -------------------------------------------------------------------------

    @computed_field
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins as a list."""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @computed_field
    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.ENVIRONMENT.lower() == "production"

    @computed_field
    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.ENVIRONMENT.lower() == "development"

    @computed_field
    @property
    def ollama_instances_list(self) -> List[str]:
        """Parse Ollama instances as a list."""
        return [i.strip() for i in self.OLLAMA_INSTANCES.split(",") if i.strip()]

    # -------------------------------------------------------------------------
    # HOT-RELOAD SUPPORT
    # -------------------------------------------------------------------------

    def enable_hot_reload(
        self,
        config_path: Optional[Path] = None,
        callback: Optional[Callable] = None
    ) -> bool:
        """
        Enable hot-reload for configuration changes.

        Args:
            config_path: Path to config file to watch
            callback: Optional callback for change events

        Returns:
            True if hot-reload enabled successfully
        """
        try:
            from mind.config.config_watcher import (
                get_config_watcher,
                ConfigChangeEvent,
                ReloadSafety,
            )
        except ImportError:
            logger.warning("Config watcher not available. Hot-reload disabled.")
            return False

        if config_path is None:
            # Try common config file locations
            for candidate in [
                Path.cwd() / "config.yaml",
                Path.cwd() / "config.yml",
                Path.cwd() / "config.json",
            ]:
                if candidate.exists():
                    config_path = candidate
                    break

        if config_path is None or not config_path.exists():
            logger.warning("No config file found for hot-reload")
            return False

        def on_config_change(event: ConfigChangeEvent):
            """Handle config changes."""
            logger.info(f"Configuration changed: {event.changed_fields}")

            if event.safety_level == ReloadSafety.SAFE:
                self._apply_changes(event)
            elif event.safety_level == ReloadSafety.RESTART_RECOMMENDED:
                logger.warning(
                    "Some config changes require restart for full effect: "
                    f"{event.changed_fields}"
                )
                self._apply_changes(event)
            else:
                logger.warning(
                    "Config changes require restart: "
                    f"{event.changed_fields}"
                )

            if callback:
                callback(event)

            for cb in self._change_callbacks:
                try:
                    cb(event)
                except Exception as e:
                    logger.error(f"Error in config change callback: {e}")

        watcher = get_config_watcher()
        return watcher.watch(config_path, on_config_change)

    def on_change(self, callback: Callable):
        """Register a callback for configuration changes."""
        self._change_callbacks.append(callback)

    def _apply_changes(self, event):
        """Apply safe configuration changes."""
        path_to_attr = {
            "cache.default_ttl": "CACHE_DEFAULT_TTL",
            "cache.llm_response_ttl": "CACHE_LLM_RESPONSE_TTL",
            "cache.bot_profile_ttl": "CACHE_BOT_PROFILE_TTL",
            "llm.max_tokens": "LLM_MAX_TOKENS",
            "llm.temperature": "LLM_TEMPERATURE",
            "engine.max_active_bots": "MAX_ACTIVE_BOTS",
            "engine.min_typing_delay_ms": "MIN_TYPING_DELAY_MS",
            "engine.max_typing_delay_ms": "MAX_TYPING_DELAY_MS",
            "engine.min_response_delay_ms": "MIN_RESPONSE_DELAY_MS",
            "engine.max_response_delay_ms": "MAX_RESPONSE_DELAY_MS",
            "engine.activity_check_interval": "BOT_ACTIVITY_CHECK_INTERVAL",
            "memory.retrieval_limit": "MEMORY_RETRIEVAL_LIMIT",
            "monitoring.log_level": "LOG_LEVEL",
        }

        for field_path in event.changed_fields:
            if field_path in path_to_attr:
                attr_name = path_to_attr[field_path]
                new_value = event.new_values.get(field_path)
                if new_value is not None and hasattr(self, attr_name):
                    try:
                        object.__setattr__(self, attr_name, new_value)
                        logger.debug(f"Updated {attr_name} = {new_value}")
                    except Exception as e:
                        logger.error(f"Failed to update {attr_name}: {e}")

    # -------------------------------------------------------------------------
    # VALIDATION
    # -------------------------------------------------------------------------

    def validate_config(self) -> bool:
        """
        Validate the current configuration.

        Returns:
            True if configuration is valid
        """
        try:
            from mind.config.config_loader import ConfigLoader

            loader = ConfigLoader()
            config_dict = {
                "database": {
                    "url": self.DATABASE_URL,
                    "pool_size": self.DATABASE_POOL_SIZE,
                    "max_overflow": self.DATABASE_MAX_OVERFLOW,
                },
                "redis": {
                    "url": self.REDIS_URL,
                    "max_connections": self.REDIS_MAX_CONNECTIONS,
                    "enabled": self.REDIS_ENABLED,
                },
                "llm": {
                    "provider": self.LLM_PROVIDER.value,
                    "ollama_base_url": self.OLLAMA_BASE_URL,
                    "ollama_model": self.OLLAMA_MODEL,
                    "ollama_embedding_model": self.OLLAMA_EMBEDDING_MODEL,
                    "max_concurrent_requests": self.LLM_MAX_CONCURRENT_REQUESTS,
                    "request_timeout": self.LLM_REQUEST_TIMEOUT,
                    "max_tokens": self.LLM_MAX_TOKENS,
                    "temperature": self.LLM_TEMPERATURE,
                },
                "security": {
                    "jwt_secret_key": self.JWT_SECRET_KEY,
                    "jwt_algorithm": self.JWT_ALGORITHM,
                    "cors_origins": self.cors_origins_list,
                },
                "engine": {
                    "max_active_bots": self.MAX_ACTIVE_BOTS,
                    "max_bots_per_community": self.MAX_BOTS_PER_COMMUNITY,
                    "min_bots_per_community": self.MIN_BOTS_PER_COMMUNITY,
                },
                "api": {
                    "host": self.API_HOST,
                    "port": self.API_PORT,
                    "workers": self.API_WORKERS,
                },
                "environment": self.ENVIRONMENT,
            }

            result = loader.validate_config(config_dict)

            if not result.is_valid:
                for error in result.errors:
                    logger.error(f"Config validation error: {error.field}: {error.message}")

            for warning in result.warnings:
                logger.warning(f"Config validation warning: {warning}")

            return result.is_valid

        except ImportError:
            # Config loader not available, skip validation
            logger.debug("Config loader not available, skipping validation")
            return True


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

settings = Settings()


# =============================================================================
# APP CONFIG ACCESS
# =============================================================================

@lru_cache(maxsize=1)
def get_app_config():
    """
    Get the full AppConfig instance.

    This provides access to the structured configuration with
    all validation and nested config objects.
    """
    try:
        from mind.config.config_loader import get_config_loader
        return get_config_loader().load()
    except ImportError:
        logger.warning("Config loader not available")
        return None


def reload_app_config():
    """Reload the application configuration."""
    get_app_config.cache_clear()
    try:
        from mind.config.config_loader import get_config_loader
        return get_config_loader().reload()
    except ImportError:
        logger.warning("Config loader not available")
        return None


# =============================================================================
# STARTUP VALIDATION
# =============================================================================

def validate_config_on_startup():
    """
    Validate configuration at application startup.

    Call this early in your application startup to catch
    configuration errors before they cause runtime issues.
    """
    logger.info("Validating configuration...")

    if not settings.validate_config():
        raise RuntimeError("Configuration validation failed. Check logs for details.")

    # Additional startup checks
    if settings.is_production:
        if "change-in-production" in settings.JWT_SECRET_KEY:
            raise RuntimeError(
                "JWT secret key must be changed for production environment"
            )

        if hasattr(settings, 'API_DEBUG') and settings.API_DEBUG:
            logger.warning("API debug mode is enabled in production")

    logger.info(f"Configuration validated successfully (env: {settings.ENVIRONMENT})")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "settings",
    "Settings",
    "LLMProvider",
    "get_app_config",
    "reload_app_config",
    "validate_config_on_startup",
    # Re-export constants for convenience
    "TIMING",
    "CONTENT",
    "POSTING",
    "EMOTION",
    "MEMORY",
    "SCHEDULER",
    "API",
    "INFERENCE",
]
