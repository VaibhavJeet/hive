"""
Production Configuration Module

Provides production-specific settings, validation, and security hardening
for Sentient deployments.

Usage:
    from mind.config.production import (
        validate_production_config,
        get_production_settings,
        ProductionSettings,
    )

    # Validate before startup
    validate_production_config()

    # Get production-aware settings
    settings = get_production_settings()
"""

import logging
import os
import secrets
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any

from pydantic import Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


# =============================================================================
# PRODUCTION CONSTANTS
# =============================================================================

class ProductionDefaults:
    """Production-specific default values."""

    # Database
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 40
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 1800

    # Redis
    REDIS_MAX_CONNECTIONS: int = 20
    REDIS_SOCKET_TIMEOUT: float = 5.0

    # LLM
    LLM_MAX_CONCURRENT_REQUESTS: int = 8
    LLM_REQUEST_TIMEOUT: int = 60
    LLM_MAX_TOKENS: int = 512

    # API
    API_HOST: str = "127.0.0.1"  # Behind reverse proxy
    API_WORKERS: int = 4
    API_DEBUG: bool = False

    # Bot Engine
    MAX_ACTIVE_BOTS: int = 50
    AUTHENTICITY_DEMO_MODE: bool = False  # Realistic timing

    # Security
    MIN_JWT_SECRET_LENGTH: int = 32
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Monitoring
    METRICS_ENABLED: bool = True
    LOG_LEVEL: str = "INFO"


class SecurityLevel(str, Enum):
    """Security level classifications."""
    CRITICAL = "critical"  # Must be fixed before deployment
    HIGH = "high"          # Should be fixed
    MEDIUM = "medium"      # Recommended to fix
    LOW = "low"            # Nice to have


# =============================================================================
# VALIDATION ISSUES
# =============================================================================

@dataclass
class ConfigurationIssue:
    """Represents a configuration issue found during validation."""
    level: SecurityLevel
    category: str
    message: str
    variable: Optional[str] = None
    recommendation: Optional[str] = None


@dataclass
class ValidationReport:
    """Report from production configuration validation."""
    is_valid: bool = True
    issues: List[ConfigurationIssue] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)

    def add_issue(
        self,
        level: SecurityLevel,
        category: str,
        message: str,
        variable: Optional[str] = None,
        recommendation: Optional[str] = None
    ):
        """Add an issue to the report."""
        self.issues.append(ConfigurationIssue(
            level=level,
            category=category,
            message=message,
            variable=variable,
            recommendation=recommendation
        ))
        if level == SecurityLevel.CRITICAL:
            self.is_valid = False

    def add_warning(self, message: str):
        """Add a warning."""
        self.warnings.append(message)

    def add_info(self, message: str):
        """Add an info message."""
        self.info.append(message)

    def get_critical_issues(self) -> List[ConfigurationIssue]:
        """Get all critical issues."""
        return [i for i in self.issues if i.level == SecurityLevel.CRITICAL]

    def get_high_issues(self) -> List[ConfigurationIssue]:
        """Get all high-severity issues."""
        return [i for i in self.issues if i.level == SecurityLevel.HIGH]

    def print_report(self, include_info: bool = False):
        """Print the validation report to logger."""
        if self.is_valid:
            logger.info("Production configuration validation PASSED")
        else:
            logger.error("Production configuration validation FAILED")

        # Critical issues
        critical = self.get_critical_issues()
        if critical:
            logger.error(f"CRITICAL issues ({len(critical)}):")
            for issue in critical:
                logger.error(f"  [{issue.category}] {issue.message}")
                if issue.variable:
                    logger.error(f"    Variable: {issue.variable}")
                if issue.recommendation:
                    logger.error(f"    Fix: {issue.recommendation}")

        # High issues
        high = self.get_high_issues()
        if high:
            logger.warning(f"HIGH severity issues ({len(high)}):")
            for issue in high:
                logger.warning(f"  [{issue.category}] {issue.message}")

        # Other issues
        other = [i for i in self.issues if i.level not in (SecurityLevel.CRITICAL, SecurityLevel.HIGH)]
        if other:
            logger.info(f"Other issues ({len(other)}):")
            for issue in other:
                logger.info(f"  [{issue.level.value}] [{issue.category}] {issue.message}")

        # Warnings
        if self.warnings:
            for warning in self.warnings:
                logger.warning(f"Warning: {warning}")

        # Info
        if include_info and self.info:
            for info in self.info:
                logger.info(f"Info: {info}")


