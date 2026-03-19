"""
Configuration Loader - Load config from multiple sources with validation.

Supports loading from:
- Environment variables
- .env files
- YAML files
- JSON files

Environment variables take precedence over file-based configuration.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Union, List, Type, TypeVar
from functools import lru_cache

from pydantic import ValidationError as PydanticValidationError

from mind.config.config_schema import (
    AppConfig,
    DatabaseConfig,
    RedisConfig,
    CacheConfig,
    LLMConfig,
    SecurityConfig,
    EngineConfig,
    MemoryConfig,
    APIConfig,
    MonitoringConfig,
    GithubConfig,
    ValidationResult,
    ValidationError,
    LLMProvider,
    LogLevel,
    Environment,
)


logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# ENV VARIABLE PREFIX AND MAPPING
# =============================================================================

ENV_PREFIX = "AIC_"

# Mapping from env var names to config paths
ENV_MAPPING = {
    # Database
    "DATABASE_URL": "database.url",
    "DATABASE_POOL_SIZE": "database.pool_size",
    "DATABASE_MAX_OVERFLOW": "database.max_overflow",
    "DATABASE_POOL_TIMEOUT": "database.pool_timeout",
    "DATABASE_ECHO": "database.echo",

    # Redis
    "REDIS_URL": "redis.url",
    "REDIS_MAX_CONNECTIONS": "redis.max_connections",
    "REDIS_ENABLED": "redis.enabled",

    # Cache
    "CACHE_DEFAULT_TTL": "cache.default_ttl",
    "CACHE_LLM_RESPONSE_TTL": "cache.llm_response_ttl",
    "CACHE_BOT_PROFILE_TTL": "cache.bot_profile_ttl",

    # LLM
    "LLM_PROVIDER": "llm.provider",
    "OLLAMA_BASE_URL": "llm.ollama_base_url",
    "OLLAMA_MODEL": "llm.ollama_model",
    "OLLAMA_EMBEDDING_MODEL": "llm.ollama_embedding_model",
    "LLM_MAX_CONCURRENT_REQUESTS": "llm.max_concurrent_requests",
    "LLM_REQUEST_TIMEOUT": "llm.request_timeout",
    "LLM_MAX_TOKENS": "llm.max_tokens",
    "LLM_TEMPERATURE": "llm.temperature",
    "INFERENCE_BATCH_SIZE": "llm.batch_size",

    # Security
    "JWT_SECRET_KEY": "security.jwt_secret_key",
    "JWT_ALGORITHM": "security.jwt_algorithm",
    "ACCESS_TOKEN_EXPIRE_MINUTES": "security.access_token_expire_minutes",
    "REFRESH_TOKEN_EXPIRE_DAYS": "security.refresh_token_expire_days",
    "CORS_ORIGINS": "security.cors_origins",

    # Engine
    "MAX_ACTIVE_BOTS": "engine.max_active_bots",
    "MAX_BOTS_PER_COMMUNITY": "engine.max_bots_per_community",
    "MIN_BOTS_PER_COMMUNITY": "engine.min_bots_per_community",
    "BOT_ACTIVITY_CHECK_INTERVAL": "engine.activity_check_interval",
    "MIN_TYPING_DELAY_MS": "engine.min_typing_delay_ms",
    "MAX_TYPING_DELAY_MS": "engine.max_typing_delay_ms",
    "MIN_RESPONSE_DELAY_MS": "engine.min_response_delay_ms",
    "MAX_RESPONSE_DELAY_MS": "engine.max_response_delay_ms",

    # Memory
    "VECTOR_DIMENSION": "memory.vector_dimension",
    "MAX_MEMORY_ITEMS": "memory.max_memory_items",
    "MEMORY_RETRIEVAL_LIMIT": "memory.retrieval_limit",

    # API
    "API_HOST": "api.host",
    "API_PORT": "api.port",
    "API_WORKERS": "api.workers",
    "API_DEBUG": "api.debug",

    # Monitoring
    "METRICS_ENABLED": "monitoring.metrics_enabled",
    "METRICS_PORT": "monitoring.metrics_port",
    "HEALTH_CHECK_TIMEOUT": "monitoring.health_check_timeout",
    "LOG_LEVEL": "monitoring.log_level",

    # GitHub
    "GITHUB_TOKEN": "github.token",
    "GITHUB_BOT_REPO_PREFIX": "github.bot_repo_prefix",

    # App metadata
    "APP_NAME": "app_name",
    "APP_VERSION": "version",
    "ENVIRONMENT": "environment",
}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def _parse_value(value: str, target_type: Type[T]) -> T:
    """Parse a string value to the target type."""
    if target_type == bool:
        return value.lower() in ("true", "1", "yes", "on")
    elif target_type == int:
        return int(value)
    elif target_type == float:
        return float(value)
    elif target_type == list or target_type == List[str]:
        # Handle comma-separated lists
        return [v.strip() for v in value.split(",") if v.strip()]
    elif hasattr(target_type, "__members__"):
        # It's an Enum
        return target_type(value)
    return value


def _set_nested_value(d: Dict[str, Any], path: str, value: Any):
    """Set a value in a nested dictionary using dot notation."""
    keys = path.split(".")
    current = d
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value


def _get_nested_value(d: Dict[str, Any], path: str, default: Any = None) -> Any:
    """Get a value from a nested dictionary using dot notation."""
    keys = path.split(".")
    current = d
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        elif value is not None:
            result[key] = value
    return result


# =============================================================================
# CONFIG LOADER CLASS
# =============================================================================

class ConfigLoader:
    """
    Loads configuration from multiple sources.

    Priority (highest to lowest):
    1. Environment variables
    2. Explicit config dict
    3. Config file (.yaml, .json, .env)
    4. Defaults
    """

    def __init__(
        self,
        env_prefix: str = ENV_PREFIX,
        config_path: Optional[Path] = None,
    ):
        self.env_prefix = env_prefix
        self.config_path = config_path
        self._config: Optional[AppConfig] = None
        self._raw_config: Dict[str, Any] = {}

    def load_from_env(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        config = {}

        for env_var, config_path in ENV_MAPPING.items():
            full_var = f"{self.env_prefix}{env_var}"
            value = os.environ.get(full_var)

            if value is not None:
                _set_nested_value(config, config_path, value)
                logger.debug(f"Loaded {full_var} -> {config_path}")

        return config

    def load_from_dotenv(self, path: Optional[Path] = None) -> Dict[str, Any]:
        """Load configuration from a .env file."""
        if path is None:
            path = Path.cwd() / ".env"

        if not path.exists():
            logger.debug(f".env file not found at {path}")
            return {}

        config = {}
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    if "=" not in line:
                        continue

                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")

                    # Remove env prefix if present
                    if key.startswith(self.env_prefix):
                        key = key[len(self.env_prefix):]

                    if key in ENV_MAPPING:
                        _set_nested_value(config, ENV_MAPPING[key], value)
                        logger.debug(f"Loaded {key} from .env")

        except Exception as e:
            logger.warning(f"Error reading .env file: {e}")

        return config

    def load_from_yaml(self, path: Path) -> Dict[str, Any]:
        """Load configuration from a YAML file."""
        try:
            import yaml
        except ImportError:
            logger.warning("PyYAML not installed. Cannot load YAML config.")
            return {}

        if not path.exists():
            logger.debug(f"YAML file not found at {path}")
            return {}

        try:
            with open(path) as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded config from {path}")
                return config or {}
        except Exception as e:
            logger.warning(f"Error reading YAML file: {e}")
            return {}

    def load_from_json(self, path: Path) -> Dict[str, Any]:
        """Load configuration from a JSON file."""
        if not path.exists():
            logger.debug(f"JSON file not found at {path}")
            return {}

        try:
            with open(path) as f:
                config = json.load(f)
                logger.info(f"Loaded config from {path}")
                return config or {}
        except Exception as e:
            logger.warning(f"Error reading JSON file: {e}")
            return {}

    def load_from_file(self, path: Union[str, Path]) -> Dict[str, Any]:
        """Load configuration from a file (auto-detects format)."""
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        suffix = path.suffix.lower()

        if suffix in (".yaml", ".yml"):
            return self.load_from_yaml(path)
        elif suffix == ".json":
            return self.load_from_json(path)
        elif suffix == ".env" or path.name.startswith(".env"):
            return self.load_from_dotenv(path)
        else:
            raise ValueError(f"Unsupported config file format: {suffix}")

    def merge_configs(
        self,
        base: Dict[str, Any],
        override: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge two config dictionaries (override takes precedence)."""
        return _deep_merge(base, override)

    def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate a configuration dictionary."""
        result = ValidationResult(is_valid=True)

        try:
            # Try to create the config model
            AppConfig(**config)
        except PydanticValidationError as e:
            for error in e.errors():
                field = ".".join(str(loc) for loc in error["loc"])
                result.add_error(
                    field=field,
                    message=error["msg"],
                    value=str(error.get("input"))
                )

        # Additional semantic validation
        self._validate_semantic(config, result)

        return result

    def _validate_semantic(self, config: Dict[str, Any], result: ValidationResult):
        """Perform semantic validation beyond Pydantic."""
        # Check database URL has required driver
        db_url = _get_nested_value(config, "database.url", "")
        if db_url and "asyncpg" not in db_url:
            result.add_warning("Database URL should use asyncpg driver for async support")

        # Check for production environment issues
        env = _get_nested_value(config, "environment")
        if env == "production":
            jwt_secret = _get_nested_value(config, "security.jwt_secret_key", "")
            if "change-in-production" in jwt_secret:
                result.add_error(
                    field="security.jwt_secret_key",
                    message="JWT secret must be changed for production"
                )

            debug = _get_nested_value(config, "api.debug", False)
            if debug:
                result.add_warning("Debug mode should be disabled in production")

    def load(
        self,
        config_path: Optional[Union[str, Path]] = None,
        extra_config: Optional[Dict[str, Any]] = None,
    ) -> AppConfig:
        """
        Load and validate configuration from all sources.

        Args:
            config_path: Optional path to config file
            extra_config: Optional extra configuration to merge

        Returns:
            Validated AppConfig instance
        """
        # Start with defaults (empty dict, Pydantic will use defaults)
        config: Dict[str, Any] = {}

        # Load from .env file if exists
        dotenv_config = self.load_from_dotenv()
        config = self.merge_configs(config, dotenv_config)

        # Load from config file if provided
        if config_path:
            file_config = self.load_from_file(config_path)
            config = self.merge_configs(config, file_config)
        elif self.config_path:
            file_config = self.load_from_file(self.config_path)
            config = self.merge_configs(config, file_config)

        # Load from environment variables (highest priority)
        env_config = self.load_from_env()
        config = self.merge_configs(config, env_config)

        # Merge extra config if provided
        if extra_config:
            config = self.merge_configs(config, extra_config)

        # Convert string values to appropriate types
        config = self._convert_types(config)

        # Store raw config
        self._raw_config = config

        # Validate
        validation = self.validate_config(config)
        if not validation.is_valid:
            errors_str = "\n".join(
                f"  - {e.field}: {e.message}" for e in validation.errors
            )
            raise ValueError(f"Configuration validation failed:\n{errors_str}")

        for warning in validation.warnings:
            logger.warning(f"Config warning: {warning}")

        # Create config instance
        self._config = AppConfig(**config)

        return self._config

    def _convert_types(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Convert string values to appropriate types based on expected schema."""
        # Type hints for known fields
        type_map = {
            "database.pool_size": int,
            "database.max_overflow": int,
            "database.pool_timeout": int,
            "database.pool_recycle": int,
            "database.echo": bool,
            "redis.max_connections": int,
            "redis.enabled": bool,
            "redis.socket_timeout": float,
            "redis.retry_on_timeout": bool,
            "cache.default_ttl": int,
            "cache.llm_response_ttl": int,
            "cache.bot_profile_ttl": int,
            "cache.community_ttl": int,
            "llm.max_concurrent_requests": int,
            "llm.request_timeout": int,
            "llm.max_tokens": int,
            "llm.temperature": float,
            "llm.batch_size": int,
            "security.access_token_expire_minutes": int,
            "security.refresh_token_expire_days": int,
            "security.cors_origins": list,
            "engine.max_active_bots": int,
            "engine.max_bots_per_community": int,
            "engine.min_bots_per_community": int,
            "engine.activity_check_interval": int,
            "engine.min_typing_delay_ms": int,
            "engine.max_typing_delay_ms": int,
            "engine.min_response_delay_ms": int,
            "engine.max_response_delay_ms": int,
            "memory.vector_dimension": int,
            "memory.max_memory_items": int,
            "memory.retrieval_limit": int,
            "memory.consolidation_threshold": float,
            "api.port": int,
            "api.workers": int,
            "api.debug": bool,
            "api.docs_enabled": bool,
            "monitoring.metrics_enabled": bool,
            "monitoring.metrics_port": int,
            "monitoring.health_check_timeout": float,
            "github.enabled": bool,
        }

        for path, target_type in type_map.items():
            value = _get_nested_value(config, path)
            if value is not None and isinstance(value, str):
                try:
                    converted = _parse_value(value, target_type)
                    _set_nested_value(config, path, converted)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not convert {path}={value}: {e}")

        return config

    def get_config(self) -> AppConfig:
        """Get the loaded configuration (loads if not already loaded)."""
        if self._config is None:
            self.load()
        return self._config

    def reload(self) -> AppConfig:
        """Reload configuration from all sources."""
        self._config = None
        return self.load()

    def get_raw_config(self) -> Dict[str, Any]:
        """Get the raw configuration dictionary."""
        return self._raw_config.copy()


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_config_loader: Optional[ConfigLoader] = None


def get_config_loader() -> ConfigLoader:
    """Get the global config loader instance."""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Get the application configuration (cached)."""
    return get_config_loader().load()


def reload_config() -> AppConfig:
    """Reload the configuration (clears cache)."""
    get_config.cache_clear()
    return get_config_loader().reload()
