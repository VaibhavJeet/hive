"""
Hooks System - Event-driven extensibility.

Hooks allow extending bot behavior by subscribing to events.
They can modify behavior, add logging, trigger side effects, etc.

Events include:
- Bot lifecycle (start, stop, error)
- Message events (receive, send, edit)
- Content events (post created, liked, commented)
- Learning events (belief updated, skill learned)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class HookEvent(str, Enum):
    """Available hook events."""
    # Bot lifecycle
    BOT_STARTED = "bot.started"
    BOT_STOPPED = "bot.stopped"
    BOT_ERROR = "bot.error"

    # Message events
    MESSAGE_RECEIVED = "message.received"
    MESSAGE_SENDING = "message.sending"
    MESSAGE_SENT = "message.sent"
    MESSAGE_FAILED = "message.failed"

    # Content events
    POST_CREATING = "post.creating"
    POST_CREATED = "post.created"
    COMMENT_CREATED = "comment.created"
    REACTION_ADDED = "reaction.added"

    # Learning events
    BELIEF_UPDATED = "learning.belief_updated"
    SKILL_LEARNED = "learning.skill_learned"
    MEMORY_STORED = "learning.memory_stored"

    # Channel events
    CHANNEL_CONNECTED = "channel.connected"
    CHANNEL_DISCONNECTED = "channel.disconnected"
    CHANNEL_MESSAGE = "channel.message"

    # System events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    HEALTH_CHECK = "system.health_check"


class HookPriority(int, Enum):
    """Hook execution priority (lower = earlier)."""
    FIRST = 0
    HIGH = 25
    NORMAL = 50
    LOW = 75
    LAST = 100


@dataclass
class HookContext:
    """Context passed to hook handlers."""
    event: HookEvent
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: dict = field(default_factory=dict)
    bot_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    metadata: dict = field(default_factory=dict)

    # Control flow
    cancelled: bool = False
    modified_data: Optional[dict] = None

    def cancel(self) -> None:
        """Cancel the event (prevent default behavior)."""
        self.cancelled = True

    def modify(self, **kwargs) -> None:
        """Modify the event data."""
        if self.modified_data is None:
            self.modified_data = dict(self.data)
        self.modified_data.update(kwargs)


# Type for hook handlers
HookHandler = Callable[[HookContext], Coroutine[Any, Any, None]]


@dataclass
class Hook:
    """A registered hook."""
    id: str = field(default_factory=lambda: str(uuid4()))
    event: HookEvent = HookEvent.MESSAGE_RECEIVED
    handler: Optional[HookHandler] = None
    priority: HookPriority = HookPriority.NORMAL
    name: str = ""
    description: str = ""
    enabled: bool = True
    filter_fn: Optional[Callable[[HookContext], bool]] = None

    async def execute(self, context: HookContext) -> None:
        """Execute the hook handler."""
        if not self.enabled or not self.handler:
            return

        # Check filter
        if self.filter_fn and not self.filter_fn(context):
            return

        try:
            await self.handler(context)
        except Exception as e:
            logger.error(f"Hook {self.name} ({self.id}) error: {e}")


class HookManager:
    """
    Manages hook registration and event dispatching.

    Usage:
        manager = HookManager()

        @manager.on(HookEvent.MESSAGE_RECEIVED)
        async def log_messages(ctx: HookContext):
            print(f"Message from {ctx.data['sender']}: {ctx.data['text']}")

        # Trigger event
        await manager.emit(HookEvent.MESSAGE_RECEIVED, data={"sender": "user", "text": "hi"})
    """

    def __init__(self):
        self._hooks: dict[HookEvent, list[Hook]] = {event: [] for event in HookEvent}
        self._global_hooks: list[Hook] = []  # Called for all events

    def register(self, hook: Hook) -> str:
        """Register a hook. Returns the hook ID."""
        self._hooks[hook.event].append(hook)
        # Sort by priority
        self._hooks[hook.event].sort(key=lambda h: h.priority.value)
        logger.debug(f"Registered hook: {hook.name} for {hook.event.value}")
        return hook.id

    def on(
        self,
        event: HookEvent,
        priority: HookPriority = HookPriority.NORMAL,
        name: str = "",
        filter_fn: Optional[Callable[[HookContext], bool]] = None,
    ) -> Callable[[HookHandler], HookHandler]:
        """
        Decorator to register a hook handler.

        Usage:
            @manager.on(HookEvent.MESSAGE_RECEIVED)
            async def my_handler(ctx: HookContext):
                ...
        """
        def decorator(handler: HookHandler) -> HookHandler:
            hook = Hook(
                event=event,
                handler=handler,
                priority=priority,
                name=name or handler.__name__,
                filter_fn=filter_fn,
            )
            self.register(hook)
            return handler
        return decorator

    def on_all(
        self,
        priority: HookPriority = HookPriority.NORMAL,
        name: str = "",
    ) -> Callable[[HookHandler], HookHandler]:
        """Register a handler for all events."""
        def decorator(handler: HookHandler) -> HookHandler:
            hook = Hook(
                handler=handler,
                priority=priority,
                name=name or handler.__name__,
            )
            self._global_hooks.append(hook)
            self._global_hooks.sort(key=lambda h: h.priority.value)
            return handler
        return decorator

    def unregister(self, hook_id: str) -> bool:
        """Unregister a hook by ID."""
        for event_hooks in self._hooks.values():
            for hook in event_hooks:
                if hook.id == hook_id:
                    event_hooks.remove(hook)
                    return True

        for hook in self._global_hooks:
            if hook.id == hook_id:
                self._global_hooks.remove(hook)
                return True

        return False

    async def emit(
        self,
        event: HookEvent,
        data: Optional[dict] = None,
        bot_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        **metadata
    ) -> HookContext:
        """
        Emit an event and run all registered hooks.

        Returns the context (check .cancelled and .modified_data).
        """
        context = HookContext(
            event=event,
            data=data or {},
            bot_id=bot_id,
            user_id=user_id,
            metadata=metadata,
        )

        # Run global hooks first
        for hook in self._global_hooks:
            if context.cancelled:
                break
            await hook.execute(context)

        # Run event-specific hooks
        for hook in self._hooks[event]:
            if context.cancelled:
                break
            await hook.execute(context)

        return context

    def get_hooks(self, event: Optional[HookEvent] = None) -> list[Hook]:
        """Get registered hooks, optionally filtered by event."""
        if event:
            return list(self._hooks[event])
        all_hooks = []
        for hooks in self._hooks.values():
            all_hooks.extend(hooks)
        all_hooks.extend(self._global_hooks)
        return all_hooks

    def clear(self, event: Optional[HookEvent] = None) -> None:
        """Clear hooks, optionally for a specific event."""
        if event:
            self._hooks[event] = []
        else:
            for event_type in HookEvent:
                self._hooks[event_type] = []
            self._global_hooks = []


# Global hook manager
_global_hook_manager: Optional[HookManager] = None


def get_hook_manager() -> HookManager:
    """Get the global hook manager."""
    global _global_hook_manager
    if _global_hook_manager is None:
        _global_hook_manager = HookManager()
    return _global_hook_manager


# Convenience decorators using global manager
def on_event(
    event: HookEvent,
    priority: HookPriority = HookPriority.NORMAL,
) -> Callable[[HookHandler], HookHandler]:
    """Decorator to register a hook with the global manager."""
    return get_hook_manager().on(event, priority)


# Built-in hooks for common functionality

async def _log_all_events(ctx: HookContext) -> None:
    """Log all events (useful for debugging)."""
    logger.debug(
        f"[HOOK] {ctx.event.value} | "
        f"bot={ctx.bot_id} user={ctx.user_id} | "
        f"data={list(ctx.data.keys())}"
    )


def enable_event_logging() -> None:
    """Enable logging for all hook events."""
    manager = get_hook_manager()
    hook = Hook(
        handler=_log_all_events,
        priority=HookPriority.FIRST,
        name="event_logger",
    )
    manager._global_hooks.insert(0, hook)
