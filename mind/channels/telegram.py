"""
Telegram channel implementation.

Provides integration with Telegram Bot API for sending and receiving messages.
Bots can communicate with users through Telegram while maintaining their
unique personalities.
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


class TelegramChannel(BaseChannel):
    """
    Telegram Bot API integration.

    Usage:
        channel = TelegramChannel(token="YOUR_BOT_TOKEN")
        await channel.connect()

        # Send a message
        result = await channel.send_message(chat_id="123456", text="Hello!")

        # Handle incoming webhook
        message = await channel.parse_incoming(webhook_data)
    """

    BASE_URL = "https://api.telegram.org/bot"

    def __init__(self, token: str):
        super().__init__(ChannelType.TELEGRAM)
        self.token = token
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def api_url(self) -> str:
        return f"{self.BASE_URL}{self.token}"

    async def connect(self) -> bool:
        """Initialize HTTP session and verify bot token."""
        try:
            self._session = aiohttp.ClientSession()

            # Verify token by calling getMe
            async with self._session.get(f"{self.api_url}/getMe") as resp:
                data = await resp.json()
                if data.get("ok"):
                    bot_info = data["result"]
                    logger.info(
                        f"Telegram connected: @{bot_info.get('username')} "
                        f"(ID: {bot_info.get('id')})"
                    )
                    self._connected = True
                    return True
                else:
                    logger.error(f"Telegram auth failed: {data}")
                    return False

        except Exception as e:
            logger.error(f"Telegram connection error: {e}")
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
        parse_mode: str = "HTML",
        **kwargs
    ) -> SendResult:
        """
        Send a text message via Telegram.

        Args:
            chat_id: Telegram chat ID
            text: Message text (supports HTML formatting)
            reply_to: Message ID to reply to
            parse_mode: "HTML" or "Markdown"
        """
        if not self._session or not self._connected:
            return SendResult(success=False, error="Not connected")

        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }

        if reply_to:
            payload["reply_to_message_id"] = reply_to

        try:
            async with self._session.post(
                f"{self.api_url}/sendMessage",
                json=payload
            ) as resp:
                data = await resp.json()

                if data.get("ok"):
                    msg = data["result"]
                    return SendResult(
                        success=True,
                        message_id=str(msg["message_id"]),
                        raw_response=data
                    )
                else:
                    return SendResult(
                        success=False,
                        error=data.get("description", "Unknown error"),
                        raw_response=data
                    )

        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return SendResult(success=False, error=str(e))

    async def send_typing(self, chat_id: str) -> None:
        """Send typing indicator to show bot is composing a message."""
        if not self._session or not self._connected:
            return

        try:
            await self._session.post(
                f"{self.api_url}/sendChatAction",
                json={"chat_id": chat_id, "action": "typing"}
            )
        except Exception as e:
            logger.debug(f"Failed to send typing indicator: {e}")

    async def parse_incoming(self, raw_data: dict) -> Optional[ChannelMessage]:
        """
        Parse Telegram webhook update into ChannelMessage.

        Handles:
        - Regular messages
        - Edited messages
        - Channel posts
        - Callback queries (button clicks)
        """
        # Handle different update types
        message_data = (
            raw_data.get("message") or
            raw_data.get("edited_message") or
            raw_data.get("channel_post")
        )

        if not message_data:
            # Could be callback_query, inline_query, etc.
            return None

        # Extract sender info
        sender = message_data.get("from", {})
        chat = message_data.get("chat", {})

        # Determine message type and content
        msg_type = MessageType.TEXT
        text = message_data.get("text")
        media_url = None

        if "photo" in message_data:
            msg_type = MessageType.IMAGE
            # Get largest photo
            photos = message_data["photo"]
            if photos:
                media_url = photos[-1].get("file_id")

        elif "video" in message_data:
            msg_type = MessageType.VIDEO
            media_url = message_data["video"].get("file_id")

        elif "voice" in message_data or "audio" in message_data:
            msg_type = MessageType.AUDIO
            audio = message_data.get("voice") or message_data.get("audio")
            media_url = audio.get("file_id") if audio else None

        elif "document" in message_data:
            msg_type = MessageType.FILE
            media_url = message_data["document"].get("file_id")

        # Get caption for media messages
        if not text and "caption" in message_data:
            text = message_data["caption"]

        # Build channel message
        return ChannelMessage(
            id=str(message_data.get("message_id", "")),
            channel_type=ChannelType.TELEGRAM,
            channel_user_id=str(sender.get("id", "")),
            channel_chat_id=str(chat.get("id", "")),
            message_type=msg_type,
            text=text,
            media_url=media_url,
            reply_to_id=str(message_data.get("reply_to_message", {}).get("message_id", ""))
            if message_data.get("reply_to_message") else None,
            raw_data=raw_data,
        )

    async def get_file_url(self, file_id: str) -> Optional[str]:
        """
        Get download URL for a Telegram file.

        Telegram doesn't provide direct URLs for media - you need to
        call getFile first to get the file path.
        """
        if not self._session or not self._connected:
            return None

        try:
            async with self._session.get(
                f"{self.api_url}/getFile",
                params={"file_id": file_id}
            ) as resp:
                data = await resp.json()

                if data.get("ok"):
                    file_path = data["result"]["file_path"]
                    return f"https://api.telegram.org/file/bot{self.token}/{file_path}"

        except Exception as e:
            logger.error(f"Failed to get file URL: {e}")

        return None

    async def set_webhook(self, url: str, secret_token: Optional[str] = None) -> bool:
        """
        Configure webhook URL for receiving updates.

        Args:
            url: HTTPS URL to receive webhook updates
            secret_token: Optional secret for webhook verification
        """
        if not self._session:
            return False

        payload = {"url": url}
        if secret_token:
            payload["secret_token"] = secret_token

        try:
            async with self._session.post(
                f"{self.api_url}/setWebhook",
                json=payload
            ) as resp:
                data = await resp.json()
                return data.get("ok", False)

        except Exception as e:
            logger.error(f"Failed to set webhook: {e}")
            return False
