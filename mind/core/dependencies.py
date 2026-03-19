"""
Dependency Injection Core for AI Community Companions.
Provides dependency providers for database session, LLM client, cache, and memory.
"""

import asyncio
import logging
from typing import Any, AsyncGenerator, Callable, Dict, Optional, TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from mind.config.settings import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DependencyProvider:
    """
    Base class for dependency providers.
    Supports lazy initialization and lifecycle management.
    """

    def __init__(self, factory: Callable[..., Any], singleton: bool = False):
        self._factory = factory
        self._singleton = singleton
        self._instance: Optional[Any] = None
        self._lock = asyncio.Lock()

    async def get(self) -> Any:
        """Get the dependency instance."""
        if self._singleton:
            if self._instance is None:
                async with self._lock:
                    if self._instance is None:
                        self._instance = await self._resolve()
            return self._instance
        return await self._resolve()

    async def _resolve(self) -> Any:
        """Resolve the dependency."""
        result = self._factory()
        if asyncio.iscoroutine(result):
            result = await result
        return result

    async def dispose(self):
        """Dispose of the singleton instance if any."""
        if self._instance is not None:
            if hasattr(self._instance, 'close'):
                close_result = self._instance.close()
                if asyncio.iscoroutine(close_result):
                    await close_result
            self._instance = None


# ============================================================================
# DATABASE SESSION PROVIDER
# ============================================================================

class DatabaseSessionProvider:
    """
    Provider for async database sessions.
    Supports request-scoped sessions with proper cleanup.
    """

    def __init__(self):
        from mind.core.database import async_session_factory
        self._session_factory = async_session_factory

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a request-scoped database session.
        Yields the session and ensures cleanup.
        """
        async with self._session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

    def create_session(self) -> AsyncSession:
        """Create a new session (caller is responsible for cleanup)."""
        return self._session_factory()


# ============================================================================
# LLM CLIENT PROVIDER
# ============================================================================

class LLMClientProvider:
    """
    Provider for LLM client instances.
    Singleton pattern for connection reuse.
    """

    def __init__(self):
        self._client = None
        self._cached_client = None
        self._lock = asyncio.Lock()

    async def get_client(self):
        """Get the base LLM client (singleton)."""
        if self._client is None:
            async with self._lock:
                if self._client is None:
                    from mind.core.llm_client import get_llm_client
                    self._client = await get_llm_client()
        return self._client

    async def get_cached_client(self):
        """Get the cached LLM client (singleton)."""
        if self._cached_client is None:
            async with self._lock:
                if self._cached_client is None:
                    from mind.core.llm_client import get_cached_client
                    self._cached_client = await get_cached_client()
        return self._cached_client

    async def dispose(self):
        """Dispose of all client instances."""
        if self._client is not None:
            await self._client.close()
            self._client = None
        if self._cached_client is not None:
            await self._cached_client.client.close()
            self._cached_client = None


# ============================================================================
# CACHE PROVIDER
# ============================================================================

class CacheProvider:
    """
    Provider for cache service instances.
    Singleton pattern with fallback to in-memory cache.
    """

    def __init__(self):
        self._cache_service = None
        self._lock = asyncio.Lock()

    async def get_cache(self):
        """Get the cache service (singleton)."""
        if self._cache_service is None:
            async with self._lock:
                if self._cache_service is None:
                    from mind.core.cache import get_cache_service
                    self._cache_service = await get_cache_service()
        return self._cache_service

    async def dispose(self):
        """Dispose of cache resources."""
        self._cache_service = None


# ============================================================================
# MEMORY PROVIDER
# ============================================================================

class MemoryProvider:
    """
    Provider for memory core instances.
    Singleton pattern for shared memory state.
    """

    def __init__(self):
        self._memory_core = None
        self._relationship_memory = None
        self._lock = asyncio.Lock()

    async def get_memory_core(self):
        """Get the memory core (singleton)."""
        if self._memory_core is None:
            async with self._lock:
                if self._memory_core is None:
                    from mind.memory.memory_core import get_memory_core
                    self._memory_core = await get_memory_core()
        return self._memory_core

    async def get_relationship_memory(self):
        """Get the relationship memory (singleton)."""
        if self._relationship_memory is None:
            async with self._lock:
                if self._relationship_memory is None:
                    from mind.memory.memory_core import RelationshipMemory
                    self._relationship_memory = RelationshipMemory()
        return self._relationship_memory

    async def dispose(self):
        """Dispose of memory resources."""
        self._memory_core = None
        self._relationship_memory = None


# ============================================================================
# ACTIVITY ENGINE PROVIDER
# ============================================================================

class ActivityEngineProvider:
    """
    Provider for activity engine instances.
    Singleton pattern for the main engine.
    """

    def __init__(self):
        self._engine = None
        self._lock = asyncio.Lock()

    async def get_engine(self):
        """Get the activity engine (singleton)."""
        if self._engine is None:
            async with self._lock:
                if self._engine is None:
                    from mind.engine.activity_engine import get_activity_engine
                    self._engine = await get_activity_engine()
        return self._engine

    async def dispose(self):
        """Dispose of engine resources."""
        if self._engine is not None:
            await self._engine.stop()
            self._engine = None


# ============================================================================
# GLOBAL PROVIDER INSTANCES
# ============================================================================

# Singleton providers
_db_provider: Optional[DatabaseSessionProvider] = None
_llm_provider: Optional[LLMClientProvider] = None
_cache_provider: Optional[CacheProvider] = None
_memory_provider: Optional[MemoryProvider] = None
_activity_provider: Optional[ActivityEngineProvider] = None


def get_db_provider() -> DatabaseSessionProvider:
    """Get the global database session provider."""
    global _db_provider
    if _db_provider is None:
        _db_provider = DatabaseSessionProvider()
    return _db_provider


def get_llm_provider() -> LLMClientProvider:
    """Get the global LLM client provider."""
    global _llm_provider
    if _llm_provider is None:
        _llm_provider = LLMClientProvider()
    return _llm_provider


def get_cache_provider() -> CacheProvider:
    """Get the global cache provider."""
    global _cache_provider
    if _cache_provider is None:
        _cache_provider = CacheProvider()
    return _cache_provider


def get_memory_provider() -> MemoryProvider:
    """Get the global memory provider."""
    global _memory_provider
    if _memory_provider is None:
        _memory_provider = MemoryProvider()
    return _memory_provider


def get_activity_provider() -> ActivityEngineProvider:
    """Get the global activity engine provider."""
    global _activity_provider
    if _activity_provider is None:
        _activity_provider = ActivityEngineProvider()
    return _activity_provider


async def dispose_all_providers():
    """Dispose of all global provider instances."""
    global _db_provider, _llm_provider, _cache_provider, _memory_provider, _activity_provider

    if _activity_provider is not None:
        await _activity_provider.dispose()
        _activity_provider = None

    if _memory_provider is not None:
        await _memory_provider.dispose()
        _memory_provider = None

    if _cache_provider is not None:
        await _cache_provider.dispose()
        _cache_provider = None

    if _llm_provider is not None:
        await _llm_provider.dispose()
        _llm_provider = None

    _db_provider = None

    logger.info("All dependency providers disposed")
