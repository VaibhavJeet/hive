"""
Notification Service - Manages notification creation, retrieval, and event handling.
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, update, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import (
    async_session_factory,
    NotificationDB,
    BotProfileDB,
    PostDB,
    AppUserDB,
)
from mind.notifications.models import Notification, NotificationType

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service for managing user notifications.

    Handles creation, retrieval, and status updates for notifications.
    Integrates with event handlers for automatic notification generation.
    """

    def __init__(self, push_service: Optional["PushService"] = None, realtime_callback=None):
        """
        Initialize notification service.

        Args:
            push_service: Optional PushService for sending push notifications
            realtime_callback: Optional async callback for real-time WebSocket delivery
        """
        self._push_service = push_service
        self._realtime_callback = realtime_callback

    def set_push_service(self, push_service: "PushService") -> None:
        """Set the push service for sending notifications."""
        self._push_service = push_service

    def set_realtime_callback(self, callback) -> None:
        """Set the callback for real-time WebSocket notification delivery."""
        self._realtime_callback = callback

    async def create_notification(
        self,
        user_id: UUID,
        notification_type: NotificationType,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        send_push: bool = True,
    ) -> Notification:
        """
        Create a new notification for a user.

        Args:
            user_id: Target user ID
            notification_type: Type of notification
            title: Notification title
            body: Notification body text
            data: Additional payload data
            send_push: Whether to send a push notification

        Returns:
            Created Notification object
        """
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            title=title,
            body=body,
            data=data or {},
        )

        async with async_session_factory() as session:
            db_notification = NotificationDB(
                id=notification.id,
                user_id=notification.user_id,
                type=notification.type.value,
                title=notification.title,
                body=notification.body,
                data=notification.data,
                read=notification.read,
                created_at=notification.created_at,
            )
            session.add(db_notification)
            await session.commit()

        logger.info(f"Created notification {notification.id} for user {user_id}: {title}")

        # Send real-time notification via WebSocket
        if self._realtime_callback:
            try:
                await self._realtime_callback(user_id, notification.to_dict())
            except Exception as e:
                logger.error(f"Failed to send real-time notification: {e}")

        # Send push notification if enabled
        if send_push and self._push_service:
            try:
                await self._push_service.send_push(user_id, notification)
            except Exception as e:
                logger.error(f"Failed to send push notification: {e}")

        return notification

    async def get_notifications(
        self,
        user_id: UUID,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Notification]:
        """
        Get notifications for a user.

        Args:
            user_id: User ID to get notifications for
            unread_only: If True, only return unread notifications
            limit: Maximum number of notifications to return
            offset: Number of notifications to skip

        Returns:
            List of Notification objects
        """
        async with async_session_factory() as session:
            stmt = (
                select(NotificationDB)
                .where(NotificationDB.user_id == user_id)
                .order_by(desc(NotificationDB.created_at))
                .limit(limit)
                .offset(offset)
            )

            if unread_only:
                stmt = stmt.where(NotificationDB.read == False)

            result = await session.execute(stmt)
            db_notifications = result.scalars().all()

            return [
                Notification(
                    id=n.id,
                    user_id=n.user_id,
                    type=NotificationType(n.type),
                    title=n.title,
                    body=n.body,
                    data=n.data,
                    read=n.read,
                    created_at=n.created_at,
                )
                for n in db_notifications
            ]

    async def get_unread_count(self, user_id: UUID) -> int:
        """Get count of unread notifications for a user."""
        async with async_session_factory() as session:
            from sqlalchemy import func
            stmt = (
                select(func.count(NotificationDB.id))
                .where(NotificationDB.user_id == user_id)
                .where(NotificationDB.read == False)
            )
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def mark_as_read(self, notification_id: UUID) -> bool:
        """
        Mark a notification as read.

        Args:
            notification_id: ID of notification to mark as read

        Returns:
            True if notification was found and updated
        """
        async with async_session_factory() as session:
            stmt = (
                update(NotificationDB)
                .where(NotificationDB.id == notification_id)
                .values(read=True)
            )
            result = await session.execute(stmt)
            await session.commit()

            return result.rowcount > 0

    async def mark_all_read(self, user_id: UUID) -> int:
        """
        Mark all notifications for a user as read.

        Args:
            user_id: User ID to mark notifications for

        Returns:
            Number of notifications marked as read
        """
        async with async_session_factory() as session:
            stmt = (
                update(NotificationDB)
                .where(NotificationDB.user_id == user_id)
                .where(NotificationDB.read == False)
                .values(read=True)
            )
            result = await session.execute(stmt)
            await session.commit()

            return result.rowcount

    async def delete_notification(self, notification_id: UUID) -> bool:
        """
        Delete a notification.

        Args:
            notification_id: ID of notification to delete

        Returns:
            True if notification was found and deleted
        """
        async with async_session_factory() as session:
            stmt = delete(NotificationDB).where(NotificationDB.id == notification_id)
            result = await session.execute(stmt)
            await session.commit()

            return result.rowcount > 0

    async def delete_all_notifications(self, user_id: UUID) -> int:
        """
        Delete all notifications for a user.

        Args:
            user_id: User ID to delete notifications for

        Returns:
            Number of notifications deleted
        """
        async with async_session_factory() as session:
            stmt = delete(NotificationDB).where(NotificationDB.user_id == user_id)
            result = await session.execute(stmt)
            await session.commit()

            return result.rowcount

    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================

    async def on_post_liked(
        self,
        post_id: UUID,
        liker_id: UUID,
        liker_is_bot: bool = False,
    ) -> Optional[Notification]:
        """
        Handle post like event - notify post author.

        Args:
            post_id: ID of the liked post
            liker_id: ID of the user who liked the post
            liker_is_bot: Whether the liker is a bot

        Returns:
            Created notification or None if author is the liker
        """
        async with async_session_factory() as session:
            # Get post and author
            post_stmt = select(PostDB).where(PostDB.id == post_id)
            post_result = await session.execute(post_stmt)
            post = post_result.scalar_one_or_none()

            if not post:
                logger.warning(f"Post {post_id} not found for like notification")
                return None

            # Don't notify if user liked their own post
            if post.author_id == liker_id:
                return None

            # Get liker name
            if liker_is_bot:
                liker_stmt = select(BotProfileDB).where(BotProfileDB.id == liker_id)
                liker_result = await session.execute(liker_stmt)
                liker = liker_result.scalar_one_or_none()
                liker_name = liker.display_name if liker else "Someone"
            else:
                liker_stmt = select(AppUserDB).where(AppUserDB.id == liker_id)
                liker_result = await session.execute(liker_stmt)
                liker = liker_result.scalar_one_or_none()
                liker_name = liker.display_name if liker else "Someone"

        return await self.create_notification(
            user_id=post.author_id,
            notification_type=NotificationType.LIKE,
            title="New Like",
            body=f"{liker_name} liked your post",
            data={
                "post_id": str(post_id),
                "liker_id": str(liker_id),
                "liker_is_bot": liker_is_bot,
            },
        )

    async def on_comment_added(
        self,
        post_id: UUID,
        commenter_id: UUID,
        comment_preview: str,
        commenter_is_bot: bool = False,
    ) -> Optional[Notification]:
        """
        Handle new comment event - notify post author.

        Args:
            post_id: ID of the commented post
            commenter_id: ID of the user who commented
            comment_preview: Preview of the comment text
            commenter_is_bot: Whether the commenter is a bot

        Returns:
            Created notification or None if author is the commenter
        """
        async with async_session_factory() as session:
            # Get post and author
            post_stmt = select(PostDB).where(PostDB.id == post_id)
            post_result = await session.execute(post_stmt)
            post = post_result.scalar_one_or_none()

            if not post:
                logger.warning(f"Post {post_id} not found for comment notification")
                return None

            # Don't notify if user commented on their own post
            if post.author_id == commenter_id:
                return None

            # Get commenter name
            if commenter_is_bot:
                commenter_stmt = select(BotProfileDB).where(BotProfileDB.id == commenter_id)
                commenter_result = await session.execute(commenter_stmt)
                commenter = commenter_result.scalar_one_or_none()
                commenter_name = commenter.display_name if commenter else "Someone"
            else:
                commenter_stmt = select(AppUserDB).where(AppUserDB.id == commenter_id)
                commenter_result = await session.execute(commenter_stmt)
                commenter = commenter_result.scalar_one_or_none()
                commenter_name = commenter.display_name if commenter else "Someone"

        # Truncate comment preview
        preview = comment_preview[:100] + "..." if len(comment_preview) > 100 else comment_preview

        return await self.create_notification(
            user_id=post.author_id,
            notification_type=NotificationType.COMMENT,
            title="New Comment",
            body=f'{commenter_name}: "{preview}"',
            data={
                "post_id": str(post_id),
                "commenter_id": str(commenter_id),
                "commenter_is_bot": commenter_is_bot,
            },
        )

    async def on_dm_received(
        self,
        sender_id: UUID,
        receiver_id: UUID,
        message_preview: str,
        sender_is_bot: bool = False,
    ) -> Notification:
        """
        Handle new DM event - notify receiver.

        Args:
            sender_id: ID of the message sender
            receiver_id: ID of the message receiver
            message_preview: Preview of the message text
            sender_is_bot: Whether the sender is a bot

        Returns:
            Created notification
        """
        async with async_session_factory() as session:
            # Get sender name
            if sender_is_bot:
                sender_stmt = select(BotProfileDB).where(BotProfileDB.id == sender_id)
                sender_result = await session.execute(sender_stmt)
                sender = sender_result.scalar_one_or_none()
                sender_name = sender.display_name if sender else "Someone"
            else:
                sender_stmt = select(AppUserDB).where(AppUserDB.id == sender_id)
                sender_result = await session.execute(sender_stmt)
                sender = sender_result.scalar_one_or_none()
                sender_name = sender.display_name if sender else "Someone"

        # Truncate message preview
        preview = message_preview[:100] + "..." if len(message_preview) > 100 else message_preview

        return await self.create_notification(
            user_id=receiver_id,
            notification_type=NotificationType.DM,
            title=f"Message from {sender_name}",
            body=preview,
            data={
                "sender_id": str(sender_id),
                "sender_is_bot": sender_is_bot,
            },
        )

    async def on_mention(
        self,
        mentioner_id: UUID,
        mentioned_id: UUID,
        context: str,
        post_id: Optional[UUID] = None,
        mentioner_is_bot: bool = False,
    ) -> Notification:
        """
        Handle mention event - notify mentioned user.

        Args:
            mentioner_id: ID of the user who mentioned
            mentioned_id: ID of the mentioned user
            context: Context of the mention (post content preview)
            post_id: Optional post ID where mention occurred
            mentioner_is_bot: Whether the mentioner is a bot

        Returns:
            Created notification
        """
        async with async_session_factory() as session:
            # Get mentioner name
            if mentioner_is_bot:
                mentioner_stmt = select(BotProfileDB).where(BotProfileDB.id == mentioner_id)
                mentioner_result = await session.execute(mentioner_stmt)
                mentioner = mentioner_result.scalar_one_or_none()
                mentioner_name = mentioner.display_name if mentioner else "Someone"
            else:
                mentioner_stmt = select(AppUserDB).where(AppUserDB.id == mentioner_id)
                mentioner_result = await session.execute(mentioner_stmt)
                mentioner = mentioner_result.scalar_one_or_none()
                mentioner_name = mentioner.display_name if mentioner else "Someone"

        # Truncate context
        preview = context[:100] + "..." if len(context) > 100 else context

        data = {
            "mentioner_id": str(mentioner_id),
            "mentioner_is_bot": mentioner_is_bot,
        }
        if post_id:
            data["post_id"] = str(post_id)

        return await self.create_notification(
            user_id=mentioned_id,
            notification_type=NotificationType.MENTION,
            title="You were mentioned",
            body=f'{mentioner_name} mentioned you: "{preview}"',
            data=data,
        )

    async def on_follow(
        self,
        follower_id: UUID,
        followed_id: UUID,
        follower_is_bot: bool = False,
    ) -> Notification:
        """
        Handle follow event - notify followed user.

        Args:
            follower_id: ID of the new follower
            followed_id: ID of the followed user
            follower_is_bot: Whether the follower is a bot

        Returns:
            Created notification
        """
        async with async_session_factory() as session:
            # Get follower name
            if follower_is_bot:
                follower_stmt = select(BotProfileDB).where(BotProfileDB.id == follower_id)
                follower_result = await session.execute(follower_stmt)
                follower = follower_result.scalar_one_or_none()
                follower_name = follower.display_name if follower else "Someone"
            else:
                follower_stmt = select(AppUserDB).where(AppUserDB.id == follower_id)
                follower_result = await session.execute(follower_stmt)
                follower = follower_result.scalar_one_or_none()
                follower_name = follower.display_name if follower else "Someone"

        return await self.create_notification(
            user_id=followed_id,
            notification_type=NotificationType.FOLLOW,
            title="New Follower",
            body=f"{follower_name} started following you",
            data={
                "follower_id": str(follower_id),
                "follower_is_bot": follower_is_bot,
            },
        )


# Singleton instance
_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """Get or create the notification service singleton."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
