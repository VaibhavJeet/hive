"""
Notifications API routes - Push notifications and notification management.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from mind.notifications.notification_service import (
    get_notification_service,
    NotificationService,
)
from mind.notifications.push_service import get_push_service, PushService
from mind.notifications.models import NotificationType


router = APIRouter(prefix="/notifications", tags=["notifications"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class NotificationResponse(BaseModel):
    """Response model for a notification."""
    id: UUID
    user_id: UUID
    type: str
    title: str
    body: str
    data: dict
    read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    """Response model for notification list."""
    notifications: List[NotificationResponse]
    unread_count: int
    total: int


class MarkReadResponse(BaseModel):
    """Response model for marking notifications as read."""
    success: bool
    marked_count: int


class PushSubscriptionRequest(BaseModel):
    """Request model for registering push subscription."""
    endpoint: str = Field(..., description="Push service endpoint URL")
    keys: dict = Field(
        ...,
        description="Subscription keys containing p256dh and auth",
        examples=[{"p256dh": "...", "auth": "..."}]
    )


class PushSubscriptionResponse(BaseModel):
    """Response model for push subscription."""
    success: bool
    message: str


class PushConfigResponse(BaseModel):
    """Response model for push notification configuration."""
    enabled: bool
    vapid_public_key: Optional[str]


# ============================================================================
# NOTIFICATION ENDPOINTS
# ============================================================================

@router.get("", response_model=NotificationListResponse)
async def get_notifications(
    user_id: UUID,
    unread_only: bool = Query(default=False, description="Only return unread notifications"),
    limit: int = Query(default=50, le=100, description="Maximum notifications to return"),
    offset: int = Query(default=0, ge=0, description="Number of notifications to skip"),
):
    """
    Get notifications for a user.

    Returns a paginated list of notifications with unread count.
    """
    service = get_notification_service()

    notifications = await service.get_notifications(
        user_id=user_id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )

    unread_count = await service.get_unread_count(user_id)

    return NotificationListResponse(
        notifications=[
            NotificationResponse(
                id=n.id,
                user_id=n.user_id,
                type=n.type.value,
                title=n.title,
                body=n.body,
                data=n.data,
                read=n.read,
                created_at=n.created_at,
            )
            for n in notifications
        ],
        unread_count=unread_count,
        total=len(notifications),
    )


@router.get("/unread-count")
async def get_unread_count(user_id: UUID):
    """Get count of unread notifications for a user."""
    service = get_notification_service()
    count = await service.get_unread_count(user_id)
    return {"unread_count": count}


@router.post("/{notification_id}/read", response_model=MarkReadResponse)
async def mark_notification_read(notification_id: UUID):
    """
    Mark a single notification as read.
    """
    service = get_notification_service()
    success = await service.mark_as_read(notification_id)

    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")

    return MarkReadResponse(success=True, marked_count=1)


@router.post("/read-all", response_model=MarkReadResponse)
async def mark_all_notifications_read(user_id: UUID):
    """
    Mark all notifications for a user as read.
    """
    service = get_notification_service()
    count = await service.mark_all_read(user_id)

    return MarkReadResponse(success=True, marked_count=count)


@router.delete("/{notification_id}")
async def delete_notification(notification_id: UUID):
    """
    Delete a notification.
    """
    service = get_notification_service()
    success = await service.delete_notification(notification_id)

    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")

    return {"success": True, "message": "Notification deleted"}


@router.delete("")
async def delete_all_notifications(user_id: UUID):
    """
    Delete all notifications for a user.
    """
    service = get_notification_service()
    count = await service.delete_all_notifications(user_id)

    return {"success": True, "deleted_count": count}


# ============================================================================
# PUSH SUBSCRIPTION ENDPOINTS
# ============================================================================

@router.get("/push/config", response_model=PushConfigResponse)
async def get_push_config():
    """
    Get push notification configuration.

    Returns the VAPID public key needed for client-side subscription.
    """
    push_service = get_push_service()

    return PushConfigResponse(
        enabled=push_service.is_enabled,
        vapid_public_key=push_service.public_key,
    )


@router.post("/subscribe", response_model=PushSubscriptionResponse)
async def subscribe_to_push(
    user_id: UUID,
    request: PushSubscriptionRequest,
):
    """
    Register a push notification subscription for a user's device.

    The client should call this after getting permission for push notifications
    and receiving a subscription from the browser's Push API.
    """
    push_service = get_push_service()

    if not push_service.is_enabled:
        raise HTTPException(
            status_code=503,
            detail="Push notifications are not configured on this server"
        )

    # Validate keys
    if "p256dh" not in request.keys or "auth" not in request.keys:
        raise HTTPException(
            status_code=400,
            detail="Subscription keys must contain 'p256dh' and 'auth'"
        )

    await push_service.register_device(
        user_id=user_id,
        subscription={
            "endpoint": request.endpoint,
            "keys": request.keys,
        },
    )

    return PushSubscriptionResponse(
        success=True,
        message="Push subscription registered successfully",
    )


@router.delete("/subscribe", response_model=PushSubscriptionResponse)
async def unsubscribe_from_push(
    user_id: UUID,
    endpoint: str = Query(..., description="Push service endpoint URL to unregister"),
):
    """
    Unregister a push notification subscription.

    Call this when the user revokes notification permission or logs out.
    """
    push_service = get_push_service()

    success = await push_service.unregister_device(
        user_id=user_id,
        endpoint=endpoint,
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found"
        )

    return PushSubscriptionResponse(
        success=True,
        message="Push subscription removed successfully",
    )


# ============================================================================
# INTERNAL/ADMIN ENDPOINTS
# ============================================================================

@router.post("/send")
async def send_notification(
    user_id: UUID,
    type: str,
    title: str,
    body: str,
    data: Optional[dict] = None,
):
    """
    Send a notification to a user (admin/internal use).

    This endpoint can be used for testing or for system notifications.
    """
    try:
        notification_type = NotificationType(type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid notification type. Must be one of: {[t.value for t in NotificationType]}"
        )

    service = get_notification_service()

    # Attach push service if available
    push_service = get_push_service()
    if push_service.is_enabled:
        service.set_push_service(push_service)

    notification = await service.create_notification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        body=body,
        data=data,
    )

    return {
        "success": True,
        "notification_id": str(notification.id),
    }
