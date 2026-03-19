"""
Configuration Schema - Pydantic models for all config sections.

Provides strong typing, validation, and sensible defaults for all configuration.
"""

from typing import Optional, List, Set
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator
import re


# =============================================================================
# ENUMS
# =============================================================================

class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OLLAMA = "ollama"
    LLAMACPP = "llamacpp"
    OPENAI = "openai"


class LogLevel(str, Enum):
    """Log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Environment(str, Enum):
    """Deployment environments."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


# =============================================================================
# DATABASE CONFIG
# =============================================================================

class DatabaseConfig(BaseModel):
    """Database configuration settings."""

    url: str = Field(
        default="postgresql+asyncpg://localhost:5432/mind",
        description="PostgreSQL connection string (with asyncpg driver)"
    )
    pool_size: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of connections in the pool"
    )
    max_overflow: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Maximum overflow connections beyond pool_size"
    )
    pool_timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Timeout for getting a connection from pool (seconds)"
    )
    pool_recycle: int = Field(
        default=1800,
        ge=300,
        le=7200,
        description="Recycle connections after this many seconds"
    )
    echo: bool = Field(
        default=False,
        description="Log all SQL statements (debug only)"
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Ensure URL has proper format."""
        if not v.startswith(("postgresql", "postgres")):
            raise ValueError("Database URL must be a PostgreSQL connection string")
        return v


# =============================================================================
# REDIS CONFIG
# =============================================================================

class RedisConfig(BaseModel):
    """Redis configuration settings."""

    url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection string"
    )
    max_connections: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of Redis connections"
    )
    enabled: bool = Field(
        default=True,
        description="Enable Redis (gracefully degrades if unavailable)"
    )
    socket_timeout: float = Field(
        default=5.0,
        ge=1.0,
        le=30.0,
        description="Socket timeout in seconds"
    )
    retry_on_timeout: bool = Field(
        default=True,
        description="Retry operations on timeout"
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Ensure URL has proper format."""
        if not v.startswith(("redis://", "rediss://")):
            raise ValueError("Redis URL must start with redis:// or rediss://")
        return v


# =============================================================================
# CACHE CONFIG
# =============================================================================

class CacheConfig(BaseModel):
    """Cache TTL configuration."""

    default_ttl: int = Field(
        default=300,
        ge=60,
        le=86400,
        description="Default cache TTL in seconds (5 minutes)"
    )
    llm_response_ttl: int = Field(
        default=3600,
        ge=300,
        le=86400,
        description="LLM response cache TTL in seconds (1 hour)"
    )
    bot_profile_ttl: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Bot profile cache TTL in seconds (5 minutes)"
    )
    community_ttl: int = Field(
        default=600,
        ge=60,
        le=3600,
        description="Community data cache TTL in seconds (10 minutes)"
    )


# =============================================================================
# LLM CONFIG
# =============================================================================

class LLMConfig(BaseModel):
    """LLM/Inference configuration settings."""

    provider: LLMProvider = Field(
        default=LLMProvider.OLLAMA,
        description="LLM provider to use"
    )

    # Ollama settings
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama server URL"
    )
    ollama_model: str = Field(
        default="phi4-mini",
        description="Ollama model for text generation"
    )
    ollama_embedding_model: str = Field(
        default="nomic-embed-text",
        description="Ollama model for embeddings"
    )

    # Inference settings
    max_concurrent_requests: int = Field(
        default=8,
        ge=1,
        le=32,
        description="Maximum concurrent LLM requests"
    )
    request_timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Request timeout in seconds"
    )
    max_tokens: int = Field(
        default=512,
        ge=64,
        le=4096,
        description="Maximum tokens per generation"
    )
    temperature: float = Field(
        default=0.8,
        ge=0.0,
        le=2.0,
        description="Generation temperature"
    )
    batch_size: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Batch size for inference grouping"
    )

    @field_validator("ollama_base_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Ensure URL has proper format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Ollama URL must be a valid HTTP(S) URL")
        return v.rstrip("/")


# =============================================================================
# SECURITY CONFIG
# =============================================================================

