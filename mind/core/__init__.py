"""Core module containing types, database, LLM client, caching, and pub/sub."""

from mind.core.redis_client import (
    RedisClient,
    get_redis_client,
    close_redis_client,
    REDIS_AVAILABLE,
)
from mind.core.cache import (
    CacheService,
    get_cache_service,
    cached,
)
from mind.core.pubsub import (
    PubSubService,
    Event,
    EventType,
    EventChannel,
    get_pubsub_service,
    close_pubsub_service,
)
from mind.core.llm_pool import (
    LLMPool,
    LoadBalancingStrategy,
    get_llm_pool,
    close_llm_pool,
)
from mind.core.embedding_batch import (
    EmbeddingBatcher,
    get_embedding_batcher,
    close_embedding_batcher,
)
from mind.core.idle_precompute import (
    IdlePrecomputer,
    get_idle_precomputer,
    close_idle_precomputer,
)
from mind.core.errors import (
    AppError,
    ValidationError,
    NotFoundError,
    AuthenticationError,
    AuthorizationError,
    RateLimitError,
    LLMError,
    DatabaseError,
    ErrorCode,
)
from mind.core.llm_rate_limiter import (
    LLMRateLimiter,
    Priority,
    get_llm_rate_limiter,
)
from mind.core.decorators import (
    handle_errors,
    retry,
    timeout,
    rate_limit,
    log_execution_time,
)

__all__ = [
    # Redis
    "RedisClient",
    "get_redis_client",
    "close_redis_client",
    "REDIS_AVAILABLE",
    # Cache
    "CacheService",
    "get_cache_service",
    "cached",
    # PubSub
    "PubSubService",
    "Event",
    "EventType",
    "EventChannel",
    "get_pubsub_service",
    "close_pubsub_service",
    # LLM Pool
    "LLMPool",
    "LoadBalancingStrategy",
    "get_llm_pool",
    "close_llm_pool",
    # Embedding Batcher
    "EmbeddingBatcher",
    "get_embedding_batcher",
    "close_embedding_batcher",
    # Idle Precompute
    "IdlePrecomputer",
    "get_idle_precomputer",
    "close_idle_precomputer",
    # Errors
    "AppError",
    "ValidationError",
    "NotFoundError",
    "AuthenticationError",
    "AuthorizationError",
    "RateLimitError",
    "LLMError",
    "DatabaseError",
    "ErrorCode",
    # LLM Rate Limiter
    "LLMRateLimiter",
    "Priority",
    "get_llm_rate_limiter",
    # Decorators
    "handle_errors",
    "retry",
    "timeout",
    "rate_limit",
    "log_execution_time",
]
