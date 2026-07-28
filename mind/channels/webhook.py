"""
Webhook handler for receiving messages from external channels.

Provides FastAPI routes for handling incoming webhooks from
Telegram, Discord, and other platforms.
"""

import hashlib
import hmac
import logging
from typing import Callable, Optional

from fastapi import APIRouter, Header, HTTPException, Request

from .base import ChannelRouter, ChannelType

logger = logging.getLogger(__name__)


class WebhookHandler:
    """
    FastAPI webhook handler for incoming channel messages.

    Usage:
        router = ChannelRouter()
        router.register(TelegramChannel(token="..."))

        webhook = WebhookHandler(router)

        # Add routes to FastAPI app
        app.include_router(webhook.router, prefix="/webhooks")
    """

    def __init__(
        self,
        channel_router: ChannelRouter,
        telegram_secret: Optional[str] = None,
        discord_public_key: Optional[str] = None,
    ):
        self.channel_router = channel_router
        self.telegram_secret = telegram_secret
        self.discord_public_key = discord_public_key

        self.router = APIRouter(tags=["webhooks"])
        self._setup_routes()

        # Callback for when messages are received
        self._message_callback: Optional[Callable] = None

    def on_message(self, callback: Callable) -> None:
        """Set callback for incoming messages."""
        self._message_callback = callback

    def _setup_routes(self) -> None:
        """Set up webhook routes for each channel."""

        @self.router.post("/telegram")
        async def telegram_webhook(
            request: Request,
            x_telegram_bot_api_secret_token: Optional[str] = Header(None),
        ):
            """Handle incoming Telegram webhook updates."""
            # Verify secret token if configured
            if self.telegram_secret:
                if x_telegram_bot_api_secret_token != self.telegram_secret:
                    raise HTTPException(status_code=403, detail="Invalid secret token")

            try:
                data = await request.json()
                message = await self.channel_router.handle_incoming(
                    ChannelType.TELEGRAM, data
                )

                if message and self._message_callback:
                    await self._message_callback(message)

                return {"ok": True}

            except Exception as e:
                logger.error(f"Telegram webhook error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/discord")
        async def discord_webhook(
            request: Request,
            x_signature_ed25519: Optional[str] = Header(None),
            x_signature_timestamp: Optional[str] = Header(None),
        ):
            """Handle incoming Discord interactions/gateway events."""
            try:
                data = await request.json()

                # Handle Discord's ping verification
                if data.get("type") == 1:
                    return {"type": 1}

                # Verify signature if configured
                if self.discord_public_key and x_signature_ed25519:
                    body = await request.body()
                    if not self._verify_discord_signature(
                        body, x_signature_ed25519, x_signature_timestamp or ""
                    ):
                        raise HTTPException(status_code=401, detail="Invalid signature")

                message = await self.channel_router.handle_incoming(
                    ChannelType.DISCORD, data
                )

                if message and self._message_callback:
                    await self._message_callback(message)

                return {"ok": True}

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Discord webhook error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/generic/{channel_name}")
        async def generic_webhook(channel_name: str, request: Request):
            """Handle webhooks from other channels."""
            try:
                channel_type = ChannelType(channel_name.lower())
            except ValueError:
                raise HTTPException(status_code=404, detail=f"Unknown channel: {channel_name}")

            try:
                data = await request.json()
                message = await self.channel_router.handle_incoming(channel_type, data)

                if message and self._message_callback:
                    await self._message_callback(message)

                return {"ok": True}

            except Exception as e:
                logger.error(f"Webhook error for {channel_name}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/health")
        async def webhook_health():
            """Health check for webhook endpoints."""
            channels = {}
            for channel_type in ChannelType:
                channel = self.channel_router.get_channel(channel_type)
                channels[channel_type.value] = {
                    "registered": channel is not None,
                    "connected": channel.is_connected if channel else False,
                }

            return {
                "status": "healthy",
                "channels": channels,
            }

    def _verify_discord_signature(
        self,
        body: bytes,
        signature: str,
        timestamp: str,
    ) -> bool:
        """Verify Discord webhook signature using Ed25519."""
        if not self.discord_public_key:
            return True

        try:
            from nacl.signing import VerifyKey
            from nacl.exceptions import BadSignature

            verify_key = VerifyKey(bytes.fromhex(self.discord_public_key))
            verify_key.verify(
                timestamp.encode() + body,
                bytes.fromhex(signature)
            )
            return True

        except (ImportError, BadSignature, Exception) as e:
            logger.warning(f"Discord signature verification failed: {e}")
            return False

    def _verify_telegram_hash(self, data: dict, bot_token: str) -> bool:
        """Verify Telegram webhook data hash."""
        check_hash = data.pop("hash", None)
        if not check_hash:
            return False

        # Sort and concatenate
        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(data.items())
        )

        # Create secret key
        secret_key = hashlib.sha256(bot_token.encode()).digest()

        # Calculate hash
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        return calculated_hash == check_hash