class SecurityConfig(BaseModel):
    """Security and authentication configuration."""

    jwt_secret_key: str = Field(
        default="your-super-secret-key-change-in-production",
        min_length=32,
        description="Secret key for JWT token signing"
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="Algorithm for JWT signing"
    )
    access_token_expire_minutes: int = Field(
        default=30,
        ge=5,
        le=1440,
        description="Access token expiration in minutes"
    )
    refresh_token_expire_days: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Refresh token expiration in days"
    )
    cors_origins: List[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed CORS origins"
    )

    @field_validator("jwt_algorithm")
    @classmethod
    def validate_algorithm(cls, v: str) -> str:
        """Ensure algorithm is supported."""
        allowed = {"HS256", "HS384", "HS512", "RS256", "RS384", "RS512"}
        if v not in allowed:
            raise ValueError(f"JWT algorithm must be one of: {allowed}")
        return v

    @model_validator(mode="after")
    def warn_default_secret(self) -> "SecurityConfig":
        """Warn if using default secret key."""
        if "change-in-production" in self.jwt_secret_key:
            import warnings
            warnings.warn(
                "Using default JWT secret key. Change this in production!",
                UserWarning
            )
        return self


# =============================================================================
# ENGINE CONFIG
# =============================================================================

class EngineConfig(BaseModel):
    """Bot engine configuration."""

    max_active_bots: int = Field(
        default=12,
        ge=1,
        le=100,
        description="Maximum number of active bots in simulation"
    )
    max_bots_per_community: int = Field(
        default=150,
        ge=10,
        le=500,
        description="Maximum bots per community"
    )
    min_bots_per_community: int = Field(
        default=30,
        ge=5,
        le=100,
        description="Minimum bots per community"
    )
    activity_check_interval: int = Field(
        default=60,
        ge=10,
        le=600,
        description="Activity check interval in seconds"
    )

    # Timing configuration (human-like delays)
    min_typing_delay_ms: int = Field(
        default=500,
        ge=100,
        le=5000,
        description="Minimum typing delay in milliseconds"
    )
    max_typing_delay_ms: int = Field(
        default=3000,
        ge=1000,
        le=30000,
        description="Maximum typing delay in milliseconds"
    )
    min_response_delay_ms: int = Field(
        default=1000,
        ge=500,
        le=10000,
        description="Minimum response delay in milliseconds"
    )
    max_response_delay_ms: int = Field(
        default=30000,
        ge=5000,
        le=120000,
        description="Maximum response delay in milliseconds"
    )

    @model_validator(mode="after")
    def validate_ranges(self) -> "EngineConfig":
        """Ensure min/max ranges are valid."""
        if self.min_bots_per_community > self.max_bots_per_community:
            raise ValueError("min_bots_per_community cannot exceed max_bots_per_community")
        if self.min_typing_delay_ms > self.max_typing_delay_ms:
            raise ValueError("min_typing_delay_ms cannot exceed max_typing_delay_ms")
        if self.min_response_delay_ms > self.max_response_delay_ms:
            raise ValueError("min_response_delay_ms cannot exceed max_response_delay_ms")
        return self


# =============================================================================
# MEMORY CONFIG
# =============================================================================

class MemoryConfig(BaseModel):
    """Memory system configuration."""

    vector_dimension: int = Field(
        default=768,
        ge=128,
        le=4096,
        description="Vector embedding dimension (must match model)"
    )
    max_memory_items: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Maximum memory items per bot"
    )
    retrieval_limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Memory retrieval limit per query"
    )
    consolidation_threshold: float = Field(
        default=0.8,
        ge=0.5,
        le=0.95,
        description="Memory consolidation threshold (% of max)"
    )


# =============================================================================
# API CONFIG
# =============================================================================

