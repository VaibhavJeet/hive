"""
Cache Service for AI Community Companions.
Provides high-level caching operations wrapping Redis.
"""

import asyncio
import functools
import hashlib
import json
import logging
import time
from typing import Any, Callable, Dict, Optional, TypeVar, Union

from mind.core.redis_client import RedisClient, get_redis_client

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheService:
    """
    High-level caching service wrapping Redis.
    Provides typed caching methods for common use cases.
    """

    # Cache key prefixes
    PREFIX_BOT_PROFILE = "bot:profile:"
    PREFIX_LLM_RESPONSE = "llm:response:"
    PREFIX_USER_SESSION = "user:session:"
    PREFIX_RATE_LIMIT = "rate:limit:"
    PREFIX_FEATURE_FLAG = "feature:flag:"

    def __init__(self, redis_client: Optional[RedisClient] = None):
        """
        Initialize cache service.

        Args:
            redis_client: Optional Redis client (will get global instance if None)
        """
        self._redis: Optional[RedisClient] = redis_client
        self._fallback_cache: Dict[str, tuple] = {}  # key -> (value, expiry_time)
        self._fallback_max_size = 1000

    async def _get_redis(self) -> Optional[RedisClient]:
        """Get Redis client, initializing if needed."""
        if self._redis is None:
            try:
                self._redis = await get_redis_client()
            except Exception as e:
                logger.warning(f"[CACHE] Failed to get Redis client: {e}")
                return None

        if not self._redis.is_connected:
            return None

        return self._redis

    def _get_from_fallback(self, key: str) -> Optional[Any]:
        """Get value from in-memory fallback cache."""
        if key in self._fallback_cache:
            value, expiry = self._fallback_cache[key]
            if expiry is None or time.time() < expiry:
                return value
            else:
                # Expired, remove it
                del self._fallback_cache[key]
        return None

    def _set_in_fallback(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in in-memory fallback cache."""
        # Evict oldest entries if cache is full
        if len(self._fallback_cache) >= self._fallback_max_size:
            # Remove 10% of oldest entries
            to_remove = list(self._fallback_cache.keys())[:self._fallback_max_size // 10]
            for k in to_remove:
                del self._fallback_cache[k]

        expiry = time.time() + ttl if ttl else None
        self._fallback_cache[key] = (value, expiry)

    def _delete_from_fallback(self, key: str) -> bool:
        """Delete value from in-memory fallback cache."""
        if key in self._fallback_cache:
            del self._fallback_cache[key]
            return True
        return False

    # ========================================================================
    # Bot Profile Caching
    # ========================================================================

    async def cache_bot_profile(
        self,
        bot_id: str,
        profile: Dict[str, Any],
        ttl: int = 300
    ) -> bool:
        """
        Cache a bot profile.

        Args:
            bot_id: Bot identifier
            profile: Bot profile data
            ttl: Time-to-live in seconds (default: 5 minutes)

        Returns:
            True if cached successfully
        """
        key = f"{self.PREFIX_BOT_PROFILE}{bot_id}"

        redis = await self._get_redis()
        if redis:
            success = await redis.set_json(key, profile, ttl=ttl)
            if success:
                logger.debug(f"[CACHE] Cached bot profile: {bot_id}")
                return True

        # Fallback to in-memory
        self._set_in_fallback(key, profile, ttl)
        logger.debug(f"[CACHE] Cached bot profile (fallback): {bot_id}")
        return True

    async def get_cached_bot_profile(
        self,
        bot_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached bot profile.

        Args:
            bot_id: Bot identifier

        Returns:
            Bot profile or None if not cached
        """
        key = f"{self.PREFIX_BOT_PROFILE}{bot_id}"

        redis = await self._get_redis()
        if redis:
            profile = await redis.get_json(key)
            if profile:
                logger.debug(f"[CACHE] Hit - bot profile: {bot_id}")
                return profile

        # Try fallback
        profile = self._get_from_fallback(key)
        if profile:
            logger.debug(f"[CACHE] Hit (fallback) - bot profile: {bot_id}")
            return profile

        logger.debug(f"[CACHE] Miss - bot profile: {bot_id}")
        return None

    async def invalidate_bot_cache(self, bot_id: str) -> bool:
        """
        Invalidate all cache entries for a bot.

        Args:
            bot_id: Bot identifier

        Returns:
            True if invalidated
        """
        key = f"{self.PREFIX_BOT_PROFILE}{bot_id}"

        redis = await self._get_redis()
        if redis:
            await redis.delete(key)

        self._delete_from_fallback(key)
        logger.debug(f"[CACHE] Invalidated bot cache: {bot_id}")
        return True

    # ========================================================================
    # LLM Response Caching
    # ========================================================================

    @staticmethod
    def hash_prompt(
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.8
    ) -> str:
        """
        Create a hash key for an LLM prompt.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Temperature setting

        Returns:
            Hash string
        """
        content = f"{system_prompt or ''}|{prompt}|{temperature}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    async def cache_llm_response(
        self,
        prompt_hash: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None,
        ttl: int = 3600
    ) -> bool:
        """
        Cache an LLM response.

        Args:
            prompt_hash: Hash of the prompt
            response: LLM response text
            metadata: Optional metadata (tokens, model, etc.)
            ttl: Time-to-live in seconds (default: 1 hour)

        Returns:
            True if cached successfully
        """
        key = f"{self.PREFIX_LLM_RESPONSE}{prompt_hash}"
        value = {
            "response": response,
            "metadata": metadata or {},
            "cached_at": time.time()
        }

        redis = await self._get_redis()
        if redis:
            success = await redis.set_json(key, value, ttl=ttl)
            if success:
                logger.debug(f"[CACHE] Cached LLM response: {prompt_hash[:8]}...")
                return True

        # Fallback
        self._set_in_fallback(key, value, ttl)
        return True

    async def get_cached_llm_response(
        self,
        prompt_hash: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached LLM response.

        Args:
            prompt_hash: Hash of the prompt

        Returns:
            Dict with 'response' and 'metadata' or None
        """
        key = f"{self.PREFIX_LLM_RESPONSE}{prompt_hash}"

        redis = await self._get_redis()
        if redis:
            cached = await redis.get_json(key)
            if cached:
                logger.debug(f"[CACHE] Hit - LLM response: {prompt_hash[:8]}...")
                return cached

        # Try fallback
        cached = self._get_from_fallback(key)
        if cached:
            logger.debug(f"[CACHE] Hit (fallback) - LLM response: {prompt_hash[:8]}...")
            return cached

        return None

    # ========================================================================
    # Generic Caching
    # ========================================================================

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        redis = await self._get_redis()
        if redis:
            value = await redis.get_json(key)
            if value is not None:
                return value

        return self._get_from_fallback(key)

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in cache."""
        redis = await self._get_redis()
        if redis:
            success = await redis.set_json(key, value, ttl=ttl)
            if success:
                return True

        self._set_in_fallback(key, value, ttl)
        return True

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        redis = await self._get_redis()
        if redis:
            await redis.delete(key)

        return self._delete_from_fallback(key)

    # ========================================================================
    # Statistics
    # ========================================================================

    def get_fallback_stats(self) -> Dict[str, Any]:
        """Get in-memory fallback cache statistics."""
        now = time.time()
        active = sum(
            1 for _, (_, exp) in self._fallback_cache.items()
            if exp is None or exp > now
        )

        return {
            "total_entries": len(self._fallback_cache),
            "active_entries": active,
            "max_size": self._fallback_max_size
        }


# ============================================================================
# Caching Decorator
# ============================================================================

def cached(
    ttl: int = 300,
    key_prefix: str = "",
    key_builder: Optional[Callable[..., str]] = None
):
    """
    Decorator for caching function results.

    Args:
        ttl: Time-to-live in seconds
        key_prefix: Prefix for cache keys
        key_builder: Optional function to build cache key from args

    Usage:
        @cached(ttl=300, key_prefix="user:")
        async def get_user(user_id: str) -> dict:
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Default: use function name and args
                key_parts = [func.__name__]
                key_parts.extend(str(a) for a in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = ":".join(key_parts)

            if key_prefix:
                cache_key = f"{key_prefix}{cache_key}"

            # Try to get from cache
            cache_service = CacheService()
            cached_value = await cache_service.get(cache_key)

            if cached_value is not None:
                logger.debug(f"[CACHE] Decorator hit: {cache_key}")
                return cached_value

            # Call function and cache result
            result = await func(*args, **kwargs)

            if result is not None:
                await cache_service.set(cache_key, result, ttl=ttl)
                logger.debug(f"[CACHE] Decorator miss - cached: {cache_key}")

            return result

        return wrapper
    return decorator


# ============================================================================
# Module-level instance
# ============================================================================

_cache_service: Optional[CacheService] = None


async def get_cache_service() -> CacheService:
    """Get the global cache service instance."""
    global _cache_service

    if _cache_service is None:
        redis_client = await get_redis_client()
        _cache_service = CacheService(redis_client)

    return _cache_service
