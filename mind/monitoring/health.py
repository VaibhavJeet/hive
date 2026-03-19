"""
Health checking system for AI Community Companions.
Provides comprehensive health status for all system components.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

import httpx
from sqlalchemy import text

from mind.config.settings import settings


class HealthState(str, Enum):
    """Health state enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthStatus:
    """Health status for a single component."""
    name: str
    status: HealthState
    latency_ms: float
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "latency_ms": round(self.latency_ms, 2),
            "message": self.message,
            "details": self.details,
        }


@dataclass
class SystemHealth:
    """Overall system health status."""
    status: HealthState
    timestamp: str
    checks: List[HealthStatus]
    version: str = "1.0.0"

    @property
    def is_healthy(self) -> bool:
        """Check if system is fully healthy."""
        return self.status == HealthState.HEALTHY

    @property
    def is_ready(self) -> bool:
        """Check if system is ready to serve requests."""
        return self.status in (HealthState.HEALTHY, HealthState.DEGRADED)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "timestamp": self.timestamp,
            "version": self.version,
            "checks": [check.to_dict() for check in self.checks],
            "summary": {
                "total": len(self.checks),
                "healthy": sum(1 for c in self.checks if c.status == HealthState.HEALTHY),
                "degraded": sum(1 for c in self.checks if c.status == HealthState.DEGRADED),
                "unhealthy": sum(1 for c in self.checks if c.status == HealthState.UNHEALTHY),
            },
        }


