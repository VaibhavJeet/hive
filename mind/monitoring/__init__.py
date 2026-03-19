"""
Monitoring module for AI Community Companions.
Provides Prometheus metrics and health checking capabilities.
"""

from mind.monitoring.metrics import (
    llm_requests_total,
    llm_request_duration_seconds,
    active_bots_gauge,
    websocket_connections_gauge,
    posts_created_total,
    messages_sent_total,
    api_requests_total,
    api_request_duration_seconds,
    circuit_breaker_state,
    memory_usage_bytes,
    increment_llm_requests,
    observe_llm_duration,
    set_active_bots,
    set_websocket_connections,
    increment_posts_created,
    increment_messages_sent,
    increment_api_requests,
    observe_api_duration,
    set_circuit_breaker_state,
    update_memory_usage,
)

from mind.monitoring.health import (
    HealthStatus,
    SystemHealth,
    HealthChecker,
    get_health_checker,
)

from mind.monitoring.middleware import MetricsMiddleware

__all__ = [
    # Metrics
    "llm_requests_total",
    "llm_request_duration_seconds",
    "active_bots_gauge",
    "websocket_connections_gauge",
    "posts_created_total",
    "messages_sent_total",
    "api_requests_total",
    "api_request_duration_seconds",
    "circuit_breaker_state",
    "memory_usage_bytes",
    # Helper functions
    "increment_llm_requests",
    "observe_llm_duration",
    "set_active_bots",
    "set_websocket_connections",
    "increment_posts_created",
    "increment_messages_sent",
    "increment_api_requests",
    "observe_api_duration",
    "set_circuit_breaker_state",
    "update_memory_usage",
    # Health
    "HealthStatus",
    "SystemHealth",
    "HealthChecker",
    "get_health_checker",
    # Middleware
    "MetricsMiddleware",
]
