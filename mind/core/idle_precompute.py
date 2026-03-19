"""
Idle Precomputation for AI Community Companions.
Precomputes embeddings and responses during low activity periods.
"""

import asyncio
import hashlib
import json
import logging
import psutil
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable, Awaitable
from enum import Enum

from mind.config.settings import settings

logger = logging.getLogger(__name__)


class SystemLoadLevel(str, Enum):
    """System load levels."""
    IDLE = "idle"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class PrecomputeTask:
    """A task to precompute."""
    key: str
    compute_fn: Callable[[], Awaitable[Any]]
    ttl: int = 3600
    priority: int = 0


class IdlePrecomputer:
    """
    Precomputes embeddings and bot responses during idle periods.

    Features:
    - System load detection
    - Precompute embeddings for common texts
    - Precompute bot responses for common scenarios
    - Store in Redis cache
    """

    def __init__(
        self,
        cpu_idle_threshold: float = 30.0,
        memory_idle_threshold: float = 50.0,
        check_interval: float = 30.0,
        max_precompute_per_cycle: int = 10
    ):
        """
        Initialize the idle precomputer.

        Args:
            cpu_idle_threshold: CPU usage % below which system is idle
            memory_idle_threshold: Memory usage % below which system is idle
            check_interval: Seconds between idle checks
            max_precompute_per_cycle: Max items to precompute per cycle
        """
        self.cpu_idle_threshold = cpu_idle_threshold
        self.memory_idle_threshold = memory_idle_threshold
        self.check_interval = check_interval
        self.max_precompute_per_cycle = max_precompute_per_cycle

        self._pending_tasks: List[PrecomputeTask] = []
        self._lock = asyncio.Lock()
        self._precompute_task: Optional[asyncio.Task] = None
        self._running = False

        self._redis_client = None

        # Stats
        self.total_precomputed = 0
        self.cycles_run = 0
        self.last_precompute_time = 0.0

    async def _get_redis(self):
        """Get Redis client."""
        if self._redis_client is None:
            try:
                from mind.core.redis_client import get_redis_client
                self._redis_client = await get_redis_client()
            except Exception as e:
                logger.warning(f"[IDLE_PRECOMPUTE] Redis not available: {e}")
        return self._redis_client

    def get_system_load(self) -> SystemLoadLevel:
        """
        Get current system load level.

        Returns:
            SystemLoadLevel indicating current load
        """
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            if cpu_percent < self.cpu_idle_threshold and memory_percent < self.memory_idle_threshold:
                return SystemLoadLevel.IDLE
            elif cpu_percent < 50 and memory_percent < 70:
                return SystemLoadLevel.LOW
            elif cpu_percent < 80 and memory_percent < 85:
                return SystemLoadLevel.MEDIUM
            else:
                return SystemLoadLevel.HIGH

        except Exception as e:
            logger.debug(f"[IDLE_PRECOMPUTE] System load check failed: {e}")
            return SystemLoadLevel.MEDIUM

    def is_idle(self) -> bool:
        """
        Check if system is currently idle.

        Returns:
            True if system is idle
        """
        return self.get_system_load() == SystemLoadLevel.IDLE

    async def add_task(
        self,
        key: str,
        compute_fn: Callable[[], Awaitable[Any]],
        ttl: int = 3600,
        priority: int = 0
    ) -> None:
        """
        Add a precompute task.

        Args:
            key: Cache key for the result
            compute_fn: Async function that computes the value
            ttl: Cache TTL in seconds
            priority: Higher priority tasks run first
        """
        task = PrecomputeTask(
            key=key,
            compute_fn=compute_fn,
            ttl=ttl,
            priority=priority
        )

        async with self._lock:
            self._pending_tasks.append(task)
            # Sort by priority (higher first)
            self._pending_tasks.sort(key=lambda t: -t.priority)

    async def precompute_embeddings(
        self,
        texts: List[str],
        priority: int = 0
    ) -> None:
        """
        Queue texts for embedding precomputation.

        Args:
            texts: List of texts to embed
            priority: Task priority
        """
        from mind.core.embedding_batch import get_embedding_batcher

        batcher = await get_embedding_batcher()

        for text in texts:
            text_hash = hashlib.sha256(text.encode()).hexdigest()[:32]
            key = f"precompute:embedding:{text_hash}"

            async def compute(t=text):
                return await batcher.get_or_compute(t)

            await self.add_task(
                key=key,
                compute_fn=compute,
                ttl=3600 * 24,  # 24 hours
                priority=priority
            )

    async def precompute_bot_responses(
        self,
        scenarios: List[Dict[str, Any]],
        priority: int = 1
    ) -> None:
        """
        Queue bot response scenarios for precomputation.

        Args:
            scenarios: List of scenario dicts with 'bot_id', 'context', 'prompt'
            priority: Task priority
        """
        from mind.core.llm_client import get_cached_client, LLMRequest

        client = await get_cached_client()

        for scenario in scenarios:
            scenario_hash = hashlib.sha256(
                json.dumps(scenario, sort_keys=True).encode()
            ).hexdigest()[:32]
            key = f"precompute:response:{scenario_hash}"

            async def compute(s=scenario):
                request = LLMRequest(
                    prompt=s.get("prompt", ""),
                    system_prompt=s.get("system_prompt"),
                    max_tokens=s.get("max_tokens", 256),
                    temperature=s.get("temperature", 0.7)
                )
                response = await client.generate(request)
                return response.text

            await self.add_task(
                key=key,
                compute_fn=compute,
                ttl=3600,  # 1 hour
                priority=priority
            )

    async def get_precomputed(self, key: str) -> Optional[Any]:
        """
        Get a precomputed value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        redis = await self._get_redis()
        if redis is None or not redis.is_connected:
            return None

        try:
            cached = await redis.get_json(f"precompute:{key}")
            if cached:
                return cached.get("value")
        except Exception as e:
            logger.debug(f"[IDLE_PRECOMPUTE] Get cached failed: {e}")

        return None

    async def _store_precomputed(
        self,
        key: str,
        value: Any,
        ttl: int
    ) -> bool:
        """Store a precomputed value in Redis."""
        redis = await self._get_redis()
        if redis is None or not redis.is_connected:
            return False

        try:
            data = {
                "value": value,
                "computed_at": time.time()
            }
            return await redis.set_json(key, data, ttl=ttl)
        except Exception as e:
            logger.debug(f"[IDLE_PRECOMPUTE] Store failed: {e}")
            return False

    async def _run_precompute_cycle(self) -> int:
        """
        Run one precompute cycle.

        Returns:
            Number of items precomputed
        """
        if not self.is_idle():
            return 0

        async with self._lock:
            tasks = self._pending_tasks[:self.max_precompute_per_cycle]
            self._pending_tasks = self._pending_tasks[self.max_precompute_per_cycle:]

        if not tasks:
            return 0

        count = 0
        for task in tasks:
            # Check if still idle
            if not self.is_idle():
                # Re-queue remaining tasks
                async with self._lock:
                    self._pending_tasks = [task] + [
                        t for t in tasks if t != task
                    ] + self._pending_tasks
                break

            try:
                value = await task.compute_fn()
                await self._store_precomputed(task.key, value, task.ttl)
                count += 1
                self.total_precomputed += 1
                logger.debug(f"[IDLE_PRECOMPUTE] Precomputed: {task.key}")

            except Exception as e:
                logger.warning(f"[IDLE_PRECOMPUTE] Task {task.key} failed: {e}")

        self.last_precompute_time = time.time()
        return count

    async def start(self) -> None:
        """Start the idle precomputation loop."""
        if self._running:
            return

        self._running = True

        async def precompute_loop():
            while self._running:
                try:
                    if self.is_idle() and self._pending_tasks:
                        count = await self._run_precompute_cycle()
                        if count > 0:
                            self.cycles_run += 1
                            logger.info(
                                f"[IDLE_PRECOMPUTE] Cycle complete: "
                                f"{count} items precomputed"
                            )
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"[IDLE_PRECOMPUTE] Loop error: {e}")

                await asyncio.sleep(self.check_interval)

        self._precompute_task = asyncio.create_task(precompute_loop())
        logger.info("[IDLE_PRECOMPUTE] Started idle precomputation")

    async def stop(self) -> None:
        """Stop the idle precomputation loop."""
        self._running = False

        if self._precompute_task:
            self._precompute_task.cancel()
            try:
                await self._precompute_task
            except asyncio.CancelledError:
                pass
            self._precompute_task = None

        logger.info("[IDLE_PRECOMPUTE] Stopped")

    def get_stats(self) -> Dict[str, Any]:
        """Get precomputer statistics."""
        return {
            "is_idle": self.is_idle(),
            "system_load": self.get_system_load().value,
            "pending_tasks": len(self._pending_tasks),
            "total_precomputed": self.total_precomputed,
            "cycles_run": self.cycles_run,
            "last_precompute_time": self.last_precompute_time,
            "running": self._running
        }


# ============================================================================
# FACTORY
# ============================================================================

_idle_precomputer: Optional[IdlePrecomputer] = None


async def get_idle_precomputer() -> IdlePrecomputer:
    """Get or create the global idle precomputer."""
    global _idle_precomputer

    if _idle_precomputer is None:
        _idle_precomputer = IdlePrecomputer()
        await _idle_precomputer.start()

    return _idle_precomputer


async def close_idle_precomputer() -> None:
    """Close the global idle precomputer."""
    global _idle_precomputer

    if _idle_precomputer is not None:
        await _idle_precomputer.stop()
        _idle_precomputer = None
