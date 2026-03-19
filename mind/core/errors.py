"""
Custom Exception Hierarchy for AI Community Companions.

Provides standardized error types with error codes, messages, and details
for consistent error handling across the application.
"""

from typing import Any, Dict, Optional
from enum import Enum


class ErrorCode(str, Enum):
    """Standardized error codes."""
    # General errors (1000-1999)
    INTERNAL_ERROR = "E1000"
    VALIDATION_ERROR = "E1001"
    NOT_FOUND = "E1002"
    CONFLICT = "E1003"
    BAD_REQUEST = "E1004"

    # Authentication errors (2000-2999)
    AUTHENTICATION_REQUIRED = "E2000"
    INVALID_CREDENTIALS = "E2001"
    TOKEN_EXPIRED = "E2002"
    TOKEN_INVALID = "E2003"
    TOKEN_REVOKED = "E2004"

    # Authorization errors (3000-3999)
    PERMISSION_DENIED = "E3000"
    INSUFFICIENT_PRIVILEGES = "E3001"
    RESOURCE_ACCESS_DENIED = "E3002"

    # Rate limiting errors (4000-4999)
    RATE_LIMIT_EXCEEDED = "E4000"
    TOO_MANY_REQUESTS = "E4001"
    QUOTA_EXCEEDED = "E4002"

    # LLM errors (5000-5999)
    LLM_UNAVAILABLE = "E5000"
    LLM_TIMEOUT = "E5001"
    LLM_CIRCUIT_OPEN = "E5002"
    LLM_GENERATION_FAILED = "E5003"
    LLM_MODEL_NOT_FOUND = "E5004"
    LLM_QUEUE_FULL = "E5005"

    # Database errors (6000-6999)
    DATABASE_ERROR = "E6000"
    DATABASE_CONNECTION_FAILED = "E6001"
    DATABASE_QUERY_FAILED = "E6002"
    DATABASE_TRANSACTION_FAILED = "E6003"
    DATABASE_INTEGRITY_ERROR = "E6004"

    # External service errors (7000-7999)
    EXTERNAL_SERVICE_ERROR = "E7000"
    EXTERNAL_SERVICE_TIMEOUT = "E7001"
    EXTERNAL_SERVICE_UNAVAILABLE = "E7002"


class AppError(Exception):
    """
    Base exception for all application errors.

    Provides consistent error structure with:
    - error_code: Unique identifier for the error type
    - message: Human-readable error message
    - details: Additional context about the error
    - http_status: Corresponding HTTP status code
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        details: Optional[Dict[str, Any]] = None,
        http_status: int = 500
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.http_status = http_status

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for JSON response."""
        return {
            "error": {
                "code": self.error_code.value,
                "message": self.message,
                "details": self.details
            }
        }

    def __str__(self) -> str:
        return f"[{self.error_code.value}] {self.message}"


class ValidationError(AppError):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str = "Validation failed",
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if field:
            error_details["field"] = field

        super().__init__(
            message=message,
            error_code=ErrorCode.VALIDATION_ERROR,
            details=error_details,
            http_status=400
        )


class NotFoundError(AppError):
    """Raised when a requested resource is not found."""

    def __init__(
        self,
        resource_type: str = "Resource",
        resource_id: Optional[str] = None,
        message: Optional[str] = None
    ):
        details = {"resource_type": resource_type}
        if resource_id:
            details["resource_id"] = resource_id

        super().__init__(
            message=message or f"{resource_type} not found",
            error_code=ErrorCode.NOT_FOUND,
            details=details,
            http_status=404
        )


class AuthenticationError(AppError):
    """Raised when authentication fails."""

    def __init__(
        self,
        message: str = "Authentication required",
        error_code: ErrorCode = ErrorCode.AUTHENTICATION_REQUIRED,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            http_status=401
        )


class AuthorizationError(AppError):
    """Raised when user lacks permission for an action."""

    def __init__(
        self,
        message: str = "Permission denied",
        required_permission: Optional[str] = None,
        resource: Optional[str] = None
    ):
        details = {}
        if required_permission:
            details["required_permission"] = required_permission
        if resource:
            details["resource"] = resource

        super().__init__(
            message=message,
            error_code=ErrorCode.PERMISSION_DENIED,
            details=details,
            http_status=403
        )


class RateLimitError(AppError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[float] = None,
        limit: Optional[int] = None,
        window: Optional[str] = None
    ):
        details = {}
        if retry_after is not None:
            details["retry_after_seconds"] = retry_after
        if limit is not None:
            details["limit"] = limit
        if window:
            details["window"] = window

        super().__init__(
            message=message,
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            details=details,
            http_status=429
        )


class LLMError(AppError):
    """Raised when LLM operations fail."""

    def __init__(
        self,
        message: str = "LLM operation failed",
        error_code: ErrorCode = ErrorCode.LLM_UNAVAILABLE,
        model: Optional[str] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if model:
            error_details["model"] = model
        if operation:
            error_details["operation"] = operation

        super().__init__(
            message=message,
            error_code=error_code,
            details=error_details,
            http_status=503
        )


class LLMTimeoutError(LLMError):
    """Raised when LLM request times out."""

    def __init__(
        self,
        timeout_seconds: float,
        model: Optional[str] = None
    ):
        super().__init__(
            message=f"LLM request timed out after {timeout_seconds}s",
            error_code=ErrorCode.LLM_TIMEOUT,
            model=model,
            details={"timeout_seconds": timeout_seconds}
        )


class LLMCircuitOpenError(LLMError):
    """Raised when LLM circuit breaker is open."""

    def __init__(
        self,
        recovery_time: Optional[float] = None
    ):
        details = {}
        if recovery_time:
            details["estimated_recovery_seconds"] = recovery_time

        super().__init__(
            message="LLM service temporarily unavailable (circuit breaker open)",
            error_code=ErrorCode.LLM_CIRCUIT_OPEN,
            details=details
        )


class LLMQueueFullError(LLMError):
    """Raised when LLM request queue is full."""

    def __init__(
        self,
        queue_length: int,
        max_queue_length: int
    ):
        super().__init__(
            message="LLM request queue is full, please try again later",
            error_code=ErrorCode.LLM_QUEUE_FULL,
            details={
                "queue_length": queue_length,
                "max_queue_length": max_queue_length
            }
        )


class DatabaseError(AppError):
    """Raised when database operations fail."""

    def __init__(
        self,
        message: str = "Database operation failed",
        error_code: ErrorCode = ErrorCode.DATABASE_ERROR,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if operation:
            error_details["operation"] = operation

        super().__init__(
            message=message,
            error_code=error_code,
            details=error_details,
            http_status=500
        )


class ConflictError(AppError):
    """Raised when there's a resource conflict (e.g., duplicate)."""

    def __init__(
        self,
        message: str = "Resource conflict",
        resource_type: Optional[str] = None,
        conflicting_field: Optional[str] = None
    ):
        details = {}
        if resource_type:
            details["resource_type"] = resource_type
        if conflicting_field:
            details["conflicting_field"] = conflicting_field

        super().__init__(
            message=message,
            error_code=ErrorCode.CONFLICT,
            details=details,
            http_status=409
        )


class ExternalServiceError(AppError):
    """Raised when external service calls fail."""

    def __init__(
        self,
        service_name: str,
        message: Optional[str] = None,
        error_code: ErrorCode = ErrorCode.EXTERNAL_SERVICE_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details["service"] = service_name

        super().__init__(
            message=message or f"External service '{service_name}' failed",
            error_code=error_code,
            details=error_details,
            http_status=502
        )
