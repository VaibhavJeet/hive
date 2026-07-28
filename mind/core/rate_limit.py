"""
Request rate limiting (HIVE-026).

The previous limiter lived in `main.py` as a `defaultdict(list)` of timestamps keyed by
client IP. Three problems:

1. **Per-process.** With `API_WORKERS=4` each worker kept its own dict, so the effective
   limit was four times the configured one — and which worker you hit decided whether
   you were throttled.
2. **Unbounded.** Entries were pruned only for an IP that made a *new* request, so an
   IP that hit the API once and never returned kept its list forever. A scan or a
   botnet grew the dict without limit.
3. **Reset on restart.** A deploy cleared everyone's budget.

This uses a Redis sorted set per client — a genuine sliding window, shared across
workers, with a TTL so idle keys expire rather than accumulate.

**Redis is not a hard dependency.** If it is unavailable the limiter falls back to the
in-process window, because refusing traffic when the cache is down is a worse failure
than briefly limiting per-worker. The fallback is bounded (see `_LocalWindow`), which
the original was not.
"""

import logging
import time
from collections import OrderedDict
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class _LocalWindow:
    """Bounded in-process fallback.

    An LRU cap is the difference from the original: memory is O(max_clients) rather
    than O(every IP ever seen).
    """

    def __init__(self, max_clients: int = 10_000):
        self.max_clients = max_clients
        self._hits: "OrderedDict[str, list]" = OrderedDict()

    def record(self, key: str, now: float, window_seconds: float) -> int:
        hits = self._hits.get(key)
        if hits is None:
            hits = []
            if len(self._hits) >= self.max_clients:
                self._hits.popitem(last=False)  # evict least-recently-used
        else:
            self._hits.move_to_end(key)

        cutoff = now - window_seconds
        hits = [t for t in hits if t > cutoff]
        hits.append(now)
        self._hits[key] = hits
        return len(hits)

    def count(self, key: str, now: float, window_seconds: float) -> int:
        cutoff = now - window_seconds
        return sum(1 for t in self._hits.get(key, ()) if t > cutoff)


class RateLimiter:
    """Sliding-window rate limiter backed by Redis, with a bounded local fallback."""

    def __init__(
        self,
        requests_per_minute: int = 120,
        burst_limit: int = 20,
        key_prefix: str = "ratelimit",
    ):
        self.requests_per_minute = requests_per_minute
        self.burst_limit = burst_limit
        self.key_prefix = key_prefix
        self._local = _LocalWindow()
        self._redis_unavailable_logged = False

    async def _redis(self):
        try:
            from mind.config.settings import settings

            if not settings.REDIS_ENABLED:
                return None
            from mind.core.redis_client import get_redis_client

            client = await get_redis_client()
            return getattr(client, "client", None) or getattr(client, "_client", None)
        except Exception:
            return None

    async def check(self, identity: str) -> Tuple[bool, Optional[str], int]:
        """Record a request and decide whether it is allowed.

        Returns `(allowed, reason, retry_after_seconds)`.
        """
        now = time.time()
        redis = await self._redis()

        if redis is not None:
            try:
                return await self._check_redis(redis, identity, now)
            except Exception as exc:
                if not self._redis_unavailable_logged:
                    logger.warning(
                        "Rate limiter falling back to in-process counting: %s", exc
                    )
                    self._redis_unavailable_logged = True

        return self._check_local(identity, now)

    async def _check_redis(self, redis, identity: str, now: float):
        minute_key = f"{self.key_prefix}:m:{identity}"
        burst_key = f"{self.key_prefix}:s:{identity}"

        pipe = redis.pipeline()
        # Sliding window: drop anything outside it, add this request, count, re-arm TTL.
        pipe.zremrangebyscore(minute_key, 0, now - 60)
        pipe.zadd(minute_key, {f"{now}": now})
        pipe.zcard(minute_key)
        pipe.expire(minute_key, 120)

        pipe.zremrangebyscore(burst_key, 0, now - 1)
        pipe.zadd(burst_key, {f"{now}": now})
        pipe.zcard(burst_key)
        pipe.expire(burst_key, 5)

        results = await pipe.execute()
        minute_count = results[2]
        burst_count = results[6]

        if burst_count > self.burst_limit:
            return False, "Too many requests. Please slow down.", 1
        if minute_count > self.requests_per_minute:
            return False, "Rate limit exceeded. Please try again later.", 60
        return True, None, 0

    def _check_local(self, identity: str, now: float):
        minute_count = self._local.record(f"m:{identity}", now, 60.0)
        burst_count = self._local.count(f"m:{identity}", now, 1.0)

        if burst_count > self.burst_limit:
            return False, "Too many requests. Please slow down.", 1
        if minute_count > self.requests_per_minute:
            return False, "Rate limit exceeded. Please try again later.", 60
        return True, None, 0
