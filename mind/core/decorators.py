"""
Utility Decorators for AI Community Companions.

Provides reusable decorators for:
- Error handling
- Retry logic with backoff
- Timeout handling
- Rate limiting
- Execution time logging
"""

import asyncio
import functools
import logging
import time
from typing import Any, Callable, Optional, Type, Tuple, Union
from collections import defaultdict

from mind.core.errors import (
    AppError,
    RateLimitError,
    LLMError,
    LLMTimeoutError,
    DatabaseError,
    ErrorCode
)


logger = logging.getLogger(__name__)


# ============================================================================
# ERROR HANDLING DECORATOR
# ============================================================================

def handle_errors(
    *exception_types: Type[Exception],
    default_error: Optional[Type[AppError]] = None,
    error_message: Optional[str] = None,
    log_traceback: bool = True
) -> Callable:
    """
    Decorator to catch and convert exceptions to AppError types.

    Args:
        exception_types: Specific exception types to catch (catches all if empty)
        default_error: AppError subclass to raise for uncaught exceptions
        error_message: Custom error message to use
        log_traceback: Whether to log the full traceback

    Usage:
        @handle_errors(ValueError, TypeError)
        async def my_function():
            ...

        @handle_errors(default_error=DatabaseError)
        async def db_operation():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            try:
                return await func(*args, **kwargs)
            except AppError:
                # Re-raise AppError subclasses as-is
                raise
            except exception_types as e:
                # Catch specific exception types
                if log_traceback:
                    logger.exception(f"Error in {func.__name__}: {e}")
                else:
                    logger.error(f"Error in {func.__name__}: {e}")

                if default_error:
                    raise default_error(
                        message=error_message or str(e)
                    ) from e
                raise
            except Exception as e:
                # Catch all other exceptions
                if log_traceback:
                    logger.exception(f"Unexpected error in {func.__name__}: {e}")
                else:
                    logger.error(f"Unexpected error in {func.__name__}: {e}")

                if default_error:
                    raise default_error(
                        message=error_message or "An unexpected error occurred"
                    ) from e
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except AppError:
                raise
            except exception_types as e:
                if log_traceback:
                    logger.exception(f"Error in {func.__name__}: {e}")
                else:
                    logger.error(f"Error in {func.__name__}: {e}")

                if default_error:
                    raise default_error(
                        message=error_message or str(e)
                    ) from e
                raise
            except Exception as e:
                if log_traceback:
                    logger.exception(f"Unexpected error in {func.__name__}: {e}")
                else:
                    logger.error(f"Unexpected error in {func.__name__}: {e}")

                if default_error:
                    raise default_error(
                        message=error_message or "An unexpected error occurred"
                    ) from e
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    # Handle decorator with or without arguments
    if len(exception_types) == 1 and callable(exception_types[0]) and \
       not isinstance(exception_types[0], type):
        # Called without arguments: @handle_errors
        func = exception_types[0]
        exception_types = (Exception,)
        return decorator(func)

    if not exception_types:
        exception_types = (Exception,)

    return decorator


# ============================================================================
# RETRY DECORATOR
# ============================================================================

def retry(
    max_attempts: int = 3,
    backoff: bool = True,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
) -> Callable:
    """
    Decorator to retry failed operations with optional exponential backoff.

    Args:
        max_attempts: Maximum number of attempts (including initial)
        backoff: Whether to use exponential backoff
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff calculation
        exceptions: Exception types to retry on
        on_retry: Callback function called on each retry with (exception, attempt)

    Usage:
        @retry(max_attempts=3, backoff=True)
        async def unreliable_operation():
            ...

        @retry(max_attempts=5, exceptions=(ConnectionError, TimeoutError))
        async def network_call():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    is_last_attempt = attempt == max_attempts

                    if is_last_attempt:
                        logger.error(
                            f"[RETRY] {func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    # Calculate delay
                    if backoff:
                        delay = min(
                            base_delay * (exponential_base ** (attempt - 1)),
                            max_delay
                        )
                    else:
                        delay = base_delay

                    logger.warning(
                        f"[RETRY] {func.__name__} attempt {attempt}/{max_attempts} "
                        f"failed: {e}. Retrying in {delay:.1f}s..."
                    )

                    if on_retry:
                        on_retry(e, attempt)

                    await asyncio.sleep(delay)

            raise last_exception

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    is_last_attempt = attempt == max_attempts

                    if is_last_attempt:
                        logger.error(
                            f"[RETRY] {func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    if backoff:
                        delay = min(
                            base_delay * (exponential_base ** (attempt - 1)),
                            max_delay
                        )
                    else:
                        delay = base_delay

                    logger.warning(
                        f"[RETRY] {func.__name__} attempt {attempt}/{max_attempts} "
                        f"failed: {e}. Retrying in {delay:.1f}s..."
                    )

                    if on_retry:
                        on_retry(e, attempt)

                    time.sleep(delay)

            raise last_exception

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# ============================================================================
# TIMEOUT DECORATOR
# ============================================================================

def timeout(seconds: float = 30.0, error_message: Optional[str] = None) -> Callable:
    """
    Decorator to add timeout to async functions.

    Args:
        seconds: Timeout duration in seconds
        error_message: Custom error message for timeout

    Usage:
        @timeout(seconds=30)
        async def slow_operation():
            ...

    Raises:
        LLMTimeoutError: When operation times out
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=seconds
                )
            except asyncio.TimeoutError:
                msg = error_message or f"{func.__name__} timed out after {seconds}s"
                logger.error(f"[TIMEOUT] {msg}")
                raise LLMTimeoutError(timeout_seconds=seconds) from None

        return wrapper

    return decorator


# ============================================================================
# RATE LIMIT DECORATOR
# ============================================================================

class InMemoryRateLimiter:
    """Simple in-memory rate limiter for decorator use."""

    def __init__(self):
        self.requests: dict = defaultdict(list)

    def is_allowed(self, key: str, limit: int, window: float) -> Tuple[bool, float]:
        """
        Check if request is allowed.

        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        now = time.time()
        window_start = now - window

        # Clean old requests
        self.requests[key] = [t for t in self.requests[key] if t > window_start]

        if len(self.requests[key]) >= limit:
            oldest = min(self.requests[key])
            retry_after = oldest + window - now
            return False, max(0, retry_after)

        self.requests[key].append(now)
        return True, 0


_rate_limiter = InMemoryRateLimiter()


def rate_limit(
    requests_per_minute: int = 60,
    key_func: Optional[Callable[..., str]] = None,
    error_message: Optional[str] = None
) -> Callable:
    """
    Decorator to rate limit function calls.

    Args:
        requests_per_minute: Maximum requests per minute
        key_func: Function to extract rate limit key from arguments
        error_message: Custom error message

    Usage:
        @rate_limit(requests_per_minute=60)
        async def api_call():
            ...

        @rate_limit(requests_per_minute=10, key_func=lambda user_id: f"user:{user_id}")
        async def user_action(user_id: str):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # Determine rate limit key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = f"{func.__module__}.{func.__name__}"

            is_allowed, retry_after = _rate_limiter.is_allowed(
                key=key,
                limit=requests_per_minute,
                window=60.0
            )

            if not is_allowed:
                msg = error_message or "Rate limit exceeded"
                logger.warning(f"[RATE_LIMIT] {func.__name__}: {msg}")
                raise RateLimitError(
                    message=msg,
                    retry_after=retry_after,
                    limit=requests_per_minute,
                    window="1 minute"
                )

            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = f"{func.__module__}.{func.__name__}"

            is_allowed, retry_after = _rate_limiter.is_allowed(
                key=key,
                limit=requests_per_minute,
                window=60.0
            )

            if not is_allowed:
                msg = error_message or "Rate limit exceeded"
                logger.warning(f"[RATE_LIMIT] {func.__name__}: {msg}")
                raise RateLimitError(
                    message=msg,
                    retry_after=retry_after,
                    limit=requests_per_minute,
                    window="1 minute"
                )

            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# ============================================================================
# EXECUTION TIME LOGGING DECORATOR
# ============================================================================

def log_execution_time(
    threshold_ms: float = 0,
    log_level: int = logging.DEBUG,
    include_args: bool = False
) -> Callable:
    """
    Decorator to log function execution time.

    Args:
        threshold_ms: Only log if execution time exceeds this threshold
        log_level: Logging level to use
        include_args: Whether to include function arguments in log

    Usage:
        @log_execution_time(threshold_ms=100)
        async def slow_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                elapsed_ms = (time.perf_counter() - start_time) * 1000

                if elapsed_ms >= threshold_ms:
                    msg = f"[TIMING] {func.__name__} took {elapsed_ms:.2f}ms"
                    if include_args:
                        msg += f" (args={args}, kwargs={kwargs})"

                    logger.log(log_level, msg)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed_ms = (time.perf_counter() - start_time) * 1000

                if elapsed_ms >= threshold_ms:
                    msg = f"[TIMING] {func.__name__} took {elapsed_ms:.2f}ms"
                    if include_args:
                        msg += f" (args={args}, kwargs={kwargs})"

                    logger.log(log_level, msg)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# ============================================================================
# COMBINED DECORATOR FOR LLM CALLS
# ============================================================================

def llm_call(
    timeout_seconds: float = 30.0,
    max_retries: int = 3,
    rate_limit_rpm: int = 60
) -> Callable:
    """
    Combined decorator for LLM calls with timeout, retry, and rate limiting.

    Usage:
        @llm_call(timeout_seconds=30, max_retries=3)
        async def generate_response():
            ...
    """
    def decorator(func: Callable) -> Callable:
        # Apply decorators in order: rate_limit -> retry -> timeout -> log_time
        decorated = log_execution_time(threshold_ms=100, log_level=logging.INFO)(func)
        decorated = timeout(seconds=timeout_seconds)(decorated)
        decorated = retry(
            max_attempts=max_retries,
            backoff=True,
            exceptions=(LLMError, asyncio.TimeoutError, ConnectionError)
        )(decorated)
        decorated = rate_limit(requests_per_minute=rate_limit_rpm)(decorated)

        return decorated

    return decorator
