"""
Pub/Sub Service for AI Community Companions.
Enables real-time event distribution for horizontal scaling.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import uuid4

from mind.core.redis_client import RedisClient, get_redis_client

logger = logging.getLogger(__name__)


# ============================================================================
# Event Types and Channels
# ============================================================================

class EventChannel(str, Enum):
    """Standard pub/sub channels."""
    EVENTS = "events"                    # General events
    BOT_ACTIONS = "bot_actions"          # Bot behavior events
    USER_NOTIFICATIONS = "user_notifications"  # User-facing notifications
    SYSTEM = "system"                    # System-level events
    METRICS = "metrics"                  # Performance metrics


class EventType(str, Enum):
    """Standard event types."""
    # Content events
    NEW_POST = "new_post"
    NEW_COMMENT = "new_comment"
    POST_UPDATED = "post_updated"
    POST_DELETED = "post_deleted"

    # Bot behavior events
    BOT_TYPING = "bot_typing"
    BOT_THINKING = "bot_thinking"
    BOT_RESPONDING = "bot_responding"
    BOT_IDLE = "bot_idle"
    BOT_LEARNING = "bot_learning"
    BOT_MOOD_CHANGED = "bot_mood_changed"

    # Social events
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    REACTION_ADDED = "reaction_added"
    MENTION = "mention"

    # System events
    CACHE_INVALIDATED = "cache_invalidated"
    CONFIG_UPDATED = "config_updated"
    BOT_SPAWNED = "bot_spawned"
    BOT_TERMINATED = "bot_terminated"


@dataclass
class Event:
    """Event message structure."""
    event_type: str
    data: Dict[str, Any]
    channel: str = EventChannel.EVENTS.value
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: float = field(default_factory=time.time)
    source: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "channel": self.channel,
            "data": self.data,
            "timestamp": self.timestamp,
            "source": self.source
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Create from dictionary."""
        return cls(
            event_id=data.get("event_id", str(uuid4())),
            event_type=data.get("event_type", "unknown"),
            channel=data.get("channel", EventChannel.EVENTS.value),
            data=data.get("data", {}),
            timestamp=data.get("timestamp", time.time()),
            source=data.get("source", "unknown")
        )


# ============================================================================
# Event Handler Type
# ============================================================================

EventHandler = Callable[[Event], Any]


# ============================================================================
# Pub/Sub Service
# ============================================================================

