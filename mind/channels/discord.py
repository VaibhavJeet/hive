"""
Discord channel implementation.

Provides integration with Discord via webhooks and bot API.
Supports server channels, DMs, and thread conversations.
"""

import logging
from typing import Optional
import aiohttp

from .base import (
    BaseChannel,
    ChannelMessage,
    ChannelType,
    MessageType,
    SendResult,
)

logger = logging.getLogger(__name__)


class DiscordChannel(BaseChannel):
    """
    Discord Bot integration.

    Can operate in two modes:
    1. Webhook mode - Simple outgoing messages only
    2. Bot mode - Full interaction with Discord Gateway

    Usage:
        # Webhook mode (simpler)
        channel = DiscordChannel(webhook_url="https://discord.com/api/webhooks/...")

        # Bot mode (full features)
        channel = DiscordChannel(bot_token="YOUR_BOT_TOKEN")
    """

    BASE_URL = "https://discord.com/api/v10"

    def __init__(
        self,
        bot_token: Optional[str] = None,
        webhook_url: Optional[str] = None,
    ):
        super().__init__(ChannelType.DISCORD)
        self.bot_token = bot_token
        self.webhook_url = webhook_url
        self._session: Optional[aiohttp.ClientSession] = None
        self._bot_user: Optional[dict] = None

    @property
    def headers(self) -> dict:
        """Get authorization headers for API requests."""
        if self.bot_token:
            return {"Authorization": f"Bot {self.bot_token}"}
        return {}

    async def connect(self) -> bool:
        """Initialize session and verify credentials."""
        try:
            self._session = aiohttp.ClientSession()

            if self.bot_token:
                # Verify bot token
                async with self._session.get(
                    f"{self.BASE_URL}/users/@me",
                    headers=self.headers
                ) as resp:
                    if resp.status == 200:
                        self._bot_user = await resp.json()
                        logger.info(
                            f"Discord connected: {self._bot_user.get('username')}#"
                            f"{self._bot_user.get('discriminator')}"
                        )
                        self._connected = True
                        return True
                    else:
                        logger.error(f"Discord auth failed: {resp.status}")
                        return False

            elif self.webhook_url:
                # Verify webhook
                async with self._session.get(self.webhook_url) as resp:
                    if resp.status == 200:
                        webhook_info = await resp.json()
                        logger.info(f"Discord webhook connected: {webhook_info.get('name')}")
                        self._connected = True
                        return True
                    else:
                        logger.error(f"Discord webhook invalid: {resp.status}")
                        return False

            else:
                logger.error("Discord: No bot_token or webhook_url provided")
                return False

        except Exception as e:
            logger.error(f"Discord connection error: {e}")
            return False

    async def disconnect(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None
        self._connected = False

    async def send_message(
        self,
        chat_id: str,
        text: str,
        reply_to: Optional[str] = None,
        username: Optional[str] = None,
        avatar_url: Optional[str] = None,
        **kwargs
    ) -> SendResult:
        """
        Send a message to Discord.

        In webhook mode:
            - chat_id is ignored (uses webhook's channel)
            - username/avatar_url customize the sender

        In bot mode:
            - chat_id is the channel ID
            - username/avatar_url are ignored
        """
        if not self._session or not self._connected:
            return SendResult(success=False, error="Not connected")

        try:
            if self.webhook_url:
                # Webhook mode
                payload = {"content": text}
                if username:
                    payload["username"] = username
                if avatar_url:
                    payload["avatar_url"] = avatar_url

                async with self._session.post(
                    f"{self.webhook_url}?wait=true",
                    json=payload
                ) as resp:
                    if resp.status in (200, 204):
                        data = await resp.json() if resp.status == 200 else {}
                        return SendResult(
                            success=True,
                            message_id=data.get("id"),
                            raw_response=data
                        )
                    else:
                        error = await resp.text()
                        return SendResult(success=False, error=error)

            else:
                # Bot mode
                payload = {"content": text}
                if reply_to:
                    payload["message_reference"] = {"message_id": reply_to}

                async with self._session.post(
                    f"{self.BASE_URL}/channels/{chat_id}/messages",
                    headers=self.headers,
                    json=payload
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return SendResult(
                            success=True,
                            message_id=data.get("id"),
                            raw_response=data
                        )
                    else:
                        error = await resp.text()
                        return SendResult(success=False, error=error)

        except Exception as e:
            logger.error(f"Discord send error: {e}")
            return SendResult(success=False, error=str(e))

    async def send_typing(self, chat_id: str) -> None:
        """Send typing indicator (bot mode only)."""
        if not self._session or not self._connected or not self.bot_token:
            return

        try:
            await self._session.post(
                f"{self.BASE_URL}/channels/{chat_id}/typing",
                headers=self.headers
            )
        except Exception as e:
            logger.debug(f"Failed to send typing indicator: {e}")

    async def parse_incoming(self, raw_data: dict) -> Optional[ChannelMessage]:
        """
        Parse Discord gateway event or webhook payload.

        Handles MESSAGE_CREATE events from Discord Gateway.
        """
        # Check if this is a gateway event
        event_type = raw_data.get("t")
        if event_type != "MESSAGE_CREATE":
            return None

        data = raw_data.get("d", raw_data)

        # Ignore bot messages (prevent loops)
        author = data.get("author", {})
        if author.get("bot"):
            return None

        # Determine message type
        msg_type = MessageType.TEXT
        text = data.get("content")
        media_url = None

        attachments = data.get("attachments", [])
        if attachments:
            att = attachments[0]
            content_type = att.get("content_type", "")
            media_url = att.get("url")

            if content_type.startswith("image/"):
                msg_type = MessageType.IMAGE
            elif content_type.startswith("video/"):
                msg_type = MessageType.VIDEO
            elif content_type.startswith("audio/"):
                msg_type = MessageType.AUDIO
            else:
                msg_type = MessageType.FILE

        # Get reply info
        reply_to = None
        if data.get("referenced_message"):
            reply_to = data["referenced_message"].get("id")

        return ChannelMessage(
            id=data.get("id", ""),
            channel_type=ChannelType.DISCORD,
            channel_user_id=author.get("id", ""),
            channel_chat_id=data.get("channel_id", ""),
            message_type=msg_type,
            text=text,
            media_url=media_url,
            reply_to_id=reply_to,
            thread_id=data.get("thread", {}).get("id") if data.get("thread") else None,
            raw_data=raw_data,
        )

    async def create_dm_channel(self, user_id: str) -> Optional[str]:
        """
        Create a DM channel with a user.

        Returns the channel ID for sending DMs.
        """
        if not self._session or not self.bot_token:
            return None

        try:
            async with self._session.post(
                f"{self.BASE_URL}/users/@me/channels",
                headers=self.headers,
                json={"recipient_id": user_id}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("id")

        except Exception as e:
            logger.error(f"Failed to create DM channel: {e}")

        return None