class APIConfig(BaseModel):
    """API server configuration."""

    host: str = Field(
        default="0.0.0.0",
        description="API server host"
    )
    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="API server port"
    )
    workers: int = Field(
        default=4,
        ge=1,
        le=32,
        description="Number of API workers"
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    docs_enabled: bool = Field(
        default=True,
        description="Enable OpenAPI documentation"
    )

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        """Validate host format."""
        ip_pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
        if v not in ("0.0.0.0", "localhost", "127.0.0.1") and not re.match(ip_pattern, v):
            # Allow hostname format too
            hostname_pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*$"
            if not re.match(hostname_pattern, v):
                raise ValueError(f"Invalid host format: {v}")
        return v


# =============================================================================
# MONITORING CONFIG
# =============================================================================

class MonitoringConfig(BaseModel):
    """Monitoring and metrics configuration."""

    metrics_enabled: bool = Field(
        default=True,
        description="Enable Prometheus metrics"
    )
    metrics_port: int = Field(
        default=9090,
        ge=1,
        le=65535,
        description="Metrics endpoint port"
    )
    health_check_timeout: float = Field(
        default=5.0,
        ge=1.0,
        le=30.0,
        description="Health check timeout in seconds"
    )
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Logging level"
    )
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string"
    )


# =============================================================================
# GITHUB CONFIG
# =============================================================================

class GithubConfig(BaseModel):
    """GitHub integration configuration."""

    token: Optional[str] = Field(
        default=None,
        description="GitHub Personal Access Token"
    )
    bot_repo_prefix: str = Field(
        default="bot-evolution",
        description="Prefix for bot-created repositories"
    )
    enabled: bool = Field(
        default=False,
        description="Enable GitHub integration"
    )

    @model_validator(mode="after")
    def check_token_required(self) -> "GithubConfig":
        """Enable only if token is provided."""
        if self.enabled and not self.token:
            self.enabled = False
        elif self.token and not self.enabled:
            self.enabled = True
        return self


# =============================================================================
# VIDEO CONFIG
# =============================================================================

class VideoConfig(BaseModel):
    """Video processing configuration."""

    max_size_mb: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum video file size in MB"
    )
    max_duration_seconds: int = Field(
        default=300,
        ge=1,
        le=3600,
        description="Maximum video duration in seconds"
    )
    allowed_formats: List[str] = Field(
        default_factory=lambda: ["mp4", "mov", "webm"],
        description="Allowed video formats"
    )

    @field_validator("allowed_formats")
    @classmethod
    def validate_formats(cls, v: List[str]) -> List[str]:
        """Ensure formats are lowercase and valid."""
        valid_formats = {"mp4", "mov", "webm", "avi", "mkv", "m4v", "flv", "wmv"}
        normalized = [fmt.lower().strip() for fmt in v]
        invalid = set(normalized) - valid_formats
        if invalid:
            raise ValueError(f"Invalid video formats: {invalid}. Valid formats: {valid_formats}")
        return normalized


# =============================================================================
# MAIN APP CONFIG
# =============================================================================

class AppConfig(BaseModel):
    """Complete application configuration."""

    # Metadata
    app_name: str = Field(
        default="AI Community Companions",
        description="Application name"
    )
    version: str = Field(
        default="1.0.0",
        description="Application version"
    )
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Deployment environment"
    )

    # Component configs
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    engine: EngineConfig = Field(default_factory=EngineConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    github: GithubConfig = Field(default_factory=GithubConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)

    @model_validator(mode="after")
    def production_checks(self) -> "AppConfig":
        """Apply stricter validation for production."""
        if self.environment == Environment.PRODUCTION:
            # Ensure secure settings
            if "change-in-production" in self.security.jwt_secret_key:
                raise ValueError(
                    "JWT secret key must be changed for production environment"
                )
            if self.api.debug:
                raise ValueError("Debug mode must be disabled in production")
            if "*" in self.security.cors_origins:
                import warnings
                warnings.warn(
                    "CORS allows all origins in production. Consider restricting.",
                    UserWarning
                )
        return self

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == Environment.PRODUCTION

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == Environment.DEVELOPMENT


# =============================================================================
# VALIDATION RESULT
# =============================================================================

class ValidationError(BaseModel):
    """A single validation error."""
    field: str
    message: str
    value: Optional[str] = None


class ValidationResult(BaseModel):
    """Result of configuration validation."""
    is_valid: bool
    errors: List[ValidationError] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    def add_error(self, field: str, message: str, value: Optional[str] = None):
        """Add a validation error."""
        self.errors.append(ValidationError(field=field, message=message, value=value))
        self.is_valid = False

    def add_warning(self, message: str):
        """Add a validation warning."""
        self.warnings.append(message)
