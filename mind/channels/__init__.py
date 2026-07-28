"""
Multi-channel messaging system for Hive.

Inspired by OpenClaw's channel architecture, this module provides a unified
interface for bots to communicate across multiple platforms.

Supported channels:
- Telegram
- Discord
- WhatsApp (via Twilio/Meta API)
- Slack
- WebSocket (internal)

Usage:
    from mind.channels import ChannelRouter, TelegramChannel

    router = ChannelRouter()
    router.register(TelegramChannel(token="..."))

    # Send message through any channel
    await router.send("telegram", user_id, "Hello!")

    # Receive messages via webhook
    @app.post("/webhook/telegram")
    async def telegram_webhook(update: dict):
        await router.handle_incoming("telegram", update)
"""

from .base import BaseChannel, ChannelMessage, ChannelRouter, ChannelType
from .telegram import TelegramChannel
from .discord import DiscordChannel
from .webhook import WebhookHandler
from .channel_service import ChannelService, get_channel_service

__all__ = [
    "BaseChannel",
    "ChannelMessage",
    "ChannelRouter",
    "ChannelType",
    "TelegramChannel",
    "DiscordChannel",
    "WebhookHandler",
    "ChannelService",
    "get_channel_service",
]
