"""
Push Service - Web Push and FCM integration for push notifications.
"""

import asyncio
import json
import logging
import os
from typing import Dict, List, Optional, Any
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from mind.config.settings import settings
from mind.core.database import async_session_factory, PushSubscriptionDB
from mind.notifications.models import Notification, PushSubscription

logger = logging.getLogger(__name__)


# =============================================================================
# FCM ERROR TYPES
# =============================================================================

class FCMError(Exception):
    """Base exception for FCM errors."""
    pass


class FCMInvalidTokenError(FCMError):
    """Raised when an FCM token is invalid or expired."""
    pass


class FCMQuotaExceededError(FCMError):
    """Raised when FCM quota is exceeded."""
    pass


class FCMServerError(FCMError):
    """Raised when FCM server encounters an error."""
    pass


class FCMNotInitializedError(FCMError):
    """Raised when FCM is not initialized."""
    pass


# =============================================================================
# FCM SERVICE
# =============================================================================

class FCMService:
    """
    Firebase Cloud Messaging service for sending push notifications to mobile devices.

    Handles:
    - Firebase Admin SDK initialization
    - Sending notifications to individual device tokens
    - Sending notifications to topics (e.g., all users, specific groups)
    - Graceful error handling and token validation
    """

    def __init__(self):
        """Initialize FCM service with Firebase credentials."""
        self._app = None
        self._initialized = False
        self._credentials_path = settings.FCM_CREDENTIALS_PATH
        self._project_id = settings.FCM_PROJECT_ID
        self._initialize()

    def _initialize(self) -> None:
        """Initialize Firebase Admin SDK."""
        if not self._credentials_path:
            logger.warning(
                "FCM credentials path not configured. FCM push notifications will be disabled. "
                "Set AIC_FCM_CREDENTIALS_PATH in settings."
            )
            return

        if not os.path.exists(self._credentials_path):
            logger.error(
                f"FCM credentials file not found at: {self._credentials_path}. "
                "FCM push notifications will be disabled."
            )
            return

        try:
            import firebase_admin
            from firebase_admin import credentials

            # Check if already initialized
            try:
                self._app = firebase_admin.get_app()
                self._initialized = True
                logger.info("FCM: Using existing Firebase app instance")
                return
            except ValueError:
                pass  # No existing app, continue initialization

            # Initialize with service account credentials
            cred = credentials.Certificate(self._credentials_path)

            options = {}
            if self._project_id:
                options['projectId'] = self._project_id

            self._app = firebase_admin.initialize_app(cred, options)
            self._initialized = True
            logger.info(f"FCM: Firebase Admin SDK initialized successfully (project: {self._project_id or 'auto-detected'})")

        except ImportError:
            logger.warning(
                "firebase-admin package not installed. FCM push notifications will be disabled. "
                "Install with: pip install firebase-admin"
            )
        except Exception as e:
            logger.error(f"FCM: Failed to initialize Firebase Admin SDK: {e}")

    @property
    def is_enabled(self) -> bool:
        """Check if FCM is enabled and initialized."""
        return self._initialized

    async def send_to_device(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        image_url: Optional[str] = None,
        badge: Optional[int] = None,
        sound: Optional[str] = "default",
        priority: str = "high",
        ttl: int = 3600,
    ) -> Dict[str, Any]:
        """
        Send a push notification to a specific device token.

        Args:
            token: FCM device registration token
            title: Notification title
            body: Notification body text
            data: Additional data payload (all values must be strings)
            image_url: URL of image to display in notification
            badge: Badge count for iOS
            sound: Sound to play (default, or custom sound file)
            priority: Message priority ('high' or 'normal')
            ttl: Time-to-live in seconds (how long FCM will attempt delivery)

        Returns:
            Dict with 'success' bool and 'message_id' or 'error' details

        Raises:
            FCMNotInitializedError: If FCM is not initialized
            FCMInvalidTokenError: If the token is invalid or expired
            FCMQuotaExceededError: If FCM quota is exceeded
            FCMServerError: If FCM server encounters an error
        """
        if not self._initialized:
            raise FCMNotInitializedError("FCM is not initialized. Check credentials configuration.")

        try:
            from firebase_admin import messaging

            # Build notification payload
            notification = messaging.Notification(
                title=title,
                body=body,
                image=image_url,
            )

            # Build Android-specific config
            android_config = messaging.AndroidConfig(
                priority=priority,
                ttl=ttl,
                notification=messaging.AndroidNotification(
                    icon="notification_icon",
                    color="#FF6B6B",
                    sound=sound if sound else "default",
                    click_action="FLUTTER_NOTIFICATION_CLICK",
                ),
            )

            # Build iOS-specific config (APNs)
            apns_config = messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        alert=messaging.ApsAlert(
                            title=title,
                            body=body,
                        ),
                        badge=badge,
                        sound=sound if sound else "default",
                        content_available=True,
                    ),
                ),
            )

            # Build the message
            message = messaging.Message(
                notification=notification,
                data=data or {},
                token=token,
                android=android_config,
                apns=apns_config,
            )

            # Send the message (run in executor for async compatibility)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                messaging.send,
                message,
            )

            logger.info(f"FCM: Successfully sent message to device. Message ID: {response}")
            return {
                "success": True,
                "message_id": response,
            }

        except ImportError:
            raise FCMNotInitializedError("firebase-admin package not installed")
        except Exception as e:
            return self._handle_fcm_error(e, token)

    async def send_to_topic(
        self,
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        image_url: Optional[str] = None,
        condition: Optional[str] = None,
        priority: str = "high",
        ttl: int = 3600,
    ) -> Dict[str, Any]:
        """
        Send a push notification to all devices subscribed to a topic.

        Args:
            topic: Topic name (e.g., 'news', 'updates', 'all_users')
            title: Notification title
            body: Notification body text
            data: Additional data payload (all values must be strings)
            image_url: URL of image to display in notification
            condition: Topic condition for targeting multiple topics
                      (e.g., "'news' in topics && 'sports' in topics")
            priority: Message priority ('high' or 'normal')
            ttl: Time-to-live in seconds

        Returns:
            Dict with 'success' bool and 'message_id' or 'error' details

        Raises:
            FCMNotInitializedError: If FCM is not initialized
            FCMServerError: If FCM server encounters an error
        """
        if not self._initialized:
            raise FCMNotInitializedError("FCM is not initialized. Check credentials configuration.")

        try:
            from firebase_admin import messaging

            # Build notification payload
            notification = messaging.Notification(
                title=title,
                body=body,
                image=image_url,
            )

            # Build Android-specific config
            android_config = messaging.AndroidConfig(
                priority=priority,
                ttl=ttl,
                notification=messaging.AndroidNotification(
                    icon="notification_icon",
                    color="#FF6B6B",
                    sound="default",
                ),
            )

            # Build iOS-specific config (APNs)
            apns_config = messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        alert=messaging.ApsAlert(
                            title=title,
                            body=body,
                        ),
                        sound="default",
                        content_available=True,
                    ),
                ),
            )

            # Build the message
            if condition:
                # Use condition for complex topic targeting
                message = messaging.Message(
                    notification=notification,
                    data=data or {},
                    condition=condition,
                    android=android_config,
                    apns=apns_config,
                )
            else:
                # Use simple topic targeting
                message = messaging.Message(
                    notification=notification,
                    data=data or {},
                    topic=topic,
                    android=android_config,
                    apns=apns_config,
                )

            # Send the message
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                messaging.send,
                message,
            )

            logger.info(f"FCM: Successfully sent message to topic '{topic}'. Message ID: {response}")
            return {
                "success": True,
                "message_id": response,
                "topic": topic,
            }

        except ImportError:
            raise FCMNotInitializedError("firebase-admin package not installed")
        except Exception as e:
            return self._handle_fcm_error(e, topic=topic)

    async def send_multicast(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        image_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a notification to multiple device tokens at once.

        Args:
            tokens: List of FCM device registration tokens (max 500)
            title: Notification title
            body: Notification body text
            data: Additional data payload
            image_url: URL of image to display

        Returns:
            Dict with 'success_count', 'failure_count', and 'failed_tokens'
        """
        if not self._initialized:
            raise FCMNotInitializedError("FCM is not initialized. Check credentials configuration.")

        if not tokens:
            return {"success_count": 0, "failure_count": 0, "failed_tokens": []}

        # FCM limits multicast to 500 tokens
        if len(tokens) > 500:
            logger.warning(f"FCM: Token list exceeds 500. Sending in batches.")

            results = {"success_count": 0, "failure_count": 0, "failed_tokens": []}
            for i in range(0, len(tokens), 500):
                batch_tokens = tokens[i:i + 500]
                batch_result = await self.send_multicast(
                    batch_tokens, title, body, data, image_url
                )
                results["success_count"] += batch_result["success_count"]
                results["failure_count"] += batch_result["failure_count"]
                results["failed_tokens"].extend(batch_result.get("failed_tokens", []))
            return results

        try:
            from firebase_admin import messaging

            # Build notification
            notification = messaging.Notification(
                title=title,
                body=body,
                image=image_url,
            )

            # Build multicast message
            message = messaging.MulticastMessage(
                notification=notification,
                data=data or {},
                tokens=tokens,
            )

            # Send the multicast message
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                messaging.send_each_for_multicast,
                message,
            )

            # Process response to identify failed tokens
            failed_tokens = []
            for idx, resp in enumerate(response.responses):
                if not resp.success:
                    failed_tokens.append({
                        "token": tokens[idx],
                        "error": str(resp.exception) if resp.exception else "Unknown error",
                    })

            logger.info(
                f"FCM: Multicast sent. Success: {response.success_count}, "
                f"Failures: {response.failure_count}"
            )

            return {
                "success_count": response.success_count,
                "failure_count": response.failure_count,
                "failed_tokens": failed_tokens,
            }

        except ImportError:
            raise FCMNotInitializedError("firebase-admin package not installed")
        except Exception as e:
            logger.error(f"FCM: Multicast error: {e}")
            return {
                "success_count": 0,
                "failure_count": len(tokens),
                "failed_tokens": [{"token": t, "error": str(e)} for t in tokens],
            }

    async def subscribe_to_topic(self, tokens: List[str], topic: str) -> Dict[str, Any]:
        """
        Subscribe device tokens to a topic.

        Args:
            tokens: List of FCM device registration tokens
            topic: Topic name to subscribe to

        Returns:
            Dict with 'success_count' and 'failure_count'
        """
        if not self._initialized:
            raise FCMNotInitializedError("FCM is not initialized.")

        try:
            from firebase_admin import messaging

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                messaging.subscribe_to_topic,
                tokens,
                topic,
            )

            logger.info(f"FCM: Subscribed {response.success_count} devices to topic '{topic}'")
            return {
                "success_count": response.success_count,
                "failure_count": response.failure_count,
            }

        except Exception as e:
            logger.error(f"FCM: Subscribe to topic error: {e}")
            return {"success_count": 0, "failure_count": len(tokens), "error": str(e)}

    async def unsubscribe_from_topic(self, tokens: List[str], topic: str) -> Dict[str, Any]:
        """
        Unsubscribe device tokens from a topic.

        Args:
            tokens: List of FCM device registration tokens
            topic: Topic name to unsubscribe from

        Returns:
            Dict with 'success_count' and 'failure_count'
        """
        if not self._initialized:
            raise FCMNotInitializedError("FCM is not initialized.")

        try:
            from firebase_admin import messaging

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                messaging.unsubscribe_from_topic,
                tokens,
                topic,
            )

            logger.info(f"FCM: Unsubscribed {response.success_count} devices from topic '{topic}'")
            return {
                "success_count": response.success_count,
                "failure_count": response.failure_count,
            }

        except Exception as e:
            logger.error(f"FCM: Unsubscribe from topic error: {e}")
            return {"success_count": 0, "failure_count": len(tokens), "error": str(e)}

    def _handle_fcm_error(
        self,
        error: Exception,
        token: Optional[str] = None,
        topic: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Handle FCM errors and return appropriate response.

        Args:
            error: The exception that occurred
            token: Device token (if applicable)
            topic: Topic name (if applicable)

        Returns:
            Dict with error details

        Raises:
            Appropriate FCM exception based on error type
        """
        error_str = str(error).lower()

        # Check for specific error types
        if "invalid" in error_str or "not found" in error_str or "unregistered" in error_str:
            logger.warning(f"FCM: Invalid or expired token: {token}")
            raise FCMInvalidTokenError(f"Invalid or expired token: {error}")

        elif "quota" in error_str or "rate" in error_str:
            logger.error(f"FCM: Quota exceeded: {error}")
            raise FCMQuotaExceededError(f"FCM quota exceeded: {error}")

        elif "server" in error_str or "internal" in error_str or "unavailable" in error_str:
            logger.error(f"FCM: Server error: {error}")
            raise FCMServerError(f"FCM server error: {error}")

        else:
            logger.error(f"FCM: Unexpected error: {error}")
            return {
                "success": False,
                "error": str(error),
                "token": token,
                "topic": topic,
            }


# =============================================================================
# PUSH SERVICE (Web Push + FCM)
# =============================================================================

class PushService:
    """
    Service for sending push notifications via Web Push and FCM.

    Supports:
    - Web Push (via pywebpush) for browser notifications
    - FCM (Firebase Cloud Messaging) for mobile apps
    """

    def __init__(self):
        """Initialize push service with VAPID credentials and FCM."""
        self._vapid_private_key = settings.VAPID_PRIVATE_KEY
        self._vapid_public_key = settings.VAPID_PUBLIC_KEY
        self._vapid_claims_email = settings.VAPID_CLAIMS_EMAIL
        self._initialized = self._check_credentials()

        # Initialize FCM service
        self._fcm_service = FCMService()

    def _check_credentials(self) -> bool:
        """Check if VAPID credentials are configured."""
        if not self._vapid_private_key or not self._vapid_public_key:
            logger.warning(
                "VAPID keys not configured. Push notifications will be disabled. "
                "Set VAPID_PRIVATE_KEY and VAPID_PUBLIC_KEY in settings."
            )
            return False
        return True

    @property
    def is_enabled(self) -> bool:
        """Check if push notifications are enabled."""
        return self._initialized

    @property
    def is_fcm_enabled(self) -> bool:
        """Check if FCM is enabled."""
        return self._fcm_service.is_enabled

    @property
    def public_key(self) -> Optional[str]:
        """Get the VAPID public key for client subscription."""
        return self._vapid_public_key if self._initialized else None

    @property
    def fcm_service(self) -> FCMService:
        """Get the FCM service instance."""
        return self._fcm_service

    async def register_device(
        self,
        user_id: UUID,
        subscription: Dict[str, Any],
    ) -> PushSubscription:
        """
        Register a push subscription for a user's device.

        Args:
            user_id: User ID to register subscription for
            subscription: Web Push subscription object containing:
                - endpoint: Push service endpoint URL
                - keys: Dict with p256dh and auth keys

        Returns:
            Created PushSubscription object
        """
        endpoint = subscription["endpoint"]
        keys = subscription.get("keys", {})

        push_sub = PushSubscription(
            user_id=user_id,
            endpoint=endpoint,
            keys=keys,
        )

        async with async_session_factory() as session:
            # Check if subscription already exists
            existing_stmt = select(PushSubscriptionDB).where(
                PushSubscriptionDB.endpoint == endpoint
            )
            existing_result = await session.execute(existing_stmt)
            existing = existing_result.scalar_one_or_none()

            if existing:
                # Update existing subscription
                existing.user_id = user_id
                existing.keys = keys
                logger.info(f"Updated push subscription for user {user_id}")
            else:
                # Create new subscription
                db_sub = PushSubscriptionDB(
                    user_id=user_id,
                    endpoint=endpoint,
                    keys=keys,
                    created_at=push_sub.created_at,
                )
                session.add(db_sub)
                logger.info(f"Registered new push subscription for user {user_id}")

            await session.commit()

        return push_sub

    async def unregister_device(
        self,
        user_id: UUID,
        endpoint: str,
    ) -> bool:
        """
        Unregister a push subscription.

        Args:
            user_id: User ID the subscription belongs to
            endpoint: Push service endpoint URL to unregister

        Returns:
            True if subscription was found and removed
        """
        async with async_session_factory() as session:
            stmt = delete(PushSubscriptionDB).where(
                PushSubscriptionDB.user_id == user_id,
                PushSubscriptionDB.endpoint == endpoint,
            )
            result = await session.execute(stmt)
            await session.commit()

            if result.rowcount > 0:
                logger.info(f"Unregistered push subscription for user {user_id}")
                return True
            return False

    async def get_user_subscriptions(self, user_id: UUID) -> List[PushSubscription]:
        """Get all push subscriptions for a user."""
        async with async_session_factory() as session:
            stmt = select(PushSubscriptionDB).where(
                PushSubscriptionDB.user_id == user_id
            )
            result = await session.execute(stmt)
            db_subs = result.scalars().all()

            return [
                PushSubscription(
                    user_id=sub.user_id,
                    endpoint=sub.endpoint,
                    keys=sub.keys,
                    created_at=sub.created_at,
                )
                for sub in db_subs
            ]

    async def send_push(
        self,
        user_id: UUID,
        notification: Notification,
    ) -> int:
        """
        Send a push notification to all user's devices.

        Args:
            user_id: User ID to send notification to
            notification: Notification to send

        Returns:
            Number of successful deliveries
        """
        if not self._initialized:
            logger.debug("Push notifications not configured, skipping send")
            return 0

        subscriptions = await self.get_user_subscriptions(user_id)
        if not subscriptions:
            logger.debug(f"No push subscriptions for user {user_id}")
            return 0

        payload = {
            "title": notification.title,
            "body": notification.body,
            "icon": "/icons/notification-icon.png",
            "badge": "/icons/badge-icon.png",
            "data": {
                "notification_id": str(notification.id),
                "type": notification.type.value,
                **notification.data,
            },
            "timestamp": notification.created_at.isoformat(),
        }

        success_count = 0
        failed_endpoints = []

        for sub in subscriptions:
            try:
                await self._send_webpush(sub, payload)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to send push to {sub.endpoint}: {e}")
                # Track failed endpoints for cleanup
                if "410" in str(e) or "404" in str(e):
                    failed_endpoints.append(sub.endpoint)

        # Clean up expired subscriptions
        if failed_endpoints:
            await self._cleanup_expired_subscriptions(user_id, failed_endpoints)

        logger.info(
            f"Sent push notification to {success_count}/{len(subscriptions)} "
            f"devices for user {user_id}"
        )
        return success_count

    async def send_push_batch(
        self,
        notifications: List[tuple[UUID, Notification]],
    ) -> Dict[str, int]:
        """
        Send push notifications to multiple users.

        Args:
            notifications: List of (user_id, notification) tuples

        Returns:
            Dict with success and failure counts
        """
        if not self._initialized:
            return {"success": 0, "failed": 0}

        tasks = [
            self.send_push(user_id, notification)
            for user_id, notification in notifications
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        success = sum(r for r in results if isinstance(r, int))
        failed = len([r for r in results if isinstance(r, Exception)])

        return {"success": success, "failed": failed}

    async def _send_webpush(
        self,
        subscription: PushSubscription,
        payload: Dict[str, Any],
    ) -> None:
        """
        Send a Web Push notification.

        Uses pywebpush library for actual delivery.
        """
        try:
            from pywebpush import webpush, WebPushException
        except ImportError:
            logger.warning(
                "pywebpush not installed. Install with: pip install pywebpush"
            )
            return

        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": subscription.keys,
        }

        vapid_claims = {
            "sub": f"mailto:{self._vapid_claims_email}",
        }

        try:
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload),
                vapid_private_key=self._vapid_private_key,
                vapid_claims=vapid_claims,
            )
        except WebPushException as e:
            # Re-raise to handle in caller
            raise e

    async def _cleanup_expired_subscriptions(
        self,
        user_id: UUID,
        endpoints: List[str],
    ) -> None:
        """Remove expired/invalid subscriptions."""
        async with async_session_factory() as session:
            for endpoint in endpoints:
                stmt = delete(PushSubscriptionDB).where(
                    PushSubscriptionDB.user_id == user_id,
                    PushSubscriptionDB.endpoint == endpoint,
                )
                await session.execute(stmt)
            await session.commit()

        logger.info(f"Cleaned up {len(endpoints)} expired subscriptions for user {user_id}")

    # =========================================================================
    # FCM (Firebase Cloud Messaging) Methods
    # =========================================================================

    async def send_fcm(
        self,
        user_id: UUID,
        notification: Notification,
        fcm_token: str,
    ) -> bool:
        """
        Send notification via Firebase Cloud Messaging to a specific device.

        Args:
            user_id: User ID to send to
            notification: Notification to send
            fcm_token: FCM device token

        Returns:
            True if sent successfully
        """
        if not self._fcm_service.is_enabled:
            logger.debug("FCM not configured, skipping send")
            return False

        try:
            # Convert notification data to string values (FCM requirement)
            data = {
                "notification_id": str(notification.id),
                "type": notification.type.value,
                "user_id": str(user_id),
            }
            for k, v in notification.data.items():
                data[k] = str(v)

            result = await self._fcm_service.send_to_device(
                token=fcm_token,
                title=notification.title,
                body=notification.body,
                data=data,
            )

            return result.get("success", False)

        except FCMInvalidTokenError:
            logger.warning(f"FCM: Invalid token for user {user_id}")
            return False
        except FCMError as e:
            logger.error(f"FCM: Error sending to user {user_id}: {e}")
            return False

    async def send_fcm_to_topic(
        self,
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Send notification to all devices subscribed to a topic.

        Args:
            topic: Topic name to send to
            title: Notification title
            body: Notification body
            data: Additional data payload

        Returns:
            True if sent successfully
        """
        if not self._fcm_service.is_enabled:
            logger.debug("FCM not configured, skipping topic send")
            return False

        try:
            result = await self._fcm_service.send_to_topic(
                topic=topic,
                title=title,
                body=body,
                data=data,
            )

            return result.get("success", False)

        except FCMError as e:
            logger.error(f"FCM: Error sending to topic '{topic}': {e}")
            return False

    async def send_fcm_multicast(
        self,
        tokens: List[str],
        notification: Notification,
    ) -> Dict[str, int]:
        """
        Send notification to multiple FCM tokens.

        Args:
            tokens: List of FCM device tokens
            notification: Notification to send

        Returns:
            Dict with success_count and failure_count
        """
        if not self._fcm_service.is_enabled:
            logger.debug("FCM not configured, skipping multicast")
            return {"success_count": 0, "failure_count": len(tokens)}

        try:
            # Convert notification data to string values
            data = {
                "notification_id": str(notification.id),
                "type": notification.type.value,
            }
            for k, v in notification.data.items():
                data[k] = str(v)

            result = await self._fcm_service.send_multicast(
                tokens=tokens,
                title=notification.title,
                body=notification.body,
                data=data,
            )

            return {
                "success_count": result.get("success_count", 0),
                "failure_count": result.get("failure_count", 0),
            }

        except FCMError as e:
            logger.error(f"FCM: Error in multicast: {e}")
            return {"success_count": 0, "failure_count": len(tokens)}


# Singleton instance
_push_service: Optional[PushService] = None


def get_push_service() -> PushService:
    """Get or create the push service singleton."""
    global _push_service
    if _push_service is None:
        _push_service = PushService()
    return _push_service


# Export FCM error types
__all__ = [
    "PushService",
    "FCMService",
    "get_push_service",
    "FCMError",
    "FCMInvalidTokenError",
    "FCMQuotaExceededError",
    "FCMServerError",
    "FCMNotInitializedError",
]
