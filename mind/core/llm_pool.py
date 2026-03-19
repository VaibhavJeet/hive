"""
LLM Pool for AI Community Companions.
Manages multiple Ollama instances with round-robin load balancing and health awareness.
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any

from mind.core.llm_client import OllamaClient, LLMRequest, LLMResponse
from mind.config.settings import settings

logger = logging.getLogger(__name__)


class LoadBalancingStrategy(str, Enum):
    """Load balancing strategies for LLM pool."""
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    RANDOM = "random"


@dataclass
class InstanceHealth:
    """Health status of an Ollama instance."""
    url: str
    is_healthy: bool = True
    last_check: float = 0.0
    consecutive_failures: int = 0
    last_success: float = 0.0
    avg_response_time_ms: float = 0.0
    total_requests: int = 0
    active_requests: int = 0


@dataclass
class PooledInstance:
    """An Ollama instance in the pool."""
    client: OllamaClient
    health: InstanceHealth
    model: str


class LLMPool:
    """
    Manages multiple Ollama instances with load balancing and health awareness.

    Features:
    - Round-robin, least-loaded, and random load balancing
    - Automatic health checking
    - Skip unhealthy instances
    - Auto-recovery when instances come back online
    """

    def __init__(
        self,
        strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN,
        health_check_interval: float = 30.0,
        unhealthy_threshold: int = 3,
        recovery_timeout: float = 60.0
    ):
        """
        Initialize the LLM pool.

        Args:
            strategy: Load balancing strategy to use
            health_check_interval: Seconds between health checks
            unhealthy_threshold: Consecutive failures before marking unhealthy
            recovery_timeout: Seconds to wait before retrying unhealthy instance
        """
        self.instances: Dict[str, PooledInstance] = {}
        self.strategy = strategy
        self.health_check_interval = health_check_interval
        self.unhealthy_threshold = unhealthy_threshold
        self.recovery_timeout = recovery_timeout

        self._round_robin_index = 0
        self._lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None
        self._running = False

    async def add_instance(
        self,
        url: str,
        model: str,
        max_concurrent: int = 8,
        timeout: int = 30
    ) -> bool:
        """
        Add a new Ollama instance to the pool.

        Args:
            url: Base URL of the Ollama instance
            model: Model to use for this instance
            max_concurrent: Max concurrent requests
            timeout: Request timeout in seconds

        Returns:
            True if instance was added successfully
        """
        url = url.rstrip("/")

        async with self._lock:
            if url in self.instances:
                logger.warning(f"[LLM_POOL] Instance {url} already exists")
                return False

            client = OllamaClient(
                base_url=url,
                model=model,
                max_concurrent=max_concurrent,
                timeout=timeout
            )

            # Check initial health
            is_healthy = await client.check_health()

            health = InstanceHealth(
                url=url,
                is_healthy=is_healthy,
                last_check=time.time(),
                last_success=time.time() if is_healthy else 0.0
            )

            self.instances[url] = PooledInstance(
                client=client,
                health=health,
                model=model
            )

            logger.info(f"[LLM_POOL] Added instance {url} (healthy={is_healthy})")
            return True

    async def remove_instance(self, url: str) -> bool:
        """
        Remove an instance from the pool.

        Args:
            url: URL of the instance to remove

        Returns:
            True if instance was removed
        """
        url = url.rstrip("/")

        async with self._lock:
            if url not in self.instances:
                return False

            instance = self.instances.pop(url)
            await instance.client.close()

            logger.info(f"[LLM_POOL] Removed instance {url}")
            return True

    def get_next_instance(self) -> Optional[OllamaClient]:
        """
        Get the next instance using round-robin selection.
        Skips unhealthy instances.

        Returns:
            OllamaClient or None if no healthy instances
        """
        healthy_instances = self._get_healthy_instances()

        if not healthy_instances:
            return None

        if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
            return self._round_robin_select(healthy_instances)
        elif self.strategy == LoadBalancingStrategy.LEAST_LOADED:
            return self._least_loaded_select(healthy_instances)
        elif self.strategy == LoadBalancingStrategy.RANDOM:
            return self._random_select(healthy_instances)
        else:
            return self._round_robin_select(healthy_instances)

    def _get_healthy_instances(self) -> List[PooledInstance]:
        """Get all healthy instances, considering recovery."""
        now = time.time()
        healthy = []

        for instance in self.instances.values():
            health = instance.health

            if health.is_healthy:
                healthy.append(instance)
            elif now - health.last_check >= self.recovery_timeout:
                # Allow recovery attempt
                healthy.append(instance)

        return healthy

    def _round_robin_select(self, instances: List[PooledInstance]) -> Optional[OllamaClient]:
        """Round-robin selection."""
        if not instances:
            return None

        self._round_robin_index = (self._round_robin_index + 1) % len(instances)
        return instances[self._round_robin_index].client

    def _least_loaded_select(self, instances: List[PooledInstance]) -> Optional[OllamaClient]:
        """Select instance with fewest active requests."""
        if not instances:
            return None

        sorted_instances = sorted(
            instances,
            key=lambda i: i.health.active_requests
        )
        return sorted_instances[0].client

    def _random_select(self, instances: List[PooledInstance]) -> Optional[OllamaClient]:
        """Random selection."""
        if not instances:
            return None
        return random.choice(instances).client

    def get_healthiest_instance(self) -> Optional[OllamaClient]:
        """
        Get the healthiest instance based on response time and success rate.

        Returns:
            OllamaClient or None if no healthy instances
        """
        healthy_instances = self._get_healthy_instances()

        if not healthy_instances:
            return None

        # Sort by response time (lower is better)
        sorted_instances = sorted(
            healthy_instances,
            key=lambda i: (
                i.health.consecutive_failures,
                i.health.avg_response_time_ms,
                -i.health.last_success
            )
        )

        return sorted_instances[0].client

    async def health_check_all(self) -> Dict[str, bool]:
        """
        Check health of all instances.

        Returns:
            Dict mapping URL to health status
        """
        results = {}
        now = time.time()

        async def check_instance(url: str, instance: PooledInstance):
            try:
                start = time.perf_counter()
                is_healthy = await instance.client.check_health()
                response_time = (time.perf_counter() - start) * 1000

                health = instance.health
                health.last_check = now

                if is_healthy:
                    health.is_healthy = True
                    health.consecutive_failures = 0
                    health.last_success = now
                    # Exponential moving average for response time
                    if health.avg_response_time_ms == 0:
                        health.avg_response_time_ms = response_time
                    else:
                        health.avg_response_time_ms = (
                            0.8 * health.avg_response_time_ms + 0.2 * response_time
                        )
                    logger.debug(f"[LLM_POOL] {url} healthy ({response_time:.1f}ms)")
                else:
                    health.consecutive_failures += 1
                    if health.consecutive_failures >= self.unhealthy_threshold:
                        health.is_healthy = False
                        logger.warning(f"[LLM_POOL] {url} marked unhealthy")

                results[url] = is_healthy

            except Exception as e:
                instance.health.consecutive_failures += 1
                if instance.health.consecutive_failures >= self.unhealthy_threshold:
                    instance.health.is_healthy = False
                instance.health.last_check = now
                results[url] = False
                logger.error(f"[LLM_POOL] Health check failed for {url}: {e}")

        tasks = [
            check_instance(url, instance)
            for url, instance in self.instances.items()
        ]

        await asyncio.gather(*tasks)
        return results

    async def record_request_start(self, client: OllamaClient) -> None:
        """Record that a request started on a client."""
        for instance in self.instances.values():
            if instance.client is client:
                instance.health.active_requests += 1
                instance.health.total_requests += 1
                break

    async def record_request_end(
        self,
        client: OllamaClient,
        success: bool,
        response_time_ms: float
    ) -> None:
        """Record that a request completed on a client."""
        for instance in self.instances.values():
            if instance.client is client:
                instance.health.active_requests = max(
                    0, instance.health.active_requests - 1
                )

                if success:
                    instance.health.consecutive_failures = 0
                    instance.health.last_success = time.time()
                    # Update moving average
                    if instance.health.avg_response_time_ms == 0:
                        instance.health.avg_response_time_ms = response_time_ms
                    else:
                        instance.health.avg_response_time_ms = (
                            0.8 * instance.health.avg_response_time_ms +
                            0.2 * response_time_ms
                        )
                else:
                    instance.health.consecutive_failures += 1
                    if instance.health.consecutive_failures >= self.unhealthy_threshold:
                        instance.health.is_healthy = False
                break

    async def start_health_checks(self) -> None:
        """Start background health check task."""
        if self._running:
            return

        self._running = True

        async def health_loop():
            while self._running:
                try:
                    await self.health_check_all()
                except Exception as e:
                    logger.error(f"[LLM_POOL] Health check loop error: {e}")
                await asyncio.sleep(self.health_check_interval)

        self._health_check_task = asyncio.create_task(health_loop())
        logger.info("[LLM_POOL] Started health check background task")

    async def stop_health_checks(self) -> None:
        """Stop background health check task."""
        self._running = False

        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None

        logger.info("[LLM_POOL] Stopped health check background task")

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        stats = {
            "total_instances": len(self.instances),
            "healthy_instances": sum(
                1 for i in self.instances.values() if i.health.is_healthy
            ),
            "strategy": self.strategy.value,
            "instances": {}
        }

        for url, instance in self.instances.items():
            stats["instances"][url] = {
                "model": instance.model,
                "is_healthy": instance.health.is_healthy,
                "consecutive_failures": instance.health.consecutive_failures,
                "avg_response_time_ms": round(instance.health.avg_response_time_ms, 2),
                "total_requests": instance.health.total_requests,
                "active_requests": instance.health.active_requests,
                "circuit_breaker": instance.client.circuit_breaker.get_stats()
            }

        return stats

    async def close(self) -> None:
        """Close all instances and cleanup."""
        await self.stop_health_checks()

        for instance in self.instances.values():
            await instance.client.close()

        self.instances.clear()
        logger.info("[LLM_POOL] Pool closed")


# ============================================================================
# FACTORY
# ============================================================================

_llm_pool: Optional[LLMPool] = None


async def get_llm_pool() -> LLMPool:
    """Get or create the global LLM pool."""
    global _llm_pool

    if _llm_pool is None:
        strategy = LoadBalancingStrategy(
            getattr(settings, 'LOAD_BALANCING_STRATEGY', 'round_robin')
        )
        _llm_pool = LLMPool(strategy=strategy)

        # Add instances from settings
        instances = getattr(settings, 'OLLAMA_INSTANCES', settings.OLLAMA_BASE_URL)
        if isinstance(instances, str):
            instances = [url.strip() for url in instances.split(',')]

        for url in instances:
            if url:
                await _llm_pool.add_instance(
                    url=url,
                    model=settings.OLLAMA_MODEL,
                    max_concurrent=settings.LLM_MAX_CONCURRENT_REQUESTS,
                    timeout=settings.LLM_REQUEST_TIMEOUT
                )

        # Start health checks
        await _llm_pool.start_health_checks()

    return _llm_pool


async def close_llm_pool() -> None:
    """Close the global LLM pool."""
    global _llm_pool

    if _llm_pool is not None:
        await _llm_pool.close()
        _llm_pool = None
