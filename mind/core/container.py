"""
Dependency Container for AI Community Companions.
Provides a central registry for dependencies with scoped lifetimes.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar
from uuid import uuid4

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Lifetime(Enum):
    """Dependency lifetime scopes."""
    SINGLETON = "singleton"  # Single instance for entire application
    SCOPED = "scoped"        # Single instance per request/scope
    TRANSIENT = "transient"  # New instance every time


class DependencyRegistration:
    """Registration information for a dependency."""

    def __init__(
        self,
        name: str,
        factory: Callable[..., Any],
        lifetime: Lifetime = Lifetime.TRANSIENT,
        is_async: bool = False
    ):
        self.name = name
        self.factory = factory
        self.lifetime = lifetime
        self.is_async = is_async


class DependencyContainer:
    """
    Dependency injection container.

    Supports:
    - Singleton: One instance for the entire application
    - Scoped: One instance per scope (e.g., request)
    - Transient: New instance every resolution

    Usage:
        container = DependencyContainer()
        container.register("db_session", factory=get_session, lifetime=Lifetime.SCOPED)
        container.register("llm_client", factory=get_cached_client, lifetime=Lifetime.SINGLETON)

        async with container.create_scope() as scope:
            session = await scope.resolve("db_session")
            client = await scope.resolve("llm_client")
    """

    def __init__(self):
        self._registrations: Dict[str, DependencyRegistration] = {}
        self._singletons: Dict[str, Any] = {}
        self._singleton_lock = asyncio.Lock()

    def register(
        self,
        name: str,
        factory: Callable[..., Any],
        lifetime: Lifetime = Lifetime.TRANSIENT,
        is_async: bool = False
    ):
        """
        Register a dependency.

        Args:
            name: Unique name for the dependency
            factory: Factory function to create instances
            lifetime: Lifetime scope (SINGLETON, SCOPED, TRANSIENT)
            is_async: Whether the factory is async
        """
        self._registrations[name] = DependencyRegistration(
            name=name,
            factory=factory,
            lifetime=lifetime,
            is_async=is_async
        )
        logger.debug(f"Registered dependency: {name} (lifetime={lifetime.value})")

    def register_instance(self, name: str, instance: Any):
        """
        Register an existing instance as a singleton.

        Args:
            name: Unique name for the dependency
            instance: Existing instance to register
        """
        self._registrations[name] = DependencyRegistration(
            name=name,
            factory=lambda: instance,
            lifetime=Lifetime.SINGLETON,
            is_async=False
        )
        self._singletons[name] = instance
        logger.debug(f"Registered singleton instance: {name}")

    def is_registered(self, name: str) -> bool:
        """Check if a dependency is registered."""
        return name in self._registrations

    async def resolve(self, name: str) -> Any:
        """
        Resolve a dependency.

        For SCOPED dependencies, creates a new scope automatically.
        For proper scoped resolution, use create_scope().

        Args:
            name: Name of the dependency to resolve

        Returns:
            The resolved dependency instance

        Raises:
            KeyError: If dependency is not registered
        """
        if name not in self._registrations:
            raise KeyError(f"Dependency not registered: {name}")

        registration = self._registrations[name]

        if registration.lifetime == Lifetime.SINGLETON:
            return await self._resolve_singleton(name, registration)
        else:
            return await self._create_instance(registration)

    async def _resolve_singleton(
        self,
        name: str,
        registration: DependencyRegistration
    ) -> Any:
        """Resolve a singleton dependency."""
        if name not in self._singletons:
            async with self._singleton_lock:
                if name not in self._singletons:
                    self._singletons[name] = await self._create_instance(registration)
        return self._singletons[name]

    async def _create_instance(self, registration: DependencyRegistration) -> Any:
        """Create a new instance from a registration."""
        if registration.is_async:
            return await registration.factory()
        else:
            result = registration.factory()
            if asyncio.iscoroutine(result):
                return await result
            return result

    @asynccontextmanager
    async def create_scope(self):
        """
        Create a new dependency scope.

        Scoped dependencies will be reused within this scope.
        Yields a ScopedContainer for resolving dependencies.
        """
        scope = ScopedContainer(self)
        try:
            yield scope
        finally:
            await scope.dispose()

    async def dispose(self):
        """Dispose of all singleton instances."""
        for name, instance in self._singletons.items():
            try:
                if hasattr(instance, 'close'):
                    close_result = instance.close()
                    if asyncio.iscoroutine(close_result):
                        await close_result
                elif hasattr(instance, 'dispose'):
                    dispose_result = instance.dispose()
                    if asyncio.iscoroutine(dispose_result):
                        await dispose_result
            except Exception as e:
                logger.warning(f"Error disposing singleton {name}: {e}")

        self._singletons.clear()
        logger.info("Dependency container disposed")


class ScopedContainer:
    """
    Scoped dependency container.

    Created by DependencyContainer.create_scope().
    Maintains scoped instances for the duration of the scope.
    """

    def __init__(self, parent: DependencyContainer):
        self._parent = parent
        self._scope_id = str(uuid4())
        self._scoped_instances: Dict[str, Any] = {}

    async def resolve(self, name: str) -> Any:
        """
        Resolve a dependency within this scope.

        Args:
            name: Name of the dependency to resolve

        Returns:
            The resolved dependency instance
        """
        if name not in self._parent._registrations:
            raise KeyError(f"Dependency not registered: {name}")

        registration = self._parent._registrations[name]

        if registration.lifetime == Lifetime.SINGLETON:
            return await self._parent._resolve_singleton(name, registration)
        elif registration.lifetime == Lifetime.SCOPED:
            return await self._resolve_scoped(name, registration)
        else:
            return await self._parent._create_instance(registration)

    async def _resolve_scoped(
        self,
        name: str,
        registration: DependencyRegistration
    ) -> Any:
        """Resolve a scoped dependency."""
        if name not in self._scoped_instances:
            self._scoped_instances[name] = await self._parent._create_instance(registration)
        return self._scoped_instances[name]

    async def dispose(self):
        """Dispose of all scoped instances."""
        for name, instance in self._scoped_instances.items():
            try:
                if hasattr(instance, 'close'):
                    close_result = instance.close()
                    if asyncio.iscoroutine(close_result):
                        await close_result
                elif hasattr(instance, 'dispose'):
                    dispose_result = instance.dispose()
                    if asyncio.iscoroutine(dispose_result):
                        await dispose_result
            except Exception as e:
                logger.debug(f"Error disposing scoped instance {name}: {e}")

        self._scoped_instances.clear()


# ============================================================================
# GLOBAL CONTAINER INSTANCE
# ============================================================================

_container: Optional[DependencyContainer] = None


def get_container() -> DependencyContainer:
    """Get the global dependency container."""
    global _container
    if _container is None:
        _container = DependencyContainer()
        _setup_default_registrations(_container)
    return _container


def _setup_default_registrations(container: DependencyContainer):
    """Set up default dependency registrations."""
    from mind.core.database import async_session_factory
    from mind.core.llm_client import get_cached_client
    from mind.core.cache import get_cache_service
    from mind.memory.memory_core import get_memory_core
    from mind.engine.activity_engine import get_activity_engine

    # Database session - scoped per request
    container.register(
        "db_session",
        factory=lambda: async_session_factory(),
        lifetime=Lifetime.SCOPED,
        is_async=False
    )

    # LLM client - singleton
    container.register(
        "llm_client",
        factory=get_cached_client,
        lifetime=Lifetime.SINGLETON,
        is_async=True
    )

    # Cache service - singleton
    container.register(
        "cache",
        factory=get_cache_service,
        lifetime=Lifetime.SINGLETON,
        is_async=True
    )

    # Memory core - singleton
    container.register(
        "memory",
        factory=get_memory_core,
        lifetime=Lifetime.SINGLETON,
        is_async=True
    )

    # Activity engine - singleton
    container.register(
        "activity_engine",
        factory=get_activity_engine,
        lifetime=Lifetime.SINGLETON,
        is_async=True
    )

    logger.info("Default dependency registrations configured")


async def reset_container():
    """Reset the global container (useful for testing)."""
    global _container
    if _container is not None:
        await _container.dispose()
    _container = None