class HealthChecker:
    """Health checker for all system components."""

    def __init__(self, timeout: float = 5.0):
        """
        Initialize health checker.

        Args:
            timeout: Timeout in seconds for health checks
        """
        self.timeout = timeout

    async def check_database(self) -> HealthStatus:
        """
        Check database connectivity and health.

        Returns:
            HealthStatus for the database
        """
        start_time = time.perf_counter()
        try:
            from mind.core.database import async_session_factory

            async with async_session_factory() as session:
                # Execute a simple query to verify connectivity
                result = await asyncio.wait_for(
                    session.execute(text("SELECT 1")),
                    timeout=self.timeout,
                )
                result.scalar()

            latency = (time.perf_counter() - start_time) * 1000

            # Consider slow database as degraded
            if latency > 1000:
                return HealthStatus(
                    name="database",
                    status=HealthState.DEGRADED,
                    latency_ms=latency,
                    message="Database responding slowly",
                )

            return HealthStatus(
                name="database",
                status=HealthState.HEALTHY,
                latency_ms=latency,
                message="Database connection successful",
            )
        except asyncio.TimeoutError:
            latency = (time.perf_counter() - start_time) * 1000
            return HealthStatus(
                name="database",
                status=HealthState.UNHEALTHY,
                latency_ms=latency,
                message="Database connection timed out",
            )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            return HealthStatus(
                name="database",
                status=HealthState.UNHEALTHY,
                latency_ms=latency,
                message=f"Database error: {str(e)}",
            )

    async def check_redis(self) -> HealthStatus:
        """
        Check Redis connectivity and health.

        Returns:
            HealthStatus for Redis
        """
        start_time = time.perf_counter()
        try:
            import redis.asyncio as redis

            client = redis.from_url(settings.REDIS_URL)
            try:
                # Ping Redis
                await asyncio.wait_for(client.ping(), timeout=self.timeout)

                # Get some info for details
                info = await asyncio.wait_for(client.info("memory"), timeout=self.timeout)

                latency = (time.perf_counter() - start_time) * 1000

                return HealthStatus(
                    name="redis",
                    status=HealthState.HEALTHY,
                    latency_ms=latency,
                    message="Redis connection successful",
                    details={
                        "used_memory": info.get("used_memory_human", "unknown"),
                    },
                )
            finally:
                await client.close()
        except asyncio.TimeoutError:
            latency = (time.perf_counter() - start_time) * 1000
            return HealthStatus(
                name="redis",
                status=HealthState.UNHEALTHY,
                latency_ms=latency,
                message="Redis connection timed out",
            )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            # Redis might be optional, so treat connection errors as degraded
            return HealthStatus(
                name="redis",
                status=HealthState.DEGRADED,
                latency_ms=latency,
                message=f"Redis unavailable: {str(e)}",
            )

    async def check_ollama(self) -> HealthStatus:
        """
        Check Ollama LLM service health.

        Returns:
            HealthStatus for Ollama
        """
        start_time = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")

                latency = (time.perf_counter() - start_time) * 1000

                if response.status_code == 200:
                    data = response.json()
                    models = data.get("models", [])
                    model_names = [m.get("name", "") for m in models]

                    # Check if our configured model is available
                    has_model = any(
                        settings.OLLAMA_MODEL in name
                        for name in model_names
                    )

                    return HealthStatus(
                        name="ollama",
                        status=HealthState.HEALTHY if has_model else HealthState.DEGRADED,
                        latency_ms=latency,
                        message="Ollama service available" if has_model else f"Model {settings.OLLAMA_MODEL} not found",
                        details={
                            "available_models": model_names[:10],  # Limit to first 10
                            "configured_model": settings.OLLAMA_MODEL,
                        },
                    )
                else:
                    return HealthStatus(
                        name="ollama",
                        status=HealthState.UNHEALTHY,
                        latency_ms=latency,
                        message=f"Ollama returned status {response.status_code}",
                    )
        except asyncio.TimeoutError:
            latency = (time.perf_counter() - start_time) * 1000
            return HealthStatus(
                name="ollama",
                status=HealthState.UNHEALTHY,
                latency_ms=latency,
                message="Ollama connection timed out",
            )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            return HealthStatus(
                name="ollama",
                status=HealthState.UNHEALTHY,
                latency_ms=latency,
                message=f"Ollama error: {str(e)}",
            )

    async def check_websockets(self) -> HealthStatus:
        """
        Check WebSocket manager health.

        Returns:
            HealthStatus for WebSocket connections
        """
        start_time = time.perf_counter()
        try:
            # Import here to avoid circular imports
            from mind.api.main import manager

            connection_count = len(manager.active_connections)
            latency = (time.perf_counter() - start_time) * 1000

            return HealthStatus(
                name="websockets",
                status=HealthState.HEALTHY,
                latency_ms=latency,
                message=f"{connection_count} active connections",
                details={
                    "active_connections": connection_count,
                },
            )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            return HealthStatus(
                name="websockets",
                status=HealthState.DEGRADED,
                latency_ms=latency,
                message=f"WebSocket check failed: {str(e)}",
            )

    async def check_llm_pool(self) -> HealthStatus:
        """
        Check LLM pool health across all Ollama instances.

        Returns:
            HealthStatus for LLM pool
        """
        start_time = time.perf_counter()
        try:
            from mind.core.llm_pool import get_llm_pool

            pool = await get_llm_pool()
            health_results = await pool.health_check_all()

            latency = (time.perf_counter() - start_time) * 1000

            total_instances = len(health_results)
            healthy_instances = sum(1 for h in health_results.values() if h)

            if total_instances == 0:
                return HealthStatus(
                    name="llm_pool",
                    status=HealthState.UNHEALTHY,
                    latency_ms=latency,
                    message="No LLM instances configured",
                    details={
                        "total_instances": 0,
                        "healthy_instances": 0,
                    },
                )

            pool_stats = pool.get_stats()

            if healthy_instances == 0:
                status = HealthState.UNHEALTHY
                message = "All LLM instances unhealthy"
            elif healthy_instances < total_instances:
                status = HealthState.DEGRADED
                message = f"{healthy_instances}/{total_instances} LLM instances healthy"
            else:
                status = HealthState.HEALTHY
                message = f"All {total_instances} LLM instances healthy"

            return HealthStatus(
                name="llm_pool",
                status=status,
                latency_ms=latency,
                message=message,
                details={
                    "total_instances": total_instances,
                    "healthy_instances": healthy_instances,
                    "strategy": pool_stats.get("strategy", "unknown"),
                    "instances": {
                        url: {"healthy": h}
                        for url, h in health_results.items()
                    },
                },
            )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            return HealthStatus(
                name="llm_pool",
                status=HealthState.DEGRADED,
                latency_ms=latency,
                message=f"LLM pool check failed: {str(e)}",
            )

    async def check_embedding_batcher(self) -> HealthStatus:
        """
        Check embedding batcher health.

        Returns:
            HealthStatus for embedding batcher
        """
        start_time = time.perf_counter()
        try:
            from mind.core.embedding_batch import get_embedding_batcher

            batcher = await get_embedding_batcher()
            stats = batcher.get_stats()

            latency = (time.perf_counter() - start_time) * 1000

            return HealthStatus(
                name="embedding_batcher",
                status=HealthState.HEALTHY,
                latency_ms=latency,
                message=f"Queue size: {stats['queue_size']}, Cache hit rate: {stats['cache_hit_rate']:.2%}",
                details=stats,
            )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            return HealthStatus(
                name="embedding_batcher",
                status=HealthState.DEGRADED,
                latency_ms=latency,
                message=f"Embedding batcher check failed: {str(e)}",
            )

    async def get_system_health(self, include_extended: bool = True) -> SystemHealth:
        """
        Get comprehensive system health status.

        Args:
            include_extended: Include LLM pool and embedding batcher checks

        Returns:
            SystemHealth with all component checks
        """
        # Core checks (always run)
        core_checks = [
            self.check_database(),
            self.check_redis(),
            self.check_ollama(),
            self.check_websockets(),
        ]
        check_names = ["database", "redis", "ollama", "websockets"]

        # Extended checks (LLM pool, embedding batcher)
        if include_extended:
            core_checks.extend([
                self.check_llm_pool(),
                self.check_embedding_batcher(),
            ])
            check_names.extend(["llm_pool", "embedding_batcher"])

        # Run all checks concurrently
        checks = await asyncio.gather(*core_checks, return_exceptions=True)

        # Handle any exceptions from gather
        health_checks: List[HealthStatus] = []
        for i, check in enumerate(checks):
            if isinstance(check, Exception):
                health_checks.append(HealthStatus(
                    name=check_names[i],
                    status=HealthState.UNHEALTHY,
                    latency_ms=0,
                    message=f"Check failed: {str(check)}",
                ))
            else:
                health_checks.append(check)

        # Determine overall status
        unhealthy_count = sum(
            1 for c in health_checks if c.status == HealthState.UNHEALTHY
        )
        degraded_count = sum(
            1 for c in health_checks if c.status == HealthState.DEGRADED
        )

        # Database and Ollama/LLM pool are critical
        critical_unhealthy = any(
            c.status == HealthState.UNHEALTHY
            for c in health_checks
            if c.name in ("database", "ollama", "llm_pool")
        )

        if critical_unhealthy or unhealthy_count >= 2:
            overall_status = HealthState.UNHEALTHY
        elif degraded_count > 0 or unhealthy_count > 0:
            overall_status = HealthState.DEGRADED
        else:
            overall_status = HealthState.HEALTHY

        return SystemHealth(
            status=overall_status,
            timestamp=datetime.utcnow().isoformat(),
            checks=health_checks,
        )


# Singleton instance
_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """
    Get the singleton health checker instance.

    Returns:
        HealthChecker instance
    """
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker(timeout=settings.HEALTH_CHECK_TIMEOUT)
    return _health_checker