# =============================================================================
# PRODUCTION SETTINGS
# =============================================================================

class ProductionSettings(BaseSettings):
    """
    Production-specific settings with stricter defaults and validation.

    This extends the base settings with production-appropriate defaults
    and additional validation.
    """

    # Environment
    ENVIRONMENT: str = Field(
        default="production",
        description="Must be 'production' for production deployments"
    )

    # Database
    DATABASE_URL: str = Field(
        ...,  # Required
        description="PostgreSQL connection string"
    )
    DATABASE_POOL_SIZE: int = Field(
        default=ProductionDefaults.DATABASE_POOL_SIZE
    )
    DATABASE_MAX_OVERFLOW: int = Field(
        default=ProductionDefaults.DATABASE_MAX_OVERFLOW
    )

    # Redis
    REDIS_URL: str = Field(
        ...,  # Required
        description="Redis connection string"
    )
    REDIS_MAX_CONNECTIONS: int = Field(
        default=ProductionDefaults.REDIS_MAX_CONNECTIONS
    )
    REDIS_ENABLED: bool = Field(default=True)

    # Security
    JWT_SECRET_KEY: str = Field(
        ...,  # Required
        min_length=32,
        description="JWT secret key (minimum 32 characters)"
    )
    JWT_ALGORITHM: str = Field(default="HS256")
    CORS_ORIGINS: str = Field(
        ...,  # Required
        description="Comma-separated allowed origins"
    )

    # API
    API_HOST: str = Field(default=ProductionDefaults.API_HOST)
    API_PORT: int = Field(default=8000)
    API_WORKERS: int = Field(default=ProductionDefaults.API_WORKERS)
    API_DEBUG: bool = Field(default=ProductionDefaults.API_DEBUG)

    # LLM
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434")
    OLLAMA_MODEL: str = Field(default="phi4-mini")
    LLM_MAX_CONCURRENT_REQUESTS: int = Field(
        default=ProductionDefaults.LLM_MAX_CONCURRENT_REQUESTS
    )
    LLM_REQUEST_TIMEOUT: int = Field(
        default=ProductionDefaults.LLM_REQUEST_TIMEOUT
    )

    # Bot Engine
    MAX_ACTIVE_BOTS: int = Field(
        default=ProductionDefaults.MAX_ACTIVE_BOTS
    )
    AUTHENTICITY_DEMO_MODE: bool = Field(
        default=ProductionDefaults.AUTHENTICITY_DEMO_MODE
    )

    # Monitoring
    METRICS_ENABLED: bool = Field(default=ProductionDefaults.METRICS_ENABLED)
    LOG_LEVEL: str = Field(default=ProductionDefaults.LOG_LEVEL)

    class Config:
        env_prefix = "AIC_"
        env_file = ".env"
        extra = "ignore"


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_production_config(raise_on_critical: bool = True) -> ValidationReport:
    """
    Validate configuration for production deployment.

    Checks security settings, performance configuration, and common
    misconfigurations that could cause issues in production.

    Args:
        raise_on_critical: If True, raise exception on critical issues

    Returns:
        ValidationReport with all findings

    Raises:
        RuntimeError: If critical issues found and raise_on_critical=True
    """
    from mind.config.settings import settings

    report = ValidationReport()

    # ==========================================================================
    # ENVIRONMENT CHECKS
    # ==========================================================================

    env = os.getenv("AIC_ENVIRONMENT", settings.ENVIRONMENT)
    if env.lower() != "production":
        report.add_issue(
            level=SecurityLevel.HIGH,
            category="Environment",
            message=f"Environment is '{env}', expected 'production'",
            variable="AIC_ENVIRONMENT",
            recommendation="Set AIC_ENVIRONMENT=production"
        )
    else:
        report.add_info("Environment correctly set to production")

    # ==========================================================================
    # SECURITY CHECKS
    # ==========================================================================

    # JWT Secret
    jwt_secret = settings.JWT_SECRET_KEY
    if "change-in-production" in jwt_secret.lower():
        report.add_issue(
            level=SecurityLevel.CRITICAL,
            category="Security",
            message="JWT secret key contains default placeholder",
            variable="AIC_JWT_SECRET_KEY",
            recommendation="Generate with: openssl rand -hex 32"
        )
    elif len(jwt_secret) < ProductionDefaults.MIN_JWT_SECRET_LENGTH:
        report.add_issue(
            level=SecurityLevel.CRITICAL,
            category="Security",
            message=f"JWT secret key too short ({len(jwt_secret)} chars, need {ProductionDefaults.MIN_JWT_SECRET_LENGTH}+)",
            variable="AIC_JWT_SECRET_KEY",
            recommendation="Use a longer, cryptographically random key"
        )
    else:
        report.add_info("JWT secret key length acceptable")

    # CORS Origins
    cors = settings.CORS_ORIGINS
    if cors == "*":
        report.add_issue(
            level=SecurityLevel.HIGH,
            category="Security",
            message="CORS allows all origins (*)",
            variable="AIC_CORS_ORIGINS",
            recommendation="Restrict to specific domains: https://yourdomain.com"
        )

    # Debug mode
    if hasattr(settings, 'API_DEBUG') and settings.API_DEBUG:
        report.add_issue(
            level=SecurityLevel.CRITICAL,
            category="Security",
            message="Debug mode is enabled",
            variable="AIC_API_DEBUG",
            recommendation="Set AIC_API_DEBUG=false"
        )

    # ==========================================================================
    # DATABASE CHECKS
    # ==========================================================================

    db_url = settings.DATABASE_URL
    if "localhost" in db_url or "127.0.0.1" in db_url:
        report.add_warning(
            "Database URL points to localhost - ensure this is intentional"
        )

    if "postgres:postgres" in db_url:
        report.add_issue(
            level=SecurityLevel.HIGH,
            category="Database",
            message="Using default PostgreSQL credentials (postgres:postgres)",
            variable="AIC_DATABASE_URL",
            recommendation="Use strong, unique database credentials"
        )

    if "sslmode" not in db_url and "localhost" not in db_url:
        report.add_issue(
            level=SecurityLevel.MEDIUM,
            category="Database",
            message="Database connection may not use SSL",
            variable="AIC_DATABASE_URL",
            recommendation="Add ?sslmode=require to connection string"
        )

    # Pool size
    pool_size = settings.DATABASE_POOL_SIZE
    if pool_size < 10:
        report.add_issue(
            level=SecurityLevel.LOW,
            category="Performance",
            message=f"Database pool size ({pool_size}) may be too small for production",
            variable="AIC_DATABASE_POOL_SIZE",
            recommendation=f"Consider increasing to {ProductionDefaults.DATABASE_POOL_SIZE}+"
        )

    # ==========================================================================
    # REDIS CHECKS
    # ==========================================================================

    redis_url = settings.REDIS_URL
    if "localhost" in redis_url or "127.0.0.1" in redis_url:
        report.add_warning(
            "Redis URL points to localhost - ensure this is intentional"
        )

    # Check for password in Redis URL
    if "@" not in redis_url and "localhost" not in redis_url:
        report.add_issue(
            level=SecurityLevel.MEDIUM,
            category="Security",
            message="Redis connection may not be password protected",
            variable="AIC_REDIS_URL",
            recommendation="Use redis://:password@host:port/db format"
        )

    # ==========================================================================
    # BOT ENGINE CHECKS
    # ==========================================================================

    if hasattr(settings, 'AUTHENTICITY_DEMO_MODE') and settings.AUTHENTICITY_DEMO_MODE:
        report.add_issue(
            level=SecurityLevel.MEDIUM,
            category="Configuration",
            message="Demo mode is enabled (10x faster timing)",
            variable="AIC_AUTHENTICITY_DEMO_MODE",
            recommendation="Set AIC_AUTHENTICITY_DEMO_MODE=false for realistic behavior"
        )

    # ==========================================================================
    # API CHECKS
    # ==========================================================================

    api_host = settings.API_HOST
    if api_host == "0.0.0.0":
        report.add_issue(
            level=SecurityLevel.MEDIUM,
            category="Security",
            message="API binds to all interfaces (0.0.0.0)",
            variable="AIC_API_HOST",
            recommendation="Use 127.0.0.1 when behind a reverse proxy"
        )

    # ==========================================================================
    # LLM CHECKS
    # ==========================================================================

    ollama_url = settings.OLLAMA_BASE_URL
    if "localhost" in ollama_url or "127.0.0.1" in ollama_url:
        report.add_info("Ollama running locally - ensure Ollama service is running")

    # ==========================================================================
    # RESULT
    # ==========================================================================

    if raise_on_critical and not report.is_valid:
        critical_messages = [i.message for i in report.get_critical_issues()]
        raise RuntimeError(
            f"Production configuration validation failed with critical issues: "
            f"{'; '.join(critical_messages)}"
        )

    return report