class PubSubService:
    """
    Pub/Sub service for event distribution.
    Uses Redis for distributed messaging with local fallback.
    """

    def __init__(
        self,
        redis_client: Optional[RedisClient] = None,
        source_id: Optional[str] = None
    ):
        """
        Initialize pub/sub service.

        Args:
            redis_client: Optional Redis client
            source_id: Identifier for this service instance
        """
        self._redis: Optional[RedisClient] = redis_client
        self._source_id = source_id or f"instance-{uuid4().hex[:8]}"

        # Local handlers for fallback mode
        self._local_handlers: Dict[str, List[EventHandler]] = {}
        self._subscriptions: Dict[str, asyncio.Task] = {}

        # Event queue for local mode
        self._local_queue: asyncio.Queue = asyncio.Queue()
        self._local_processor: Optional[asyncio.Task] = None

        # Statistics
        self._events_published = 0
        self._events_received = 0
        self._errors = 0

    async def _get_redis(self) -> Optional[RedisClient]:
        """Get Redis client, initializing if needed."""
        if self._redis is None:
            try:
                self._redis = await get_redis_client()
            except Exception:
                return None

        if not self._redis.is_connected:
            return None

        return self._redis

    # ========================================================================
    # Publishing
    # ========================================================================

    async def publish_event(
        self,
        channel: str,
        event_type: str,
        data: Dict[str, Any],
        source: Optional[str] = None
    ) -> bool:
        """
        Publish an event to a channel.

        Args:
            channel: Channel name
            event_type: Type of event
            data: Event data
            source: Optional source identifier

        Returns:
            True if published successfully
        """
        event = Event(
            event_type=event_type,
            data=data,
            channel=channel,
            source=source or self._source_id
        )

        return await self.publish(event)

    async def publish(self, event: Event) -> bool:
        """
        Publish an event.

        Args:
            event: Event to publish

        Returns:
            True if published successfully
        """
        redis = await self._get_redis()

        if redis:
            try:
                subscribers = await redis.publish(event.channel, event.to_dict())
                self._events_published += 1
                logger.debug(
                    f"[PUBSUB] Published {event.event_type} to {event.channel} "
                    f"({subscribers} subscribers)"
                )
                return True
            except Exception as e:
                logger.error(f"[PUBSUB] Publish error: {e}")
                self._errors += 1

        # Fallback: local event delivery
        return await self._publish_local(event)

    async def _publish_local(self, event: Event) -> bool:
        """Publish event locally (fallback mode)."""
        handlers = self._local_handlers.get(event.channel, [])

        if not handlers:
            logger.debug(f"[PUBSUB] No local handlers for channel: {event.channel}")
            return True

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"[PUBSUB] Local handler error: {e}")
                self._errors += 1

        self._events_published += 1
        return True

    # ========================================================================
    # Subscribing
    # ========================================================================

    async def subscribe(
        self,
        channel: str,
        callback: EventHandler
    ) -> bool:
        """
        Subscribe to a channel.

        Args:
            channel: Channel name
            callback: Event handler callback

        Returns:
            True if subscribed successfully
        """
        redis = await self._get_redis()

        if redis:
            # Wrap callback to convert raw data to Event
            async def event_handler(ch: str, data: Any):
                try:
                    if isinstance(data, dict):
                        event = Event.from_dict(data)
                    else:
                        event = Event(
                            event_type="unknown",
                            data={"raw": data},
                            channel=ch
                        )

                    self._events_received += 1

                    if asyncio.iscoroutinefunction(callback):
                        await callback(event)
                    else:
                        callback(event)

                except Exception as e:
                    logger.error(f"[PUBSUB] Handler error: {e}")
                    self._errors += 1

            task = await redis.subscribe(channel, event_handler)
            if task:
                self._subscriptions[channel] = task
                logger.info(f"[PUBSUB] Subscribed to channel: {channel}")
                return True

        # Fallback: register local handler
        if channel not in self._local_handlers:
            self._local_handlers[channel] = []
        self._local_handlers[channel].append(callback)
        logger.info(f"[PUBSUB] Local subscription to channel: {channel}")
        return True

    async def unsubscribe(self, channel: str) -> bool:
        """
        Unsubscribe from a channel.

        Args:
            channel: Channel name

        Returns:
            True if unsubscribed
        """
        # Cancel Redis subscription
        if channel in self._subscriptions:
            task = self._subscriptions.pop(channel)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Remove local handlers
        if channel in self._local_handlers:
            del self._local_handlers[channel]

        logger.info(f"[PUBSUB] Unsubscribed from channel: {channel}")
        return True

    # ========================================================================
    # Convenience Methods
    # ========================================================================

    async def publish_new_post(
        self,
        post_id: str,
        author_id: str,
        community_id: str,
        preview: str
    ) -> bool:
        """Publish a new post event."""
        return await self.publish_event(
            channel=EventChannel.EVENTS.value,
            event_type=EventType.NEW_POST.value,
            data={
                "post_id": post_id,
                "author_id": author_id,
                "community_id": community_id,
                "preview": preview[:200]
            }
        )

    async def publish_new_comment(
        self,
        comment_id: str,
        post_id: str,
        author_id: str,
        preview: str
    ) -> bool:
        """Publish a new comment event."""
        return await self.publish_event(
            channel=EventChannel.EVENTS.value,
            event_type=EventType.NEW_COMMENT.value,
            data={
                "comment_id": comment_id,
                "post_id": post_id,
                "author_id": author_id,
                "preview": preview[:200]
            }
        )

    async def publish_bot_typing(
        self,
        bot_id: str,
        context_id: str,
        is_typing: bool = True
    ) -> bool:
        """Publish bot typing indicator."""
        return await self.publish_event(
            channel=EventChannel.BOT_ACTIONS.value,
            event_type=EventType.BOT_TYPING.value,
            data={
                "bot_id": bot_id,
                "context_id": context_id,
                "is_typing": is_typing
            }
        )

    async def publish_bot_mood_changed(
        self,
        bot_id: str,
        old_mood: str,
        new_mood: str,
        trigger: Optional[str] = None
    ) -> bool:
        """Publish bot mood change event."""
        return await self.publish_event(
            channel=EventChannel.BOT_ACTIONS.value,
            event_type=EventType.BOT_MOOD_CHANGED.value,
            data={
                "bot_id": bot_id,
                "old_mood": old_mood,
                "new_mood": new_mood,
                "trigger": trigger
            }
        )

    async def publish_user_notification(
        self,
        user_id: str,
        notification_type: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Publish user notification."""
        return await self.publish_event(
            channel=EventChannel.USER_NOTIFICATIONS.value,
            event_type=notification_type,
            data={
                "user_id": user_id,
                "message": message,
                **(data or {})
            }
        )

    async def publish_cache_invalidated(
        self,
        cache_key: str,
        reason: str
    ) -> bool:
        """Publish cache invalidation event."""
        return await self.publish_event(
            channel=EventChannel.SYSTEM.value,
            event_type=EventType.CACHE_INVALIDATED.value,
            data={
                "cache_key": cache_key,
                "reason": reason
            }
        )

    # ========================================================================
    # Statistics and Lifecycle
    # ========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get pub/sub statistics."""
        return {
            "source_id": self._source_id,
            "events_published": self._events_published,
            "events_received": self._events_received,
            "errors": self._errors,
            "active_subscriptions": len(self._subscriptions),
            "local_handlers": {
                ch: len(handlers)
                for ch, handlers in self._local_handlers.items()
            }
        }

    async def close(self) -> None:
        """Close all subscriptions and cleanup."""
        # Cancel all subscription tasks
        for channel, task in list(self._subscriptions.items()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._subscriptions.clear()
        self._local_handlers.clear()

        logger.info("[PUBSUB] Service closed")


# ============================================================================
# Module-level instance
# ============================================================================

_pubsub_service: Optional[PubSubService] = None


async def get_pubsub_service() -> PubSubService:
    """Get the global pub/sub service instance."""
    global _pubsub_service

    if _pubsub_service is None:
        try:
            redis_client = await get_redis_client()
            _pubsub_service = PubSubService(redis_client)
        except Exception:
            _pubsub_service = PubSubService()

    return _pubsub_service


async def close_pubsub_service() -> None:
    """Close the global pub/sub service."""
    global _pubsub_service

    if _pubsub_service is not None:
        await _pubsub_service.close()
        _pubsub_service = None
