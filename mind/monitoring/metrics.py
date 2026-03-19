"""
Prometheus metrics definitions for AI Community Companions.
Provides comprehensive metrics for monitoring LLM usage, bot activity, API performance, and system health.
"""

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest

# Create a custom registry to avoid conflicts with default metrics
REGISTRY = CollectorRegistry()

# ============================================================================
# LLM METRICS
# ============================================================================

llm_requests_total = Counter(
    "llm_requests_total",
    "Total number of LLM requests",
    labelnames=["model", "status"],
    registry=REGISTRY,
)

llm_request_duration_seconds = Histogram(
    "llm_request_duration_seconds",
    "LLM request duration in seconds",
    labelnames=["model"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, float("inf")),
    registry=REGISTRY,
)

# ============================================================================
# BOT METRICS
# ============================================================================

active_bots_gauge = Gauge(
    "active_bots",
    "Number of currently active bots",
    registry=REGISTRY,
)

websocket_connections_gauge = Gauge(
    "websocket_connections",
    "Number of active WebSocket connections",
    registry=REGISTRY,
)

posts_created_total = Counter(
    "posts_created_total",
    "Total number of posts created",
    registry=REGISTRY,
)

messages_sent_total = Counter(
    "messages_sent_total",
    "Total number of messages sent",
    labelnames=["type"],  # dm, chat, comment
    registry=REGISTRY,
)

# ============================================================================
# API METRICS
# ============================================================================

api_requests_total = Counter(
    "api_requests_total",
    "Total number of API requests",
    labelnames=["endpoint", "method", "status"],
    registry=REGISTRY,
)

api_request_duration_seconds = Histogram(
    "api_request_duration_seconds",
    "API request duration in seconds",
    labelnames=["endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf")),
    registry=REGISTRY,
)

# ============================================================================
# CIRCUIT BREAKER METRICS
# ============================================================================

circuit_breaker_state = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half-open)",
    labelnames=["service"],
    registry=REGISTRY,
)

# ============================================================================
# SYSTEM METRICS
# ============================================================================

memory_usage_bytes = Gauge(
    "memory_usage_bytes",
    "Current memory usage in bytes",
    registry=REGISTRY,
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def increment_llm_requests(model: str, status: str) -> None:
    """
    Increment the LLM requests counter.

    Args:
        model: The LLM model name (e.g., "phi4-mini", "llama2")
        status: Request status ("success", "error", "timeout")
    """
    llm_requests_total.labels(model=model, status=status).inc()


def observe_llm_duration(model: str, duration_seconds: float) -> None:
    """
    Record an LLM request duration.

    Args:
        model: The LLM model name
        duration_seconds: Duration of the request in seconds
    """
    llm_request_duration_seconds.labels(model=model).observe(duration_seconds)


def set_active_bots(count: int) -> None:
    """
    Set the current number of active bots.

    Args:
        count: Number of active bots
    """
    active_bots_gauge.set(count)


def set_websocket_connections(count: int) -> None:
    """
    Set the current number of WebSocket connections.

    Args:
        count: Number of active WebSocket connections
    """
    websocket_connections_gauge.set(count)


def increment_posts_created() -> None:
    """Increment the posts created counter."""
    posts_created_total.inc()


def increment_messages_sent(message_type: str) -> None:
    """
    Increment the messages sent counter.

    Args:
        message_type: Type of message ("dm", "chat", "comment")
    """
    messages_sent_total.labels(type=message_type).inc()


def increment_api_requests(endpoint: str, method: str, status: int) -> None:
    """
    Increment the API requests counter.

    Args:
        endpoint: API endpoint path
        method: HTTP method (GET, POST, etc.)
        status: HTTP status code
    """
    api_requests_total.labels(
        endpoint=endpoint,
        method=method,
        status=str(status),
    ).inc()


def observe_api_duration(endpoint: str, duration_seconds: float) -> None:
    """
    Record an API request duration.

    Args:
        endpoint: API endpoint path
        duration_seconds: Duration of the request in seconds
    """
    api_request_duration_seconds.labels(endpoint=endpoint).observe(duration_seconds)


def set_circuit_breaker_state(service: str, state: int) -> None:
    """
    Set the circuit breaker state for a service.

    Args:
        service: Service name (e.g., "ollama", "database", "redis")
        state: Circuit breaker state (0=closed, 1=open, 2=half-open)
    """
    circuit_breaker_state.labels(service=service).set(state)


def update_memory_usage() -> None:
    """Update the memory usage gauge with current process memory."""
    if PSUTIL_AVAILABLE:
        process = psutil.Process()
        memory_info = process.memory_info()
        memory_usage_bytes.set(memory_info.rss)
    else:
        # Fallback: set to 0 if psutil is not available
        memory_usage_bytes.set(0)


def get_metrics() -> bytes:
    """
    Generate Prometheus metrics output.

    Returns:
        bytes: Prometheus metrics in text format
    """
    # Update memory usage before generating metrics
    update_memory_usage()
    return generate_latest(REGISTRY)
