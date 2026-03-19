"""
LLM Client for AI Community Companions.
Handles inference with Ollama and other local LLM providers.
"""

import asyncio
import aiohttp
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID
import time

from mind.config.settings import settings
from mind.core.errors import (
    LLMError,
    LLMTimeoutError,
    LLMCircuitOpenError,
    LLMQueueFullError,
    ErrorCode
)

logger = logging.getLogger(__name__)


# ============================================================================
# CIRCUIT BREAKER
# ============================================================================

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker pattern for LLM calls.
    Prevents cascading failures when Ollama is overloaded or down.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def is_closed(self) -> bool:
        return self._state == CircuitState.CLOSED

    async def can_execute(self) -> bool:
        """Check if a request can be executed."""
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if time.time() - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info("[CIRCUIT] Transitioning to HALF_OPEN state")
                    return True
                return False

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls < self.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False

            return False

    async def record_success(self):
        """Record a successful call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                logger.info("[CIRCUIT] Recovered - transitioning to CLOSED state")
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    async def record_failure(self):
        """Record a failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning("[CIRCUIT] Recovery failed - transitioning to OPEN state")
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    self._state = CircuitState.OPEN
                    logger.warning(f"[CIRCUIT] Failure threshold reached ({self._failure_count}) - transitioning to OPEN state")

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "state": self._state.value,
            "failure_count": self._failure_count,
            "last_failure_time": self._last_failure_time,
            "half_open_calls": self._half_open_calls,
        }


# ============================================================================
# LLM REQUEST/RESPONSE TYPES
# ============================================================================

@dataclass
class LLMRequest:
    """Request for LLM generation."""
    prompt: str
    system_prompt: Optional[str] = None
    max_tokens: int = 512
    temperature: float = 0.8
    stop_sequences: Optional[List[str]] = None
    request_id: Optional[str] = None
    bot_id: Optional[UUID] = None  # For per-bot rate limiting
    priority: Optional[int] = None  # Priority level (see llm_rate_limiter.Priority)


@dataclass
class LLMResponse:
    """Response from LLM generation."""
    text: str
    tokens_used: int
    generation_time_ms: float
    request_id: Optional[str] = None
    model: str = ""


# ============================================================================
# OLLAMA CLIENT
# ============================================================================

