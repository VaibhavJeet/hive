"""
Channel Service - Manages external channel connections and routing.

This service integrates external messaging channels (Telegram, Discord) with
the Hive platform, allowing bots to interact with users across platforms.
"""

import logging
from typing import Optional
from uuid import UUID

from mind.config.settings import settings
from mind.channels.base import ChannelRouter, ChannelType, ChannelMessage, SendResult
from mind.channels.telegram import TelegramChannel
from mind.channels.discord import DiscordChannel

logger = logging.getLogger(__name__)


# Singleton instance
_channel_service: Optional["ChannelService"] = None


async def get_channel_service() -> "ChannelService":
    """Get or create the channel service singleton."""
    global _channel_service
    if _channel_service is None:
        _channel_service = ChannelService()
        await _channel_service.initialize()
    return _channel_service


class ChannelService:
    """
    Service for managing external communication channels.

    Handles:
    - Channel initialization based on configuration
    - Message routing to/from external platforms
    - Bot presence on external channels
    - User mapping between platforms and internal IDs
    """

    def __init__(self):
        self.router = ChannelRouter()
        self.initialized = False
        self._message_handlers: list = []

    async def initialize(self) -> bool:
        """
        Initialize configured channels.

        Reads from settings to determine which channels to enable.
        """
        if not settings.EXTERNAL_CHANNELS_ENABLED:
            logger.info("External channels disabled in settings")
            return False

        channels_connected = 0

        # Initialize Telegram if configured
        if settings.TELEGRAM_BOT_TOKEN:
            try:
                telegram = TelegramChannel(token=settings.TELEGRAM_BOT_TOKEN)
                self.router.register(telegram)
                if await telegram.connect():
                    channels_connected += 1
                    logger.info("Telegram channel connected")
                else:
                    logger.warning("Telegram channel failed to connect")
            except Exception as e:
                logger.error(f"Failed to initialize Telegram: {e}")

        # Initialize Discord if configured
        if settings.DISCORD_BOT_TOKEN or settings.DISCORD_WEBHOOK_URL:
            try:
                discord = DiscordChannel(
                    bot_token=settings.DISCORD_BOT_TOKEN,
                    webhook_url=settings.DISCORD_WEBHOOK_URL
                )
                self.router.register(discord)
                if await discord.connect():
                    channels_connected += 1
                    logger.info("Discord channel connected")
                else:
                    logger.warning("Discord channel failed to connect")
            except Exception as e:
                logger.error(f"Failed to initialize Discord: {e}")

        self.initialized = channels_connected > 0
        logger.info(f"Channel service initialized with {channels_connected} channel(s)")
        return self.initialized

    async def shutdown(self) -> None:
        """Disconnect all channels gracefully."""
        await self.router.disconnect_all()
        self.initialized = False
        logger.info("Channel service shut down")

    def on_message(self, handler) -> None:
        """Register a handler for incoming messages from any channel."""
        self._message_handlers.append(handler)

    async def handle_webhook(
        self,
        channel_type: ChannelType,
        raw_data: dict
    ) -> Optional[ChannelMessage]:
        """
        Handle incoming webhook from an external channel.

        Args:
            channel_type: Type of channel (TELEGRAM, DISCORD)
            raw_data: Raw webhook payload

        Returns:
            Parsed message if valid
        """
        message = await self.router.handle_incoming(channel_type, raw_data)

        if message:
            # Dispatch to registered handlers
            for handler in self._message_handlers:
                try:
                    await handler(message)
                except Exception as e:
                    logger.error(f"Error in message handler: {e}")

        return message

    async def send_as_bot(
        self,
        bot_id: UUID,
        bot_name: str,
        channel_type: ChannelType,
        chat_id: str,
        text: str,
        avatar_url: Optional[str] = None,
        **kwargs
    ) -> SendResult:
        """
        Send a message as a specific bot.

        Args:
            bot_id: Internal bot ID
            bot_name: Display name of the bot
            channel_type: Which channel to send through
            chat_id: Platform-specific chat identifier
            text: Message content
            avatar_url: Bot's avatar URL (for Discord webhooks)

        Returns:
            SendResult with status
        """
        # Add bot identity to kwargs for platforms that support it
        kwargs["username"] = bot_name
        if avatar_url:
            kwargs["avatar_url"] = avatar_url

        return await self.router.send(channel_type, chat_id, text, **kwargs)

    async def broadcast_post(
        self,
        bot_id: UUID,
        bot_name: str,
        content: str,
        avatar_url: Optional[str] = None
    ) -> dict:
        """
        Broadcast a bot's post to all configured channels.

        Returns dict with results per channel.
        """
        results = {}

        # Broadcast to Discord if configured
        if settings.DISCORD_WEBHOOK_URL:
            result = await self.send_as_bot(
                bot_id=bot_id,
                bot_name=bot_name,
                channel_type=ChannelType.DISCORD,
                chat_id="",  # Webhook doesn't need chat_id
                text=content,
                avatar_url=avatar_url
            )
            results["discord"] = result.success

        # Note: Telegram requires explicit chat_ids, can't broadcast freely

        return results

    def is_channel_available(self, channel_type: ChannelType) -> bool:
        """Check if a specific channel is configured and connected."""
        channel = self.router.get_channel(channel_type)
        return channel is not None and channel.is_connected
