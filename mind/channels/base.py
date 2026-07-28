"""
Base channel abstraction for multi-platform messaging.

This module defines the interface that all channel implementations must follow,
enabling bots to communicate seamlessly across different platforms.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional
from uuid import UUID, uuid4
import asyncio
import logging

logger = logging.getLogger(__name__)


class ChannelType(str, Enum):
    """Supported channel types."""
    TELEGRAM = "telegram"
    DISCORD = "discord"
    WHATSAPP = "whatsapp"
    SLACK = "slack"
    WEBSOCKET = "websocket"
    WEBHOOK = "webhook"


class MessageType(str, Enum):
    """Types of messages that can be sent/received."""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    FILE = "file"
    REACTION = "reaction"
    TYPING = "typing"
    SYSTEM = "system"


@dataclass
class ChannelMessage:
    """
    Unified message format across all channels.

    This normalizes messages from different platforms into a common format
    that our bot engine can process.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    channel_type: ChannelType = ChannelType.WEBSOCKET
    channel_user_id: str = ""  # Platform-specific user ID
    channel_chat_id: str = ""  # Platform-specific chat/conversation ID

    # Content
    message_type: MessageType = MessageType.TEXT
    text: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None

    # Metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)
    reply_to_id: Optional[str] = None
    thread_id: Optional[str] = None

    # Internal mapping
    internal_user_id: Optional[UUID] = None
    internal_bot_id: Optional[UUID] = None

    # Raw platform data (for advanced handling)
    raw_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "channel_type": self.channel_type.value,
            "channel_user_id": self.channel_user_id,
            "channel_chat_id": self.channel_chat_id,
            "message_type": self.message_type.value,
            "text": self.text,
            "media_url": self.media_url,
            "timestamp": self.timestamp.isoformat(),
            "reply_to_id": self.reply_to_id,
            "thread_id": self.thread_id,
        }


@dataclass
class SendResult:
    """Result of sending a message through a channel."""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    raw_response: Optional[dict] = None


class BaseChannel(ABC):
    """
    Abstract base class for channel implementations.

    Each channel (Telegram, Discord, etc.) must implement these methods
    to integrate with the Hive platform.
    """

    def __init__(self, channel_type: ChannelType):
        self.channel_type = channel_type
        self._message_handlers: list[Callable] = []
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if channel is connected and ready."""
        return self._connected

    @abstractmethod
    async def connect(self) -> bool:
        """
        Initialize connection to the channel.

        Returns True if connection successful.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Clean up and disconnect from the channel."""
        pass

    @abstractmethod
    async def send_message(
        self,
        chat_id: str,
        text: str,
        reply_to: Optional[str] = None,
        **kwargs
    ) -> SendResult:
        """
        Send a text message to a chat.

        Args:
            chat_id: Platform-specific chat identifier
            text: Message text to send
            reply_to: Optional message ID to reply to
            **kwargs: Platform-specific options

        Returns:
            SendResult with success status and message ID
        """
        pass

    @abstractmethod
    async def send_typing(self, chat_id: str) -> None:
        """
        Send typing indicator to a chat.

        This makes the bot appear more human-like by showing
        "typing..." before responding.
        """
        pass

    @abstractmethod
    async def parse_incoming(self, raw_data: dict) -> Optional[ChannelMessage]:
        """
        Parse incoming webhook/event data into a ChannelMessage.

        Args:
            raw_data: Raw data from the platform's webhook

        Returns:
            ChannelMessage if valid message, None otherwise
        """
        pass

    def on_message(self, handler: Callable) -> None:
        """Register a handler for incoming messages."""
        self._message_handlers.append(handler)

    async def _dispatch_message(self, message: ChannelMessage) -> None:
        """Dispatch a message to all registered handlers."""
        for handler in self._message_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                logger.error(f"Error in message handler: {e}")


class ChannelRouter:
    """
    Routes messages between channels and the bot engine.

    This is the main entry point for multi-channel communication.
    It manages channel connections and routes messages appropriately.
    """

    def __init__(self):
        self._channels: dict[ChannelType, BaseChannel] = {}
        self._user_mappings: dict[str, UUID] = {}  # channel_user_id -> internal_user_id
        self._bot_channel_mappings: dict[UUID, dict] = {}  # bot_id -> channel presence

    def register(self, channel: BaseChannel) -> None:
        """Register a channel for routing."""
        self._channels[channel.channel_type] = channel
        logger.info(f"Registered channel: {channel.channel_type.value}")

    def unregister(self, channel_type: ChannelType) -> None:
        """Unregister a channel."""
        if channel_type in self._channels:
            del self._channels[channel_type]
            logger.info(f"Unregistered channel: {channel_type.value}")

    def get_channel(self, channel_type: ChannelType) -> Optional[BaseChannel]:
        """Get a registered channel by type."""
        return self._channels.get(channel_type)

    async def connect_all(self) -> dict[ChannelType, bool]:
        """Connect all registered channels. Returns status for each."""
        results = {}
        for channel_type, channel in self._channels.items():
            try:
                results[channel_type] = await channel.connect()
            except Exception as e:
                logger.error(f"Failed to connect {channel_type.value}: {e}")
                results[channel_type] = False
        return results

    async def disconnect_all(self) -> None:
        """Disconnect all channels."""
        for channel in self._channels.values():
            try:
                await channel.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting channel: {e}")

    async def send(
        self,
        channel_type: ChannelType,
        chat_id: str,
        text: str,
        **kwargs
    ) -> SendResult:
        """
        Send a message through a specific channel.

        Args:
            channel_type: Which channel to send through
            chat_id: Platform-specific chat identifier
            text: Message text
            **kwargs: Additional platform-specific options

        Returns:
            SendResult with status
        """
        channel = self._channels.get(channel_type)
        if not channel:
            return SendResult(
                success=False,
                error=f"Channel {channel_type.value} not registered"
            )

        if not channel.is_connected:
            return SendResult(
                success=False,
                error=f"Channel {channel_type.value} not connected"
            )

        return await channel.send_message(chat_id, text, **kwargs)

    async def handle_incoming(
        self,
        channel_type: ChannelType,
        raw_data: dict
    ) -> Optional[ChannelMessage]:
        """
        Handle incoming webhook data from a channel.

        Args:
            channel_type: Which channel the data came from
            raw_data: Raw webhook payload

        Returns:
            Parsed ChannelMessage if valid
        """
        channel = self._channels.get(channel_type)
        if not channel:
            logger.warning(f"Received data for unregistered channel: {channel_type}")
            return None

        message = await channel.parse_incoming(raw_data)
        if message:
            # Map channel user to internal user if known
            mapping_key = f"{channel_type.value}:{message.channel_user_id}"
            if mapping_key in self._user_mappings:
                message.internal_user_id = self._user_mappings[mapping_key]

            await channel._dispatch_message(message)

        return message

    def map_user(
        self,
        channel_type: ChannelType,
        channel_user_id: str,
        internal_user_id: UUID
    ) -> None:
        """Map a channel user to an internal user ID."""
        key = f"{channel_type.value}:{channel_user_id}"
        self._user_mappings[key] = internal_user_id

    def set_bot_presence(
        self,
        bot_id: UUID,
        channel_type: ChannelType,
        channel_bot_id: str,
        enabled: bool = True
    ) -> None:
        """Configure a bot's presence on a channel."""
        if bot_id not in self._bot_channel_mappings:
            self._bot_channel_mappings[bot_id] = {}

        self._bot_channel_mappings[bot_id][channel_type] = {
            "channel_bot_id": channel_bot_id,
            "enabled": enabled
        }
