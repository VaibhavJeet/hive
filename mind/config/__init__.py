"""
Configuration module for AI Community Companions.

This module provides centralized configuration management with:
- Strong typing and validation via Pydantic
- Support for environment variables, .env, YAML, and JSON
- Hot-reload capability for safe configuration changes
- Constants for all magic numbers

Usage:
    # Simple access (backward compatible)
    from mind.config import settings
    print(settings.DATABASE_URL)

    # Full config with validation
    from mind.config import get_app_config
    config = get_app_config()
    print(config.database.pool_size)

    # Constants
    from mind.config import TIMING, POSTING
    print(TIMING.THOUGHT_BASE_DELAY)

    # Hot-reload
    from mind.config import settings
    settings.enable_hot_reload(Path("config.yaml"))
"""

from mind.config.settings import (
    settings,
    Settings,
    LLMProvider,
    get_app_config,
    reload_app_config,
    validate_config_on_startup,
)

from mind.config.constants import (
    POSTING,
    TIMING,
    CONTENT,
    EMOTION,
    RELATIONSHIP,
    MEMORY,
    SCHEDULER,
    COMMUNITY,
    API,
    INFERENCE,
)

__all__ = [
    # Main settings
    "settings",
    "Settings",
    "LLMProvider",
    "get_app_config",
    "reload_app_config",
    "validate_config_on_startup",
    # Constants
    "POSTING",
    "TIMING",
    "CONTENT",
    "EMOTION",
    "RELATIONSHIP",
    "MEMORY",
    "SCHEDULER",
    "COMMUNITY",
    "API",
    "INFERENCE",
]