def get_production_settings() -> Dict[str, Any]:
    """
    Get production-optimized settings.

    Returns a dictionary of recommended production settings that can be
    used to override defaults.
    """
    return {
        # Database
        "DATABASE_POOL_SIZE": ProductionDefaults.DATABASE_POOL_SIZE,
        "DATABASE_MAX_OVERFLOW": ProductionDefaults.DATABASE_MAX_OVERFLOW,

        # Redis
        "REDIS_MAX_CONNECTIONS": ProductionDefaults.REDIS_MAX_CONNECTIONS,

        # LLM
        "LLM_MAX_CONCURRENT_REQUESTS": ProductionDefaults.LLM_MAX_CONCURRENT_REQUESTS,
        "LLM_REQUEST_TIMEOUT": ProductionDefaults.LLM_REQUEST_TIMEOUT,

        # API
        "API_HOST": ProductionDefaults.API_HOST,
        "API_WORKERS": ProductionDefaults.API_WORKERS,
        "API_DEBUG": ProductionDefaults.API_DEBUG,

        # Bot Engine
        "MAX_ACTIVE_BOTS": ProductionDefaults.MAX_ACTIVE_BOTS,
        "AUTHENTICITY_DEMO_MODE": ProductionDefaults.AUTHENTICITY_DEMO_MODE,

        # Monitoring
        "METRICS_ENABLED": ProductionDefaults.METRICS_ENABLED,
        "LOG_LEVEL": ProductionDefaults.LOG_LEVEL,
    }