class OllamaClient:
    """
    Async client for Ollama API.
    Optimized for high throughput with connection pooling.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2:8b",
        max_concurrent: int = 8,
        timeout: int = 30
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None
        self._semaphore = asyncio.Semaphore(max_concurrent)

        # Circuit breaker for failure protection
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30.0,
            half_open_max_calls=3
        )

        # Stats
        self.total_requests = 0
        self.total_tokens = 0
        self.total_time_ms = 0

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=settings.LLM_MAX_CONCURRENT_REQUESTS,
                keepalive_timeout=300
            )
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=self.timeout
            )
        return self._session

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate completion for a single request with circuit breaker protection."""
        # Check circuit breaker
        if not await self.circuit_breaker.can_execute():
            logger.warning("[CIRCUIT] Request rejected - circuit is OPEN")
            raise LLMCircuitOpenError(
                recovery_time=self.circuit_breaker.recovery_timeout
            )

        async with self._semaphore:
            try:
                result = await self._do_generate(request)
                await self.circuit_breaker.record_success()
                return result
            except asyncio.TimeoutError:
                await self.circuit_breaker.record_failure()
                raise LLMTimeoutError(
                    timeout_seconds=self.timeout.total,
                    model=self.model
                )
            except LLMError:
                await self.circuit_breaker.record_failure()
                raise
            except Exception as e:
                await self.circuit_breaker.record_failure()
                raise LLMError(
                    message=f"LLM generation failed: {str(e)}",
                    error_code=ErrorCode.LLM_GENERATION_FAILED,
                    model=self.model
                ) from e

    async def _do_generate(self, request: LLMRequest) -> LLMResponse:
        """Internal generation method."""
        session = await self._get_session()
        start_time = time.perf_counter()

        # Build Ollama request
        payload = {
            "model": self.model,
            "prompt": request.prompt,
            "stream": False,
            "options": {
                "num_predict": request.max_tokens,
                "temperature": request.temperature,
            }
        }

        if request.system_prompt:
            payload["system"] = request.system_prompt

        if request.stop_sequences:
            payload["options"]["stop"] = request.stop_sequences

        try:
            async with session.post(
                f"{self.base_url}/api/generate",
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise LLMError(
                        message=f"Ollama error: {response.status} - {error_text}",
                        error_code=ErrorCode.LLM_GENERATION_FAILED,
                        model=self.model
                    )

                data = await response.json()

        except asyncio.TimeoutError:
            raise LLMTimeoutError(
                timeout_seconds=self.timeout.total,
                model=self.model
            )

        end_time = time.perf_counter()
        generation_time = (end_time - start_time) * 1000

        # Update stats
        self.total_requests += 1
        self.total_tokens += data.get("eval_count", 0)
        self.total_time_ms += generation_time

        return LLMResponse(
            text=data.get("response", ""),
            tokens_used=data.get("eval_count", 0),
            generation_time_ms=generation_time,
            request_id=request.request_id,
            model=self.model
        )

    async def generate_batch(
        self,
        requests: List[LLMRequest]
    ) -> List[LLMResponse]:
        """Generate completions for multiple requests concurrently."""
        tasks = [self.generate(req) for req in requests]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.8
    ) -> LLMResponse:
        """Chat completion with message history."""
        session = await self._get_session()
        start_time = time.perf_counter()

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            }
        }

        async with self._semaphore:
            try:
                async with session.post(
                    f"{self.base_url}/api/chat",
                    json=payload
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Ollama chat error: {response.status} - {error_text}")

                    data = await response.json()

            except asyncio.TimeoutError:
                raise Exception(f"Ollama chat timed out")

        end_time = time.perf_counter()
        generation_time = (end_time - start_time) * 1000

        # Update stats
        self.total_requests += 1
        self.total_tokens += data.get("eval_count", 0)
        self.total_time_ms += generation_time

        return LLMResponse(
            text=data.get("message", {}).get("content", ""),
            tokens_used=data.get("eval_count", 0),
            generation_time_ms=generation_time,
            model=self.model
        )

    async def check_health(self) -> bool:
        """Check if Ollama is running and model is available."""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/api/tags") as response:
                if response.status != 200:
                    return False

                data = await response.json()
                models = [m["name"] for m in data.get("models", [])]

                # Check if our model is available
                model_base = self.model.split(":")[0]
                return any(model_base in m for m in models)

        except Exception:
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics including circuit breaker status."""
        avg_time = self.total_time_ms / max(1, self.total_requests)
        return {
            "total_requests": self.total_requests,
            "total_tokens": self.total_tokens,
            "total_time_ms": self.total_time_ms,
            "avg_time_ms": avg_time,
            "tokens_per_second": self.total_tokens / max(1, self.total_time_ms / 1000),
            "circuit_breaker": self.circuit_breaker.get_stats()
        }

    async def close(self):
        """Close the client session."""
        if self._session and not self._session.closed:
            await self._session.close()


# ============================================================================
# CACHED LLM CLIENT
# ============================================================================

class CachedLLMClient:
    """
    LLM client with response caching for common prompts.
    Reduces inference load for repetitive requests.

    Uses Redis for distributed caching with automatic fallback
    to in-memory cache if Redis is unavailable.
    """

    def __init__(
        self,
        client: OllamaClient,
        cache_size: int = 1000,
        redis_cache_ttl: int = 3600
    ):
        self.client = client
        self.cache_size = cache_size
        self.redis_cache_ttl = redis_cache_ttl

        # In-memory fallback cache
        self.cache: Dict[str, LLMResponse] = {}
        self.cache_hits = 0
        self.cache_misses = 0
        self.redis_hits = 0
        self.redis_misses = 0

        # Redis cache service (lazy initialized)
        self._cache_service = None
        self._redis_available = None

    async def _get_cache_service(self):
        """Get Redis cache service, checking availability."""
        if self._cache_service is None:
            try:
                from mind.core.cache import CacheService, get_redis_client
                redis_client = await get_redis_client()
                self._cache_service = CacheService(redis_client)
                self._redis_available = redis_client.is_connected
            except Exception as e:
                logger.debug(f"[LLM_CACHE] Redis not available: {e}")
                self._redis_available = False

        return self._cache_service if self._redis_available else None

    def _make_cache_key(self, request: LLMRequest) -> str:
        """Create a cache key from request."""
        return f"{request.system_prompt}|{request.prompt}|{request.temperature}"

    def _make_prompt_hash(self, request: LLMRequest) -> str:
        """Create a hash for Redis cache key."""
        import hashlib
        content = self._make_cache_key(request)
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    async def _get_from_redis(self, prompt_hash: str) -> Optional[LLMResponse]:
        """Try to get cached response from Redis."""
        cache_service = await self._get_cache_service()
        if not cache_service:
            return None

        try:
            cached = await cache_service.get_cached_llm_response(prompt_hash)
            if cached:
                self.redis_hits += 1
                return LLMResponse(
                    text=cached["response"],
                    tokens_used=cached.get("metadata", {}).get("tokens_used", 0),
                    generation_time_ms=0,
                    model=cached.get("metadata", {}).get("model", "")
                )
        except Exception as e:
            logger.debug(f"[LLM_CACHE] Redis get error: {e}")

        self.redis_misses += 1
        return None

    async def _set_in_redis(self, prompt_hash: str, response: LLMResponse) -> bool:
        """Cache response in Redis."""
        cache_service = await self._get_cache_service()
        if not cache_service:
            return False

        try:
            return await cache_service.cache_llm_response(
                prompt_hash=prompt_hash,
                response=response.text,
                metadata={
                    "tokens_used": response.tokens_used,
                    "model": response.model
                },
                ttl=self.redis_cache_ttl
            )
        except Exception as e:
            logger.debug(f"[LLM_CACHE] Redis set error: {e}")
            return False

    async def generate(
        self,
        request: LLMRequest,
        use_cache: bool = True
    ) -> LLMResponse:
        """Generate with optional caching (Redis + in-memory fallback)."""
        if not use_cache:
            return await self.client.generate(request)

        cache_key = self._make_cache_key(request)
        prompt_hash = self._make_prompt_hash(request)

        # Try Redis first
        redis_cached = await self._get_from_redis(prompt_hash)
        if redis_cached:
            redis_cached.request_id = request.request_id
            logger.debug(f"[LLM_CACHE] Redis hit for prompt: {prompt_hash[:8]}...")
            return redis_cached

        # Try in-memory cache
        if cache_key in self.cache:
            self.cache_hits += 1
            cached = self.cache[cache_key]
            return LLMResponse(
                text=cached.text,
                tokens_used=cached.tokens_used,
                generation_time_ms=0,
                request_id=request.request_id,
                model=cached.model
            )

        self.cache_misses += 1

        # Generate new response
        response = await self.client.generate(request)

        # Cache in Redis (async, non-blocking)
        asyncio.create_task(self._set_in_redis(prompt_hash, response))

        # Cache in memory
        if len(self.cache) >= self.cache_size:
            first_key = next(iter(self.cache))
            del self.cache[first_key]

        self.cache[cache_key] = response

        return response

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / max(1, total)

        redis_total = self.redis_hits + self.redis_misses
        redis_hit_rate = self.redis_hits / max(1, redis_total)

        return {
            "cache_size": len(self.cache),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": hit_rate,
            "redis_available": self._redis_available,
            "redis_hits": self.redis_hits,
            "redis_misses": self.redis_misses,
            "redis_hit_rate": redis_hit_rate,
            **self.client.get_stats()
        }


# ============================================================================
# RATE-LIMITED LLM CLIENT
# ============================================================================

class RateLimitedLLMClient:
    """
    LLM client with priority-based rate limiting.

    Wraps CachedLLMClient with rate limiting to:
    - Prioritize user interactions over background tasks
    - Ensure fair distribution across bots
    - Prevent LLM backend overload
    """

    def __init__(
        self,
        client: CachedLLMClient,
        rate_limiter=None
    ):
        self.client = client
        self._rate_limiter = rate_limiter

    async def _get_rate_limiter(self):
        """Get or create the rate limiter."""
        if self._rate_limiter is None:
            from mind.core.llm_rate_limiter import get_llm_rate_limiter
            self._rate_limiter = get_llm_rate_limiter()
        return self._rate_limiter

    async def generate(
        self,
        request: LLMRequest,
        use_cache: bool = True,
        timeout: Optional[float] = None
    ) -> LLMResponse:
        """
        Generate with rate limiting based on priority.

        Args:
            request: LLM request with optional priority and bot_id
            use_cache: Whether to use response caching
            timeout: Maximum time to wait for rate limit acquisition

        Returns:
            LLM response

        Raises:
            LLMQueueFullError: If rate limit queue is full
            LLMTimeoutError: If waiting for rate limit times out
        """
        from mind.core.llm_rate_limiter import Priority

        rate_limiter = await self._get_rate_limiter()

        # Determine priority
        priority = Priority(request.priority) if request.priority else Priority.NORMAL

        # Try to acquire rate limit slot
        acquired = await rate_limiter.acquire(
            priority=priority,
            bot_id=request.bot_id,
            timeout=timeout or 30.0,
            request_id=request.request_id
        )

        if not acquired:
            queue_length = rate_limiter.get_queue_length()
            raise LLMQueueFullError(
                queue_length=queue_length,
                max_queue_length=rate_limiter.max_queue_length
            )

        try:
            return await self.client.generate(request, use_cache=use_cache)
        finally:
            rate_limiter.release()

    async def generate_with_priority(
        self,
        request: LLMRequest,
        priority: int,
        use_cache: bool = True,
        timeout: Optional[float] = None
    ) -> LLMResponse:
        """
        Generate with explicit priority.

        Args:
            request: LLM request
            priority: Priority level (use llm_rate_limiter.Priority constants)
            use_cache: Whether to use response caching
            timeout: Maximum time to wait

        Returns:
            LLM response
        """
        # Set priority on request
        request.priority = priority
        return await self.generate(request, use_cache=use_cache, timeout=timeout)

    def get_stats(self) -> Dict[str, Any]:
        """Get combined statistics."""
        stats = self.client.get_stats()
        if self._rate_limiter:
            stats["rate_limiter"] = self._rate_limiter.get_stats()
        return stats


# ============================================================================
# POOLED LLM CLIENT
# ============================================================================

class PooledLLMClient:
    """
    LLM client with connection pooling and automatic failover.

    Features:
    - Uses LLMPool for load balancing across instances
    - Automatic fallback to next instance on failure
    - Health-aware instance selection
    """

    def __init__(self, pool=None):
        """
        Initialize pooled client.

        Args:
            pool: Optional LLMPool instance (lazy loaded if not provided)
        """
        self._pool = pool
        self._fallback_client: Optional[OllamaClient] = None

        # Stats
        self.total_requests = 0
        self.failovers = 0

    async def _get_pool(self):
        """Get or create the LLM pool."""
        if self._pool is None:
            from mind.core.llm_pool import get_llm_pool
            self._pool = await get_llm_pool()
        return self._pool

    async def _get_fallback_client(self) -> OllamaClient:
        """Get fallback client for when pool is unavailable."""
        if self._fallback_client is None:
            self._fallback_client = OllamaClient(
                base_url=settings.OLLAMA_BASE_URL,
                model=settings.OLLAMA_MODEL,
                max_concurrent=settings.LLM_MAX_CONCURRENT_REQUESTS,
                timeout=settings.LLM_REQUEST_TIMEOUT
            )
        return self._fallback_client

    async def generate(
        self,
        request: LLMRequest,
        max_retries: int = 3
    ) -> LLMResponse:
        """
        Generate with automatic failover to next instance.

        Args:
            request: LLM request
            max_retries: Maximum retry attempts

        Returns:
            LLM response
        """
        self.total_requests += 1

        pool = await self._get_pool()
        last_error = None

        for attempt in range(max_retries):
            client = pool.get_next_instance()

            if client is None:
                # No healthy instances, try fallback
                client = await self._get_fallback_client()
                logger.warning("[POOLED_LLM] No healthy instances, using fallback")

            try:
                start_time = time.perf_counter()
                await pool.record_request_start(client)

                result = await client.generate(request)

                response_time = (time.perf_counter() - start_time) * 1000
                await pool.record_request_end(client, True, response_time)

                return result

            except Exception as e:
                last_error = e
                self.failovers += 1
                await pool.record_request_end(client, False, 0)

                logger.warning(
                    f"[POOLED_LLM] Instance failed (attempt {attempt + 1}/{max_retries}): {e}"
                )

                if attempt < max_retries - 1:
                    # Small delay before retry
                    await asyncio.sleep(0.1 * (attempt + 1))

        raise Exception(f"All LLM instances failed: {last_error}")

    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.8,
        max_retries: int = 3
    ) -> LLMResponse:
        """
        Chat with automatic failover.

        Args:
            messages: Chat messages
            max_tokens: Max tokens to generate
            temperature: Sampling temperature
            max_retries: Maximum retry attempts

        Returns:
            LLM response
        """
        pool = await self._get_pool()
        last_error = None

        for attempt in range(max_retries):
            client = pool.get_next_instance()

            if client is None:
                client = await self._get_fallback_client()

            try:
                start_time = time.perf_counter()
                await pool.record_request_start(client)

                result = await client.chat(messages, max_tokens, temperature)

                response_time = (time.perf_counter() - start_time) * 1000
                await pool.record_request_end(client, True, response_time)

                return result

            except Exception as e:
                last_error = e
                self.failovers += 1
                await pool.record_request_end(client, False, 0)

                if attempt < max_retries - 1:
                    await asyncio.sleep(0.1 * (attempt + 1))

        raise Exception(f"All LLM instances failed: {last_error}")

    async def generate_batch(
        self,
        requests: List[LLMRequest]
    ) -> List[LLMResponse]:
        """Generate batch with load distribution across pool."""
        tasks = [self.generate(req) for req in requests]
        return await asyncio.gather(*tasks, return_exceptions=True)

    def get_stats(self) -> Dict[str, Any]:
        """Get pooled client statistics."""
        return {
            "total_requests": self.total_requests,
            "failovers": self.failovers,
            "failover_rate": self.failovers / max(1, self.total_requests)
        }

    async def close(self):
        """Close all clients."""
        if self._fallback_client:
            await self._fallback_client.close()
            self._fallback_client = None


# ============================================================================
# FACTORY
# ============================================================================

_llm_client: Optional[OllamaClient] = None
_cached_client: Optional[CachedLLMClient] = None
_rate_limited_client: Optional[RateLimitedLLMClient] = None
_pooled_client: Optional[PooledLLMClient] = None


async def get_llm_client() -> OllamaClient:
    """Get or create the global LLM client."""
    global _llm_client
    if _llm_client is None:
        _llm_client = OllamaClient(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_MODEL,
            max_concurrent=settings.LLM_MAX_CONCURRENT_REQUESTS,
            timeout=settings.LLM_REQUEST_TIMEOUT
        )
    return _llm_client


async def get_cached_client() -> CachedLLMClient:
    """Get or create the cached LLM client."""
    global _cached_client
    if _cached_client is None:
        base_client = await get_llm_client()
        _cached_client = CachedLLMClient(base_client)
    return _cached_client


async def get_rate_limited_client() -> RateLimitedLLMClient:
    """Get or create the rate-limited LLM client with priority queuing."""
    global _rate_limited_client
    if _rate_limited_client is None:
        cached_client = await get_cached_client()
        _rate_limited_client = RateLimitedLLMClient(cached_client)
    return _rate_limited_client


async def get_pooled_client() -> PooledLLMClient:
    """Get or create the pooled LLM client with load balancing."""
    global _pooled_client
    if _pooled_client is None:
        _pooled_client = PooledLLMClient()
    return _pooled_client


async def close_llm_clients() -> None:
    """Close all LLM clients."""
    global _llm_client, _cached_client, _rate_limited_client, _pooled_client

    if _llm_client:
        await _llm_client.close()
        _llm_client = None

    _rate_limited_client = None

    if _pooled_client:
        await _pooled_client.close()
        _pooled_client = None

    _cached_client = None
