"""
Metrics middleware for FastAPI.
Records request metrics for Prometheus monitoring.
"""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from mind.config.settings import settings
from mind.monitoring.metrics import (
    increment_api_requests,
    observe_api_duration,
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for recording Prometheus metrics.

    Records:
    - Total API requests by endpoint, method, and status
    - Request duration by endpoint
    """

    def __init__(self, app: ASGIApp, excluded_paths: list = None):
        """
        Initialize metrics middleware.

        Args:
            app: FastAPI application
            excluded_paths: List of paths to exclude from metrics
        """
        super().__init__(app)
        self.excluded_paths = excluded_paths or [
            "/metrics",
            "/health/live",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]

    def _normalize_path(self, path: str) -> str:
        """
        Normalize path for metrics grouping.

        Replaces UUIDs and numeric IDs with placeholders to avoid
        high cardinality metrics.

        Args:
            path: Raw request path

        Returns:
            Normalized path suitable for metrics labels
        """
        import re

        # Replace UUIDs
        path = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "{id}",
            path,
            flags=re.IGNORECASE,
        )

        # Replace numeric IDs
        path = re.sub(r"/\d+", "/{id}", path)

        return path

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and record metrics.

        Args:
            request: Incoming request
            call_next: Next middleware/handler in chain

        Returns:
            Response from handler
        """
        # Skip metrics collection if disabled
        if not settings.METRICS_ENABLED:
            return await call_next(request)

        # Skip excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        # Record start time
        start_time = time.perf_counter()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.perf_counter() - start_time

        # Normalize path for metrics
        normalized_path = self._normalize_path(request.url.path)

        # Record metrics
        increment_api_requests(
            endpoint=normalized_path,
            method=request.method,
            status=response.status_code,
        )
        observe_api_duration(
            endpoint=normalized_path,
            duration_seconds=duration,
        )

        return response
