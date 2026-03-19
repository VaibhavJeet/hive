"""
FastAPI Error Handlers for AI Community Companions.

Registers exception handlers with FastAPI to convert exceptions
to consistent HTTP responses with proper logging.
"""

import logging
import traceback
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError as PydanticValidationError

from mind.core.errors import (
    AppError,
    ValidationError,
    NotFoundError,
    AuthenticationError,
    AuthorizationError,
    RateLimitError,
    LLMError,
    DatabaseError,
    ErrorCode
)


logger = logging.getLogger(__name__)


def create_error_response(
    error_code: str,
    message: str,
    details: dict = None,
    http_status: int = 500
) -> JSONResponse:
    """Create a standardized JSON error response."""
    content = {
        "error": {
            "code": error_code,
            "message": message,
            "details": details or {}
        }
    }

    headers = {}
    if http_status == 429 and details and "retry_after_seconds" in details:
        headers["Retry-After"] = str(int(details["retry_after_seconds"]))

    return JSONResponse(
        status_code=http_status,
        content=content,
        headers=headers if headers else None
    )


def register_error_handlers(app: FastAPI) -> None:
    """
    Register all error handlers with FastAPI application.

    This function should be called during application startup to ensure
    all exceptions are handled consistently.
    """

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        """Handle all AppError exceptions."""
        # Log based on severity
        if exc.http_status >= 500:
            logger.error(
                f"[{exc.error_code.value}] {exc.message}",
                extra={
                    "error_code": exc.error_code.value,
                    "details": exc.details,
                    "path": request.url.path,
                    "method": request.method
                }
            )
        else:
            logger.warning(
                f"[{exc.error_code.value}] {exc.message}",
                extra={
                    "error_code": exc.error_code.value,
                    "path": request.url.path
                }
            )

        return create_error_response(
            error_code=exc.error_code.value,
            message=exc.message,
            details=exc.details,
            http_status=exc.http_status
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError
    ) -> JSONResponse:
        """Handle Pydantic/FastAPI validation errors."""
        errors = exc.errors()

        # Format validation errors
        formatted_errors = []
        for error in errors:
            location = ".".join(str(loc) for loc in error.get("loc", []))
            formatted_errors.append({
                "field": location,
                "message": error.get("msg", "Invalid value"),
                "type": error.get("type", "unknown")
            })

        logger.warning(
            f"Validation error on {request.method} {request.url.path}",
            extra={"errors": formatted_errors}
        )

        return create_error_response(
            error_code=ErrorCode.VALIDATION_ERROR.value,
            message="Request validation failed",
            details={"validation_errors": formatted_errors},
            http_status=422
        )

    @app.exception_handler(PydanticValidationError)
    async def pydantic_validation_handler(
        request: Request,
        exc: PydanticValidationError
    ) -> JSONResponse:
        """Handle Pydantic validation errors outside of FastAPI routes."""
        errors = exc.errors()

        formatted_errors = []
        for error in errors:
            location = ".".join(str(loc) for loc in error.get("loc", []))
            formatted_errors.append({
                "field": location,
                "message": error.get("msg", "Invalid value"),
                "type": error.get("type", "unknown")
            })

        return create_error_response(
            error_code=ErrorCode.VALIDATION_ERROR.value,
            message="Data validation failed",
            details={"validation_errors": formatted_errors},
            http_status=400
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException
    ) -> JSONResponse:
        """Handle standard HTTP exceptions."""
        # Map status codes to error codes
        status_to_code = {
            400: ErrorCode.BAD_REQUEST,
            401: ErrorCode.AUTHENTICATION_REQUIRED,
            403: ErrorCode.PERMISSION_DENIED,
            404: ErrorCode.NOT_FOUND,
            409: ErrorCode.CONFLICT,
            429: ErrorCode.RATE_LIMIT_EXCEEDED,
            500: ErrorCode.INTERNAL_ERROR,
        }

        error_code = status_to_code.get(exc.status_code, ErrorCode.INTERNAL_ERROR)

        if exc.status_code >= 500:
            logger.error(
                f"HTTP {exc.status_code}: {exc.detail}",
                extra={"path": request.url.path, "method": request.method}
            )
        else:
            logger.warning(
                f"HTTP {exc.status_code}: {exc.detail}",
                extra={"path": request.url.path}
            )

        return create_error_response(
            error_code=error_code.value,
            message=str(exc.detail) if exc.detail else "An error occurred",
            http_status=exc.status_code
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception
    ) -> JSONResponse:
        """Handle any unhandled exceptions."""
        # Log the full traceback for unhandled exceptions
        logger.error(
            f"Unhandled exception: {type(exc).__name__}: {str(exc)}",
            extra={
                "path": request.url.path,
                "method": request.method,
                "traceback": traceback.format_exc()
            },
            exc_info=True
        )

        return create_error_response(
            error_code=ErrorCode.INTERNAL_ERROR.value,
            message="An unexpected error occurred",
            details={
                "type": type(exc).__name__,
                # Only include exception message in non-production
                # In production, you might want to hide this
            },
            http_status=500
        )

    logger.info("Error handlers registered successfully")


def create_error_middleware() -> Callable:
    """
    Create an error handling middleware for additional error processing.

    This middleware can be used for cross-cutting concerns like:
    - Request ID tracking
    - Error metrics collection
    - Custom error transformations
    """
    async def error_middleware(request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            # Re-raise to let exception handlers deal with it
            raise

    return error_middleware
