"""
Redis Client for AI Community Companions.
Provides connection pooling, caching, and pub/sub support.
"""

import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Union
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Try to import redis, but make it optional
try:
    import redis.asyncio as redis
    from redis.asyncio import ConnectionPool
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None
    ConnectionPool = None


class RedisClient:
    """
    Async Redis client with connection pooling.
    Implements singleton pattern for resource efficiency.
    """

    _instance: Optional["RedisClient"] = None
    _lock = asyncio.Lock()

    def __init__(
        self,
        url: str = "redis://localhost:6379/0",
        max_connections: int = 10,
        decode_responses: bool = True
    ):
        """
        Initialize Redis client.

        Args:
            url: Redis connection URL
            max_connections: Maximum number of connections in pool
            decode_responses: Whether to decode responses to strings
        """
        self.url = url
        self.max_connections = max_connections
        self.decode_responses = decode_responses
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[redis.Redis] = None
        self._connected = False
        self._pubsub_tasks: List[asyncio.Task] = []

    @classmethod
    async def get_instance(
        cls,
        url: str = "redis://localhost:6379/0",
        max_connections: int = 10
    ) -> "RedisClient":
        """
        Get or create singleton instance.

        Args:
            url: Redis connection URL
            max_connections: Maximum connections in pool

        Returns:
            RedisClient instance
        """
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls(url=url, max_connections=max_connections)
                await cls._instance.connect()
            return cls._instance

    @classmethod
    async def reset_instance(cls) -> None:
        """Reset the singleton instance (for testing)."""
        async with cls._lock:
            if cls._instance is not None:
                await cls._instance.close()
                cls._instance = None

    async def connect(self) -> bool:
        """
        Establish connection to Redis.

        Returns:
            True if connected successfully, False otherwise
        """
        if not REDIS_AVAILABLE:
            logger.warning("[REDIS] redis package not installed - Redis features disabled")
            return False

        try:
            self._pool = ConnectionPool.from_url(
                self.url,
                max_connections=self.max_connections,
                decode_responses=self.decode_responses
            )
            self._client = redis.Redis(connection_pool=self._pool)

            # Test connection
            await self._client.ping()
            self._connected = True
            logger.info(f"[REDIS] Connected to {self.url}")
            return True

        except Exception as e:
            logger.warning(f"[REDIS] Connection failed: {e}")
            self._connected = False
            return False

    @property
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        return self._connected and self._client is not None

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on Redis connection.

        Returns:
            Health status dictionary
        """
        if not self.is_connected:
            return {
                "healthy": False,
                "connected": False,
                "error": "Not connected to Redis"
            }

        try:
            start = asyncio.get_event_loop().time()
            await self._client.ping()
            latency_ms = (asyncio.get_event_loop().time() - start) * 1000

            info = await self._client.info("server")

            return {
                "healthy": True,
                "connected": True,
                "latency_ms": round(latency_ms, 2),
                "redis_version": info.get("redis_version", "unknown"),
                "connected_clients": info.get("connected_clients", 0)
            }

        except Exception as e:
            return {
                "healthy": False,
                "connected": self._connected,
                "error": str(e)
            }

    # ========================================================================
    # Basic Key-Value Operations
    # ========================================================================

    async def get(self, key: str) -> Optional[str]:
        """
        Get value by key.

        Args:
            key: Redis key

        Returns:
            Value or None if not found
        """
        if not self.is_connected:
            return None

        try:
            return await self._client.get(key)
        except Exception as e:
            logger.error(f"[REDIS] GET error for key '{key}': {e}")
            return None

    async def set(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set key-value pair.

        Args:
            key: Redis key
            value: Value to store
            ttl: Time-to-live in seconds (optional)

        Returns:
            True if successful
        """
        if not self.is_connected:
            return False

        try:
            if ttl:
                await self._client.setex(key, ttl, value)
            else:
                await self._client.set(key, value)
            return True
        except Exception as e:
            logger.error(f"[REDIS] SET error for key '{key}': {e}")
            return False

    async def delete(self, *keys: str) -> int:
        """
        Delete one or more keys.

        Args:
            keys: Keys to delete

        Returns:
            Number of keys deleted
        """
        if not self.is_connected or not keys:
            return 0

        try:
            return await self._client.delete(*keys)
        except Exception as e:
            logger.error(f"[REDIS] DELETE error: {e}")
            return 0

    async def expire(self, key: str, ttl: int) -> bool:
        """
        Set expiration time on key.

        Args:
            key: Redis key
            ttl: Time-to-live in seconds

        Returns:
            True if successful
        """
        if not self.is_connected:
            return False

        try:
            return await self._client.expire(key, ttl)
        except Exception as e:
            logger.error(f"[REDIS] EXPIRE error for key '{key}': {e}")
            return False

    async def exists(self, *keys: str) -> int:
        """
        Check if keys exist.

        Args:
            keys: Keys to check

        Returns:
            Number of existing keys
        """
        if not self.is_connected or not keys:
            return 0

        try:
            return await self._client.exists(*keys)
        except Exception as e:
            logger.error(f"[REDIS] EXISTS error: {e}")
            return 0

    async def keys(self, pattern: str = "*") -> List[str]:
        """
        Get keys matching pattern.

        Args:
            pattern: Key pattern (e.g., "cache:*")

        Returns:
            List of matching keys
        """
        if not self.is_connected:
            return []

        try:
            return await self._client.keys(pattern)
        except Exception as e:
            logger.error(f"[REDIS] KEYS error for pattern '{pattern}': {e}")
            return []

    # ========================================================================
    # JSON Serialization Helpers
    # ========================================================================

    async def get_json(self, key: str) -> Optional[Any]:
        """
        Get and deserialize JSON value.

        Args:
            key: Redis key

        Returns:
            Deserialized object or None
        """
        value = await self.get(key)
        if value is None:
            return None

        try:
            return json.loads(value)
        except json.JSONDecodeError as e:
            logger.error(f"[REDIS] JSON decode error for key '{key}': {e}")
            return None

    async def set_json(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Serialize and set JSON value.

        Args:
            key: Redis key
            value: Object to serialize
            ttl: Time-to-live in seconds

        Returns:
            True if successful
        """
        try:
            json_str = json.dumps(value, default=str)
            return await self.set(key, json_str, ttl=ttl)
        except (TypeError, ValueError) as e:
            logger.error(f"[REDIS] JSON encode error for key '{key}': {e}")
            return False

    # ========================================================================
    # Pub/Sub Support
    # ========================================================================

    async def publish(self, channel: str, message: Union[str, Dict]) -> int:
        """
        Publish message to channel.

        Args:
            channel: Channel name
            message: Message to publish (string or dict)

        Returns:
            Number of subscribers that received the message
        """
        if not self.is_connected:
            return 0

        try:
            if isinstance(message, dict):
                message = json.dumps(message, default=str)
            return await self._client.publish(channel, message)
        except Exception as e:
            logger.error(f"[REDIS] PUBLISH error on channel '{channel}': {e}")
            return 0

    async def subscribe(
        self,
        channel: str,
        callback: Callable[[str, str], None]
    ) -> Optional[asyncio.Task]:
        """
        Subscribe to channel with callback.

        Args:
            channel: Channel name or pattern
            callback: Async callback function(channel, message)

        Returns:
            Subscription task or None if failed
        """
        if not self.is_connected:
            logger.warning(f"[REDIS] Cannot subscribe - not connected")
            return None

        try:
            pubsub = self._client.pubsub()
            await pubsub.subscribe(channel)

            async def listener():
                try:
                    async for message in pubsub.listen():
                        if message["type"] == "message":
                            channel_name = message["channel"]
                            data = message["data"]

                            # Try to parse as JSON
                            try:
                                if isinstance(data, str):
                                    data = json.loads(data)
                            except json.JSONDecodeError:
                                pass

                            if asyncio.iscoroutinefunction(callback):
                                await callback(channel_name, data)
                            else:
                                callback(channel_name, data)

                except asyncio.CancelledError:
                    await pubsub.unsubscribe(channel)
                    raise
                except Exception as e:
                    logger.error(f"[REDIS] Subscription error on '{channel}': {e}")

            task = asyncio.create_task(listener())
            self._pubsub_tasks.append(task)
            logger.info(f"[REDIS] Subscribed to channel '{channel}'")
            return task

        except Exception as e:
            logger.error(f"[REDIS] SUBSCRIBE error for channel '{channel}': {e}")
            return None

    async def psubscribe(
        self,
        pattern: str,
        callback: Callable[[str, str], None]
    ) -> Optional[asyncio.Task]:
        """
        Subscribe to channels matching pattern.

        Args:
            pattern: Channel pattern (e.g., "events:*")
            callback: Async callback function(channel, message)

        Returns:
            Subscription task or None if failed
        """
        if not self.is_connected:
            return None

        try:
            pubsub = self._client.pubsub()
            await pubsub.psubscribe(pattern)

            async def listener():
                try:
                    async for message in pubsub.listen():
                        if message["type"] == "pmessage":
                            channel_name = message["channel"]
                            data = message["data"]

                            try:
                                if isinstance(data, str):
                                    data = json.loads(data)
                            except json.JSONDecodeError:
                                pass

                            if asyncio.iscoroutinefunction(callback):
                                await callback(channel_name, data)
                            else:
                                callback(channel_name, data)

                except asyncio.CancelledError:
                    await pubsub.punsubscribe(pattern)
                    raise
                except Exception as e:
                    logger.error(f"[REDIS] Pattern subscription error '{pattern}': {e}")

            task = asyncio.create_task(listener())
            self._pubsub_tasks.append(task)
            logger.info(f"[REDIS] Pattern subscribed to '{pattern}'")
            return task

        except Exception as e:
            logger.error(f"[REDIS] PSUBSCRIBE error for pattern '{pattern}': {e}")
            return None

    # ========================================================================
    # Lifecycle
    # ========================================================================

    async def close(self) -> None:
        """Close Redis connection and cleanup."""
        # Cancel all pubsub tasks
        for task in self._pubsub_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._pubsub_tasks.clear()

        if self._client:
            await self._client.close()
            self._client = None

        if self._pool:
            await self._pool.disconnect()
            self._pool = None

        self._connected = False
        logger.info("[REDIS] Connection closed")

    @asynccontextmanager
    async def pipeline(self):
        """
        Create a pipeline for batching commands.

        Usage:
            async with redis_client.pipeline() as pipe:
                await pipe.set("key1", "value1")
                await pipe.set("key2", "value2")
                results = await pipe.execute()
        """
        if not self.is_connected:
            raise RuntimeError("Redis not connected")

        pipe = self._client.pipeline()
        try:
            yield pipe
        finally:
            await pipe.execute()


# ============================================================================
# Module-level convenience functions
# ============================================================================

_redis_client: Optional[RedisClient] = None


async def get_redis_client() -> RedisClient:
    """Get the global Redis client instance."""
    global _redis_client

    if _redis_client is None:
        from mind.config.settings import settings
        _redis_client = await RedisClient.get_instance(
            url=settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS
        )

    return _redis_client


async def close_redis_client() -> None:
    """Close the global Redis client."""
    global _redis_client

    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