def generate_secure_jwt_secret() -> str:
    """
    Generate a cryptographically secure JWT secret key.

    Returns:
        64-character hex string (256 bits of entropy)
    """
    return secrets.token_hex(32)


def print_production_checklist():
    """Print a production deployment checklist to stdout."""
    checklist = """
================================================================================
SENTIENT PRODUCTION DEPLOYMENT CHECKLIST
================================================================================

SECURITY (Critical)
-------------------
[ ] Generate unique JWT secret: openssl rand -hex 32
[ ] Set strong database password (20+ characters)
[ ] Set Redis password
[ ] Restrict CORS origins to your domains
[ ] Enable SSL/TLS via reverse proxy (Nginx, Caddy)
[ ] Set .env file permissions: chmod 600

CONFIGURATION (Required)
------------------------
[ ] Set AIC_ENVIRONMENT=production
[ ] Set AIC_API_DEBUG=false
[ ] Set AIC_AUTHENTICITY_DEMO_MODE=false
[ ] Configure proper AIC_API_HOST (127.0.0.1 behind proxy)

INFRASTRUCTURE
--------------
[ ] PostgreSQL with pgvector extension installed
[ ] Redis configured and running
[ ] Ollama with required models pulled
[ ] Reverse proxy configured (Nginx recommended)
[ ] Firewall configured (allow 80, 443, 22 only)
[ ] SSL certificate obtained (Let's Encrypt)

MONITORING
----------
[ ] AIC_METRICS_ENABLED=true
[ ] Prometheus configured to scrape metrics
[ ] Log aggregation set up (journald, Loki, etc.)
[ ] Alerting configured for critical metrics

RELIABILITY
-----------
[ ] Database backups scheduled
[ ] Redis persistence configured (AOF recommended)
[ ] Systemd service files created
[ ] Health checks enabled

STORAGE (if using media)
------------------------
[ ] Object storage configured (MinIO, S3)
[ ] CDN configured for static assets
[ ] Backup strategy for media files

================================================================================
Run `python -c "from mind.config.production import validate_production_config; r = validate_production_config(False); r.print_report(True)"` to validate.
================================================================================
"""
    print(checklist)


# =============================================================================
# STARTUP HOOK
# =============================================================================

def validate_on_startup():
    """
    Validate production configuration at application startup.

    Call this early in your application startup to catch configuration
    errors before they cause runtime issues.
    """
    from mind.config.settings import settings

    if settings.ENVIRONMENT.lower() == "production":
        logger.info("Running production configuration validation...")
        report = validate_production_config(raise_on_critical=True)
        report.print_report(include_info=False)
        logger.info("Production configuration validated successfully")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "ProductionDefaults",
    "ProductionSettings",
    "SecurityLevel",
    "ConfigurationIssue",
    "ValidationReport",
    "validate_production_config",
    "get_production_settings",
    "generate_secure_jwt_secret",
    "print_production_checklist",
    "validate_on_startup",
]
