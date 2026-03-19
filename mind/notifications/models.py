"""
Notification data models and enums.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID, uuid4


class NotificationType(str, Enum):
    """Types of notifications that can be sent."""
    # Engagement notifications
    LIKE = "like"
    COMMENT = "comment"
    MENTION = "mention"

    # Social notifications
    DM = "dm"
    NEW_MESSAGE = "new_message"
    FOLLOW = "follow"
    NEW_FOLLOWER = "new_follower"

    # Content notifications
    NEW_POST = "new_post"
    NEW_LIKE = "new_like"
    NEW_COMMENT = "new_comment"
    HASHTAG = "hashtag"  # New post in followed hashtag
    TRENDING = "trending"  # Content is trending

    # System notifications
    SYSTEM = "system"
    ACCOUNT = "account"  # Account-related (verification, security)
    PROMOTION = "promotion"  # Marketing/promotional
    UPDATE = "update"  # App update notifications


@dataclass
class Notification:
    """
    Represents a notification for a user.

    Attributes:
        id: Unique notification identifier
        user_id: The user this notification is for
        type: Type of notification (like, comment, etc.)
        title: Notification title
        body: Notification body text
        data: Additional data payload (e.g., post_id, sender_id)
        read: Whether the notification has been read
        created_at: When the notification was created
    """
    user_id: UUID
    type: NotificationType
    title: str
    body: str
    data: Dict[str, Any] = field(default_factory=dict)
    read: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    id: UUID = field(default_factory=uuid4)

    def to_dict(self) -> Dict[str, Any]:
        """Convert notification to dictionary."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "type": self.type.value,
            "title": self.title,
            "body": self.body,
            "data": self.data,
            "read": self.read,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Notification":
        """Create notification from dictionary."""
        return cls(
            id=UUID(data["id"]) if isinstance(data.get("id"), str) else data.get("id", uuid4()),
            user_id=UUID(data["user_id"]) if isinstance(data["user_id"], str) else data["user_id"],
            type=NotificationType(data["type"]),
            title=data["title"],
            body=data["body"],
            data=data.get("data", {}),
            read=data.get("read", False),
            created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data.get("created_at"), str) else data.get("created_at", datetime.utcnow()),
        )


@dataclass
class PushSubscription:
    """
    Web Push subscription information for a user's device.

    Attributes:
        user_id: The user this subscription belongs to
        endpoint: Push service endpoint URL
        keys: Authentication keys (p256dh and auth)
        created_at: When the subscription was created
    """
    user_id: UUID
    endpoint: str
    keys: Dict[str, str]
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert subscription to dictionary."""
        return {
            "user_id": str(self.user_id),
            "endpoint": self.endpoint,
            "keys": self.keys,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PushSubscription":
        """Create subscription from dictionary."""
        return cls(
            user_id=UUID(data["user_id"]) if isinstance(data["user_id"], str) else data["user_id"],
            endpoint=data["endpoint"],
            keys=data["keys"],
            created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data.get("created_at"), str) else data.get("created_at", datetime.utcnow()),
        )
