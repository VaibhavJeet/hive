"""
LLM Rate Limiter for AI Community Companions.

Provides priority-based rate limiting for LLM requests using
token bucket algorithm with per-bot and global limits.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, Optional, Any
from uuid import UUID
import heapq


logger = logging.getLogger(__name__)


class Priority(IntEnum):
    """
    Priority levels for LLM requests.

    Higher priority requests are processed first.
    """
    LOW = 1       # Background tasks (thoughts, passive behaviors)
    NORMAL = 5    # Bot-initiated actions (posts, comments)
    HIGH = 10     # User interactions (chat responses, DMs)
    CRITICAL = 20 # System operations (health checks)


@dataclass(order=True)
class QueuedRequest:
    """A request waiting in the priority queue."""
    priority: int
    timestamp: float = field(compare=False)
    request_id: str = field(compare=False)
    bot_id: Optional[UUID] = field(compare=False, default=None)
    event: asyncio.Event = field(compare=False, default_factory=asyncio.Event)

    def __post_init__(self):
        # Negate priority for max-heap behavior (highest priority first)
        self.priority = -self.priority


class TokenBucket:
    """
    Token bucket rate limiter.

    Allows smooth rate limiting with burst capacity.
    """

    def __init__(
        self,
        tokens_per_second: float,
        max_tokens: float,
        initial_tokens: Optional[float] = None
    ):
        self.tokens_per_second = tokens_per_second
        self.max_tokens = max_tokens
        self.tokens = initial_tokens if initial_tokens is not None else max_tokens
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> bool:
        """
        Try to acquire tokens.

        Returns True if tokens were acquired, False otherwise.
        """
        async with self._lock:
            self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    async def wait_and_acquire(self, tokens: float = 1.0, timeout: Optional[float] = None) -> bool:
        """
        Wait for tokens to become available and acquire them.

        Returns True if acquired within timeout, False otherwise.
        """
        start_time = time.monotonic()

        while True:
            if await self.acquire(tokens):
                return True

            # Calculate wait time for tokens
            async with self._lock:
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.tokens_per_second

            # Check timeout
            if timeout is not None:
                elapsed = time.monotonic() - start_time
                if elapsed + wait_time > timeout:
                    return False
                wait_time = min(wait_time, timeout - elapsed)

            await asyncio.sleep(min(wait_time, 0.1))

    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_update
        self.last_update = now

        self.tokens = min(
            self.max_tokens,
            self.tokens + elapsed * self.tokens_per_second
        )

    @property
    def available_tokens(self) -> float:
        """Get current available tokens (without modifying state)."""
        elapsed = time.monotonic() - self.last_update
        return min(
            self.max_tokens,
            self.tokens + elapsed * self.tokens_per_second
        )

    def get_wait_time(self, tokens: float = 1.0) -> float:
        """Calculate wait time for specified tokens."""
        available = self.available_tokens
        if available >= tokens:
            return 0.0
        tokens_needed = tokens - available
        return tokens_needed / self.tokens_per_second


class LLMRateLimiter:
    """
    Advanced rate limiter for LLM requests with priority queuing.

    Features:
    - Priority queue (HIGH > NORMAL > LOW)
    - Token bucket algorithm for smooth rate limiting
    - Per-bot limits to ensure fair distribution
    - Global limits to protect the LLM backend
    - Queue management to prevent memory issues
    """

    def __init__(
        self,
        global_requests_per_minute: int = 60,
        global_burst_size: int = 10,
        per_bot_requests_per_minute: int = 10,
        per_bot_burst_size: int = 3,
        max_queue_length: int = 100,
        high_priority_reservation: float = 0.3  # Reserve 30% for high priority
    ):
        # Global rate limiting
        self.global_bucket = TokenBucket(
            tokens_per_second=global_requests_per_minute / 60.0,
            max_tokens=global_burst_size
        )

        # Per-bot rate limiting
        self.per_bot_limits = per_bot_requests_per_minute
        self.per_bot_burst = per_bot_burst_size
        self.bot_buckets: Dict[UUID, TokenBucket] = {}

        # Priority queue
        self.queue: list = []
        self.max_queue_length = max_queue_length
        self.high_priority_reservation = high_priority_reservation

        # Stats
        self.total_requests = 0
        self.total_acquired = 0
        self.total_rejected = 0
        self.requests_by_priority: Dict[Priority, int] = {p: 0 for p in Priority}

        # Lock for thread safety
        self._lock = asyncio.Lock()
        self._processing = False

    def _get_bot_bucket(self, bot_id: UUID) -> TokenBucket:
        """Get or create token bucket for a bot."""
        if bot_id not in self.bot_buckets:
            self.bot_buckets[bot_id] = TokenBucket(
                tokens_per_second=self.per_bot_limits / 60.0,
                max_tokens=self.per_bot_burst
            )
        return self.bot_buckets[bot_id]

    async def acquire(
        self,
        priority: Priority = Priority.NORMAL,
        bot_id: Optional[UUID] = None,
        timeout: Optional[float] = None,
        request_id: Optional[str] = None
    ) -> bool:
        """
        Acquire permission to make an LLM request.

        Args:
            priority: Request priority level
            bot_id: Bot making the request (for per-bot limits)
            timeout: Maximum time to wait for permission
            request_id: Optional identifier for tracking

        Returns:
            True if permission granted, False otherwise
        """
        self.total_requests += 1
        self.requests_by_priority[priority] += 1

        async with self._lock:
            # Check queue length limits
            if len(self.queue) >= self.max_queue_length:
                # Only reject low priority when queue is full
                if priority <= Priority.NORMAL:
                    self.total_rejected += 1
                    logger.warning(
                        f"[RATE_LIMIT] Queue full ({len(self.queue)}), "
                        f"rejecting {priority.name} request"
                    )
                    return False

        # Try immediate acquisition for high priority
        if priority >= Priority.HIGH:
            # Reserve capacity for high priority
            if await self._try_acquire_immediate(bot_id):
                self.total_acquired += 1
                logger.debug(
                    f"[RATE_LIMIT] Immediate acquisition for {priority.name} "
                    f"(bot: {bot_id})"
                )
                return True

        # Create queued request
        request = QueuedRequest(
            priority=priority,
            timestamp=time.monotonic(),
            request_id=request_id or f"req_{self.total_requests}",
            bot_id=bot_id
        )

        async with self._lock:
            heapq.heappush(self.queue, request)

        # Wait for acquisition
        try:
            if timeout:
                await asyncio.wait_for(
                    self._wait_for_acquisition(request),
                    timeout=timeout
                )
            else:
                await self._wait_for_acquisition(request)

            self.total_acquired += 1
            return True

        except asyncio.TimeoutError:
            # Remove from queue on timeout
            async with self._lock:
                try:
                    self.queue.remove(request)
                    heapq.heapify(self.queue)
                except ValueError:
                    pass
            self.total_rejected += 1
            return False

    async def _try_acquire_immediate(self, bot_id: Optional[UUID]) -> bool:
        """Try to acquire without queuing."""
        # Check global limit
        if not await self.global_bucket.acquire():
            return False

        # Check per-bot limit
        if bot_id:
            bot_bucket = self._get_bot_bucket(bot_id)
            if not await bot_bucket.acquire():
                # Return the global token since we can't use it
                self.global_bucket.tokens = min(
                    self.global_bucket.max_tokens,
                    self.global_bucket.tokens + 1
                )
                return False

        return True

    async def _wait_for_acquisition(self, request: QueuedRequest):
        """Wait for a queued request to be processed."""
        # Start processing if not already running
        if not self._processing:
            asyncio.create_task(self._process_queue())

        # Wait for our turn
        await request.event.wait()

    async def _process_queue(self):
        """Process the priority queue."""
        self._processing = True

        try:
            while True:
                async with self._lock:
                    if not self.queue:
                        break

                    # Get highest priority request
                    request = heapq.heappop(self.queue)

                # Wait for global capacity
                await self.global_bucket.wait_and_acquire()

                # Wait for per-bot capacity if applicable
                if request.bot_id:
                    bot_bucket = self._get_bot_bucket(request.bot_id)
                    await bot_bucket.wait_and_acquire()

                # Signal the request can proceed
                request.event.set()

                # Small delay to prevent tight loops
                await asyncio.sleep(0.01)

        finally:
            self._processing = False

    def release(self):
        """
        Release a held request slot.

        Note: With token bucket, release is automatic over time.
        This method is kept for interface compatibility.
        """
        pass

    def get_queue_length(self) -> int:
        """Get current queue length."""
        return len(self.queue)

    def get_wait_time(self, priority: Priority = Priority.NORMAL) -> float:
        """
        Estimate wait time for a new request with given priority.

        Returns approximate wait time in seconds.
        """
        # Base wait from global bucket
        base_wait = self.global_bucket.get_wait_time()

        # Add queue processing time estimate
        queue_length = self.get_queue_length()

        # Count higher priority items
        higher_priority_count = sum(
            1 for req in self.queue
            if -req.priority > priority  # Remember priority is negated
        )

        # Estimate: each request takes ~1/rate seconds
        queue_wait = higher_priority_count / self.global_bucket.tokens_per_second

        return base_wait + queue_wait

    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        return {
            "total_requests": self.total_requests,
            "total_acquired": self.total_acquired,
            "total_rejected": self.total_rejected,
            "acceptance_rate": self.total_acquired / max(1, self.total_requests),
            "queue_length": len(self.queue),
            "max_queue_length": self.max_queue_length,
            "requests_by_priority": {
                p.name: count for p, count in self.requests_by_priority.items()
            },
            "global_tokens_available": self.global_bucket.available_tokens,
            "active_bots": len(self.bot_buckets)
        }

    async def cleanup_idle_buckets(self, idle_threshold: float = 300.0):
        """Remove bot buckets that have been idle."""
        now = time.monotonic()
        to_remove = []

        for bot_id, bucket in self.bot_buckets.items():
            if now - bucket.last_update > idle_threshold:
                to_remove.append(bot_id)

        for bot_id in to_remove:
            del self.bot_buckets[bot_id]

        if to_remove:
            logger.debug(f"[RATE_LIMIT] Cleaned up {len(to_remove)} idle bot buckets")


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_llm_rate_limiter: Optional[LLMRateLimiter] = None


def get_llm_rate_limiter() -> LLMRateLimiter:
    """Get or create the global LLM rate limiter."""
    global _llm_rate_limiter
    if _llm_rate_limiter is None:
        from mind.config.settings import settings
        _llm_rate_limiter = LLMRateLimiter(
            global_requests_per_minute=settings.LLM_MAX_CONCURRENT_REQUESTS * 10,
            global_burst_size=settings.LLM_MAX_CONCURRENT_REQUESTS,
            per_bot_requests_per_minute=10,
            per_bot_burst_size=3,
            max_queue_length=200
        )
    return _llm_rate_limiter
