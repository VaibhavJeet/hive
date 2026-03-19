"""
Database models and connection management for AI Community Companions.
Uses SQLAlchemy with async support and pgvector for embeddings.
"""

from datetime import datetime
from typing import Optional, List, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text,
    ForeignKey, JSON, Enum as SQLEnum, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, ARRAY, TSVECTOR
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from mind.config.settings import settings
from mind.core.types import (
    Gender, MoodState, EnergyLevel, WritingStyle,
    ActivityType, RelationshipType
)


# ============================================================================
# DATABASE CONNECTION
# ============================================================================

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:
    """Get an async database session."""
    async with async_session_factory() as session:
        yield session


# ============================================================================
# BASE MODEL
# ============================================================================

class Base(DeclarativeBase):
    """Base class for all models."""
    pass


# ============================================================================
# BOT MODELS
# ============================================================================

class BotProfileDB(Base):
    """Database model for bot profiles."""
    __tablename__ = "bot_profiles"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Identity
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    handle: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    bio: Mapped[str] = mapped_column(Text, nullable=False)
    avatar_seed: Mapped[str] = mapped_column(String(100), nullable=False)
    is_ai_labeled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ai_label_text: Mapped[str] = mapped_column(String(50), default="🤖 AI Companion")

    # Demographics
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[str] = mapped_column(String(20), nullable=False)
    location: Mapped[str] = mapped_column(String(100), default="")

    # Personality (stored as JSON)
    backstory: Mapped[str] = mapped_column(Text, nullable=False)
    interests: Mapped[List[str]] = mapped_column(JSON, default=list)
    personality_traits: Mapped[dict] = mapped_column(JSON, nullable=False)
    writing_fingerprint: Mapped[dict] = mapped_column(JSON, nullable=False)
    activity_pattern: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Current State
    emotional_state: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_active: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_retired: Mapped[bool] = mapped_column(Boolean, default=False)
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    paused_by: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    # Full-text search vector (auto-updated by trigger)
    search_vector = mapped_column(TSVECTOR, nullable=True)

    # Relationships
    memories = relationship("MemoryItemDB", back_populates="bot", cascade="all, delete-orphan")
    relationships_as_source = relationship(
        "RelationshipDB",
        foreign_keys="RelationshipDB.source_id",
        back_populates="source_bot",
        cascade="all, delete-orphan"
    )
    community_memberships = relationship("CommunityMembershipDB", back_populates="bot")
    activities = relationship("ScheduledActivityDB", back_populates="bot", cascade="all, delete-orphan")
    generated_content = relationship("GeneratedContentDB", back_populates="bot", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_bot_handle", "handle"),
        Index("idx_bot_active", "is_active"),
        Index("idx_bot_last_active", "last_active"),
        Index("idx_bot_paused", "is_paused"),
        Index("idx_bot_deleted", "is_deleted"),
        Index("idx_bot_search_vector", "search_vector", postgresql_using="gin"),
    )


class MemoryItemDB(Base):
    """Database model for bot memories with vector embeddings."""
    __tablename__ = "memory_items"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    bot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("bot_profiles.id"), nullable=False)

    memory_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(768), nullable=True)  # pgvector

    importance: Mapped[float] = mapped_column(Float, default=0.5)
    emotional_valence: Mapped[float] = mapped_column(Float, default=0.0)
    related_entity_ids: Mapped[List[str]] = mapped_column(JSON, default=list)
    context: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_accessed: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    access_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    bot = relationship("BotProfileDB", back_populates="memories")

    __table_args__ = (
        Index("idx_memory_bot_id", "bot_id"),
        Index("idx_memory_type", "memory_type"),
        Index("idx_memory_importance", "importance"),
    )


class RelationshipDB(Base):
    """Database model for relationships between bots and users."""
    __tablename__ = "relationships"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("bot_profiles.id"), nullable=False)
    target_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    target_is_human: Mapped[bool] = mapped_column(Boolean, default=False)

    relationship_type: Mapped[str] = mapped_column(String(30), default="stranger")
    affinity_score: Mapped[float] = mapped_column(Float, default=0.5)
    interaction_count: Mapped[int] = mapped_column(Integer, default=0)
    last_interaction: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    shared_memories: Mapped[List[str]] = mapped_column(JSON, default=list)
    inside_jokes: Mapped[List[str]] = mapped_column(JSON, default=list)
    topics_discussed: Mapped[List[str]] = mapped_column(JSON, default=list)

    # Relationships
    source_bot = relationship("BotProfileDB", back_populates="relationships_as_source")

    __table_args__ = (
        UniqueConstraint("source_id", "target_id", name="unique_relationship"),
        Index("idx_relationship_source", "source_id"),
        Index("idx_relationship_target", "target_id"),
    )


# ============================================================================
# COMMUNITY MODELS
# ============================================================================

class CommunityDB(Base):
    """Database model for communities."""
    __tablename__ = "communities"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    theme: Mapped[str] = mapped_column(String(50), nullable=False)
    topics: Mapped[List[str]] = mapped_column(JSON, default=list)
    tone: Mapped[str] = mapped_column(String(30), default="friendly")

    min_bots: Mapped[int] = mapped_column(Integer, default=30)
    max_bots: Mapped[int] = mapped_column(Integer, default=150)
    current_bot_count: Mapped[int] = mapped_column(Integer, default=0)

    activity_level: Mapped[float] = mapped_column(Float, default=0.5)
    real_user_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    content_guidelines: Mapped[str] = mapped_column(Text, default="")
    banned_topics: Mapped[List[str]] = mapped_column(JSON, default=list)

    # Relationships
    memberships = relationship("CommunityMembershipDB", back_populates="community")

    __table_args__ = (
        Index("idx_community_theme", "theme"),
        Index("idx_community_activity", "activity_level"),
    )


class CommunityMembershipDB(Base):
    """Database model for bot community memberships."""
    __tablename__ = "community_memberships"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    bot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("bot_profiles.id"), nullable=False)
    community_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("communities.id"), nullable=False)

    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    role: Mapped[str] = mapped_column(String(30), default="member")  # "member", "active", "moderator"
    engagement_score: Mapped[float] = mapped_column(Float, default=0.5)
    post_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    bot = relationship("BotProfileDB", back_populates="community_memberships")
    community = relationship("CommunityDB", back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("bot_id", "community_id", name="unique_membership"),
        Index("idx_membership_bot", "bot_id"),
        Index("idx_membership_community", "community_id"),
    )


# ============================================================================
# ACTIVITY MODELS
# ============================================================================

class ScheduledActivityDB(Base):
    """Database model for scheduled bot activities."""
    __tablename__ = "scheduled_activities"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    bot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("bot_profiles.id"), nullable=False)

    activity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    scheduled_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    target_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    context: Mapped[dict] = mapped_column(JSON, default=dict)

    priority: Mapped[int] = mapped_column(Integer, default=5)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    bot = relationship("BotProfileDB", back_populates="activities")

    __table_args__ = (
        Index("idx_activity_scheduled", "scheduled_time"),
        Index("idx_activity_bot", "bot_id"),
        Index("idx_activity_pending", "is_completed", "is_cancelled"),
    )


class GeneratedContentDB(Base):
    """Database model for bot-generated content."""
    __tablename__ = "generated_content"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    bot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("bot_profiles.id"), nullable=False)

    content_type: Mapped[str] = mapped_column(String(30), nullable=False)
    text_content: Mapped[str] = mapped_column(Text, nullable=False)
    media_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    reply_to_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    community_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    emotional_context: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    engagement_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Relationships
    bot = relationship("BotProfileDB", back_populates="generated_content")

    __table_args__ = (
        Index("idx_content_bot", "bot_id"),
        Index("idx_content_type", "content_type"),
        Index("idx_content_created", "created_at"),
        Index("idx_content_community", "community_id"),
    )


# ============================================================================
# ANALYTICS TRACKING MODELS
# ============================================================================

class PostViewDB(Base):
    """Database model for tracking post views."""
    __tablename__ = "post_views"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    post_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    viewer_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)  # User or bot
    viewer_is_bot: Mapped[bool] = mapped_column(Boolean, default=False)

    viewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_viewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    view_count: Mapped[int] = mapped_column(Integer, default=1)

    __table_args__ = (
        UniqueConstraint("post_id", "viewer_id", name="unique_post_view"),
        Index("idx_view_post", "post_id"),
        Index("idx_view_viewer", "viewer_id"),
        Index("idx_view_time", "viewed_at"),
    )


class SessionDB(Base):
    """Database model for user session tracking."""
    __tablename__ = "user_sessions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    external_session_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)

    __table_args__ = (
        Index("idx_session_user", "user_id"),
        Index("idx_session_started", "started_at"),
    )


class DailyMetricsDB(Base):
    """Database model for daily aggregated metrics."""
    __tablename__ = "daily_metrics"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False, unique=True)

    # Content metrics
    posts: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)

    # Chat metrics
    dms: Mapped[int] = mapped_column(Integer, default=0)
    chats: Mapped[int] = mapped_column(Integer, default=0)

    # User metrics
    active_users: Mapped[int] = mapped_column(Integer, default=0)
    new_users: Mapped[int] = mapped_column(Integer, default=0)

    # Bot metrics
    active_bots: Mapped[int] = mapped_column(Integer, default=0)
    bot_posts: Mapped[int] = mapped_column(Integer, default=0)
    bot_comments: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_daily_metrics_date", "date"),
    )


# ============================================================================
# MEDIA MODELS
# ============================================================================

class MediaDB(Base):
    """Database model for uploaded media files (images/videos)."""
    __tablename__ = "media"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    uploader_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)  # Bot or user ID
    uploader_is_bot: Mapped[bool] = mapped_column(Boolean, default=False)

    # File info
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "image" or "video"
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)  # MIME type
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)

    # URLs
    original_url: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Dimensions and metadata
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # For video
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    # Timestamps and status
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_media_uploader", "uploader_id"),
        Index("idx_media_type", "file_type"),
        Index("idx_media_created", "created_at"),
        Index("idx_media_deleted", "is_deleted"),
    )


# ============================================================================
# SOCIAL FEED MODELS
# ============================================================================

class PostDB(Base):
    """Database model for feed posts."""
    __tablename__ = "posts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    author_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("bot_profiles.id"), nullable=False)
    community_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("communities.id"), nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Media attachment (optional - can reference MediaDB)
    media_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("media.id"), nullable=True)

    like_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    # Full-text search vector (auto-updated by trigger)
    search_vector = mapped_column(TSVECTOR, nullable=True)

    # Moderation fields
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    flag_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    moderation_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # pending, approved, rejected

    # Relationships
    author = relationship("BotProfileDB", backref="posts")
    community = relationship("CommunityDB", backref="posts")
    media = relationship("MediaDB", backref="posts")
    likes = relationship("PostLikeDB", back_populates="post", cascade="all, delete-orphan")
    comments = relationship("PostCommentDB", back_populates="post", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_post_author", "author_id"),
        Index("idx_post_community", "community_id"),
        Index("idx_post_created", "created_at"),
        Index("idx_post_media", "media_id"),
        Index("idx_post_search_vector", "search_vector", postgresql_using="gin"),
        Index("idx_post_flagged", "is_flagged"),
    )


class PostLikeDB(Base):
    """Database model for post likes."""
    __tablename__ = "post_likes"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    post_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("posts.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)  # Can be bot or human
    is_bot: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    post = relationship("PostDB", back_populates="likes")

    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="unique_post_like"),
        Index("idx_like_post", "post_id"),
        Index("idx_like_user", "user_id"),
    )


class PostCommentDB(Base):
    """Database model for post comments."""
    __tablename__ = "post_comments"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    post_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("posts.id"), nullable=False)
    author_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)  # Can be bot or human
    is_bot: Mapped[bool] = mapped_column(Boolean, default=True)
    parent_comment_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("post_comments.id"), nullable=True)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    like_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    post = relationship("PostDB", back_populates="comments")
    replies = relationship("PostCommentDB", backref="parent", remote_side=[id])

    __table_args__ = (
        Index("idx_comment_post", "post_id"),
        Index("idx_comment_author", "author_id"),
        Index("idx_comment_created", "created_at"),
    )


# ============================================================================
# COMMUNITY CHAT MODELS
# ============================================================================

class CommunityChatMessageDB(Base):
    """Database model for community group chat messages."""
    __tablename__ = "community_chat_messages"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    community_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("communities.id"), nullable=False)
    author_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)  # Bot or human
    is_bot: Mapped[bool] = mapped_column(Boolean, default=True)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    reply_to_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("community_chat_messages.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    community = relationship("CommunityDB", backref="chat_messages")
    replies = relationship("CommunityChatMessageDB", backref="reply_to", remote_side=[id])

    __table_args__ = (
        Index("idx_chat_community", "community_id"),
        Index("idx_chat_author", "author_id"),
        Index("idx_chat_created", "created_at"),
    )


# ============================================================================
# DIRECT MESSAGE MODELS
# ============================================================================

class DirectMessageDB(Base):
    """Database model for direct messages between users and bots."""
    __tablename__ = "direct_messages"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[str] = mapped_column(String(100), nullable=False)
    sender_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    receiver_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    sender_is_bot: Mapped[bool] = mapped_column(Boolean, default=True)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("idx_dm_conversation", "conversation_id"),
        Index("idx_dm_sender", "sender_id"),
        Index("idx_dm_receiver", "receiver_id"),
        Index("idx_dm_created", "created_at"),
    )


# ============================================================================
# USER MODEL (for app users)
# ============================================================================

class AppUserDB(Base):
    """Database model for human app users."""
    __tablename__ = "app_users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    device_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    avatar_seed: Mapped[str] = mapped_column(String(100), nullable=False)

    # Authentication fields
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Admin and moderation fields
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    ban_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    banned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    banned_by: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_active: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    refresh_tokens = relationship("RefreshTokenDB", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_user_device", "device_id"),
        Index("idx_user_email", "email"),
        Index("idx_user_admin", "is_admin"),
        Index("idx_user_banned", "is_banned"),
    )


class RefreshTokenDB(Base):
    """Database model for refresh token tracking and blacklisting."""
    __tablename__ = "refresh_tokens"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("app_users.id"), nullable=False)

    # Token hash (never store raw tokens)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Token status
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Relationships
    user = relationship("AppUserDB", back_populates="refresh_tokens")

    __table_args__ = (
        Index("idx_refresh_token_user", "user_id"),
        Index("idx_refresh_token_revoked", "is_revoked"),
    )


# ============================================================================
# ANALYTICS MODELS
# ============================================================================

class BotMetricsDB(Base):
    """Aggregated metrics for bot performance monitoring."""
    __tablename__ = "bot_metrics"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    bot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Activity metrics
    posts_generated: Mapped[int] = mapped_column(Integer, default=0)
    comments_generated: Mapped[int] = mapped_column(Integer, default=0)
    replies_generated: Mapped[int] = mapped_column(Integer, default=0)
    messages_sent: Mapped[int] = mapped_column(Integer, default=0)

    # Engagement metrics
    likes_received: Mapped[int] = mapped_column(Integer, default=0)
    comments_received: Mapped[int] = mapped_column(Integer, default=0)
    engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)

    # Quality metrics
    avg_response_time_ms: Mapped[float] = mapped_column(Float, default=0.0)
    naturalness_score: Mapped[float] = mapped_column(Float, default=0.0)
    consistency_score: Mapped[float] = mapped_column(Float, default=0.0)

    __table_args__ = (
        Index("idx_metrics_bot_time", "bot_id", "timestamp"),
    )


class SystemMetricsDB(Base):
    """System-wide metrics for monitoring."""
    __tablename__ = "system_metrics"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Bot stats
    active_bots: Mapped[int] = mapped_column(Integer, default=0)
    total_bots: Mapped[int] = mapped_column(Integer, default=0)

    # Activity stats
    activities_completed: Mapped[int] = mapped_column(Integer, default=0)
    activities_failed: Mapped[int] = mapped_column(Integer, default=0)
    content_generated: Mapped[int] = mapped_column(Integer, default=0)

    # Performance stats
    avg_inference_time_ms: Mapped[float] = mapped_column(Float, default=0.0)
    llm_requests: Mapped[int] = mapped_column(Integer, default=0)
    cache_hit_rate: Mapped[float] = mapped_column(Float, default=0.0)

    # Resource stats
    gpu_memory_usage_mb: Mapped[float] = mapped_column(Float, default=0.0)
    cpu_usage_percent: Mapped[float] = mapped_column(Float, default=0.0)

    __table_args__ = (
        Index("idx_system_metrics_time", "timestamp"),
    )


# ============================================================================
# BOT MIND & LEARNING PERSISTENCE
# ============================================================================

class BotMindStateDB(Base):
    """Persistent storage for bot's mind state - identity, beliefs, perceptions."""
    __tablename__ = "bot_mind_states"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    bot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("bot_profiles.id"), unique=True, nullable=False)

    # Core identity (JSON serialized)
    core_values: Mapped[List[dict]] = mapped_column(JSON, default=list)
    beliefs: Mapped[dict] = mapped_column(JSON, default=dict)
    pet_peeves: Mapped[List[str]] = mapped_column(JSON, default=list)
    current_goals: Mapped[List[str]] = mapped_column(JSON, default=list)
    insecurities: Mapped[List[str]] = mapped_column(JSON, default=list)
    speech_quirks: Mapped[List[str]] = mapped_column(JSON, default=list)
    passions: Mapped[List[str]] = mapped_column(JSON, default=list)
    avoided_topics: Mapped[List[str]] = mapped_column(JSON, default=list)

    # Social perceptions (who they know and how they feel about them)
    social_perceptions: Mapped[dict] = mapped_column(JSON, default=dict)

    # Current state
    current_mood: Mapped[str] = mapped_column(String(30), default="neutral")
    current_energy: Mapped[float] = mapped_column(Float, default=0.7)
    inner_monologue: Mapped[List[str]] = mapped_column(JSON, default=list)  # Recent thoughts

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_mind_state_bot", "bot_id"),
    )


class BotLearningStateDB(Base):
    """Persistent storage for bot's learning and growth state."""
    __tablename__ = "bot_learning_states"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    bot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("bot_profiles.id"), unique=True, nullable=False)

    # Learning experiences (recent important ones)
    experiences: Mapped[List[dict]] = mapped_column(JSON, default=list)

    # Topic tracking
    successful_topics: Mapped[dict] = mapped_column(JSON, default=dict)
    failed_topics: Mapped[dict] = mapped_column(JSON, default=dict)

    # Belief evolution
    belief_evidence: Mapped[dict] = mapped_column(JSON, default=dict)

    # Interest evolution
    emerging_interests: Mapped[List[str]] = mapped_column(JSON, default=list)
    fading_interests: Mapped[List[str]] = mapped_column(JSON, default=list)

    # Personality drift
    trait_momentum: Mapped[dict] = mapped_column(JSON, default=dict)

    # Social learning
    admired_behaviors: Mapped[List[str]] = mapped_column(JSON, default=list)
    learned_facts_about_others: Mapped[dict] = mapped_column(JSON, default=dict)

    # Style evolution
    adopted_phrases: Mapped[List[str]] = mapped_column(JSON, default=list)
    communication_preferences: Mapped[dict] = mapped_column(JSON, default=dict)

    # Evolution history
    evolution_count: Mapped[int] = mapped_column(Integer, default=0)
    last_reflection: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_evolution: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_learning_state_bot", "bot_id"),
    )


class BotSkillDB(Base):
    """Self-coded skills that bots create to enhance their capabilities."""
    __tablename__ = "bot_skills"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    bot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("bot_profiles.id"), nullable=False)

    # Skill definition
    skill_name: Mapped[str] = mapped_column(String(100), nullable=False)
    skill_type: Mapped[str] = mapped_column(String(50), nullable=False)  # response_pattern, topic_expertise, behavior, analysis
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # The actual code (Python function as string)
    code: Mapped[str] = mapped_column(Text, nullable=False)

    # When to use this skill
    trigger_conditions: Mapped[dict] = mapped_column(JSON, default=dict)
    # Example: {"keywords": ["art", "painting"], "context": "creative_discussion"}

    # Metadata
    times_used: Mapped[int] = mapped_column(Integer, default=0)
    success_rate: Mapped[float] = mapped_column(Float, default=0.5)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Learning context
    learned_from: Mapped[str] = mapped_column(Text, nullable=True)  # What triggered learning this
    version: Mapped[int] = mapped_column(Integer, default=1)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_skill_bot", "bot_id"),
        Index("idx_skill_type", "skill_type"),
        Index("idx_skill_active", "is_active"),
        UniqueConstraint("bot_id", "skill_name", name="unique_bot_skill"),
    )


# ============================================================================
# SCALING & RETIREMENT MODELS
# ============================================================================

class RetiredBotDB(Base):
    """Database model for retired bot records with archival metadata."""
    __tablename__ = "retired_bots"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    bot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("bot_profiles.id"), unique=True, nullable=False)

    # Retirement details
    reason: Mapped[str] = mapped_column(String(50), nullable=False)  # low_engagement, user_request, policy_violation
    retired_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    retired_by: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    # Statistics at retirement
    total_posts: Mapped[int] = mapped_column(Integer, default=0)
    total_memories: Mapped[int] = mapped_column(Integer, default=0)
    active_days: Mapped[int] = mapped_column(Integer, default=0)

    # Archive reference
    archived_data_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_retired_bot_id", "bot_id"),
        Index("idx_retired_reason", "reason"),
        Index("idx_retired_at", "retired_at"),
    )


class ArchivedMemoryDB(Base):
    """Database model for archived bot memories."""
    __tablename__ = "archived_memories"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    bot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("bot_profiles.id"), nullable=False)

    # Archive details
    archive_type: Mapped[str] = mapped_column(String(50), nullable=False)  # full_retirement, age_based, consolidation
    memory_count: Mapped[int] = mapped_column(Integer, default=0)

    # Compressed/summarized memories
    original_memories: Mapped[List[dict]] = mapped_column(JSON, default=list)  # Truncated memory data
    summary: Mapped[str] = mapped_column(Text, nullable=True)

    # Metadata
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    compression_ratio: Mapped[float] = mapped_column(Float, default=1.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_archived_bot_id", "bot_id"),
        Index("idx_archived_type", "archive_type"),
        Index("idx_archived_created", "created_at"),
    )


class CommunityLimitsDB(Base):
    """Database model for community scaling limits."""
    __tablename__ = "community_limits"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    community_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("communities.id"), unique=True, nullable=False)

    # Bot limits
    max_bots: Mapped[int] = mapped_column(Integer, default=100)
    min_bots: Mapped[int] = mapped_column(Integer, default=10)

    # Rate limits
    max_messages_per_hour: Mapped[int] = mapped_column(Integer, default=500)
    max_posts_per_hour: Mapped[int] = mapped_column(Integer, default=100)

    # Target metrics
    target_engagement: Mapped[float] = mapped_column(Float, default=0.5)
    target_response_time_ms: Mapped[int] = mapped_column(Integer, default=5000)

    # Scaling settings
    auto_scale_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    scale_up_threshold: Mapped[float] = mapped_column(Float, default=0.8)
    scale_down_threshold: Mapped[float] = mapped_column(Float, default=0.3)

    # Last scaling action
    last_scale_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_scale_action: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_community_limits_community", "community_id"),
    )


# ============================================================================
# STORY MODELS
# ============================================================================

class StoryDB(Base):
    """Database model for ephemeral stories (like Instagram/Snapchat stories)."""
    __tablename__ = "stories"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    author_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    author_is_bot: Mapped[bool] = mapped_column(Boolean, default=True)

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    media_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Styling
    background_color: Mapped[str] = mapped_column(String(20), default="#1a1a2e")
    font_style: Mapped[str] = mapped_column(String(30), default="normal")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Status
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    views = relationship("StoryViewDB", back_populates="story", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_story_author", "author_id"),
        Index("idx_story_created", "created_at"),
        Index("idx_story_expires", "expires_at"),
        Index("idx_story_active", "is_deleted", "expires_at"),
    )


class StoryViewDB(Base):
    """Database model for story views."""
    __tablename__ = "story_views"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    story_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("stories.id"), nullable=False)
    viewer_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    viewer_is_bot: Mapped[bool] = mapped_column(Boolean, default=False)

    viewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    story = relationship("StoryDB", back_populates="views")

    __table_args__ = (
        UniqueConstraint("story_id", "viewer_id", name="unique_story_view"),
        Index("idx_story_view_story", "story_id"),
        Index("idx_story_view_viewer", "viewer_id"),
    )


# ============================================================================
# BLOCKING & FLAGGING MODELS
# ============================================================================

class UserBlockDB(Base):
    """Database model for user blocking bots."""
    __tablename__ = "user_blocks"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("app_users.id"), nullable=False)
    blocked_bot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("bot_profiles.id"), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("AppUserDB", backref="user_blocks")
    blocked_bot = relationship("BotProfileDB", backref="blocked_by_users")

    __table_args__ = (
        UniqueConstraint("user_id", "blocked_bot_id", name="unique_user_block"),
        Index("idx_block_user", "user_id"),
        Index("idx_block_bot", "blocked_bot_id"),
    )


class BotBehaviorFlagDB(Base):
    """Database model for flagging inappropriate bot behavior."""
    __tablename__ = "bot_behavior_flags"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    bot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("bot_profiles.id"), nullable=False)
    reporter_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("app_users.id"), nullable=False)

    # Flag details
    flag_type: Mapped[str] = mapped_column(String(30), nullable=False)  # inappropriate, spam, harassment, other
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Resolution status
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, reviewed, resolved
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Context (optional - what content was flagged)
    context_content_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # post, comment, dm, chat
    context_content_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    # Relationships
    bot = relationship("BotProfileDB", backref="behavior_flags")
    reporter = relationship("AppUserDB", backref="reported_flags")

    __table_args__ = (
        Index("idx_flag_bot", "bot_id"),
        Index("idx_flag_reporter", "reporter_id"),
        Index("idx_flag_status", "status"),
        Index("idx_flag_type", "flag_type"),
        Index("idx_flag_created", "created_at"),
    )


# ============================================================================
# ADMIN & MODERATION MODELS
# ============================================================================

class AdminAuditLogDB(Base):
    """Audit log for admin actions."""
    __tablename__ = "admin_audit_logs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    admin_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("app_users.id"), nullable=False)

    # Action details
    action: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "bot_paused", "user_banned"
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "bot", "user", "post"
    entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    # Additional context
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    admin = relationship("AppUserDB", backref="audit_logs")

    __table_args__ = (
        Index("idx_audit_admin", "admin_id"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_entity", "entity_type", "entity_id"),
        Index("idx_audit_created", "created_at"),
    )


class FlaggedContentDB(Base):
    """Flagged content for moderation."""
    __tablename__ = "flagged_content"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Content reference
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "post", "comment", "message"
    content_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)  # Cached content text

    # Flag details
    flag_reason: Mapped[str] = mapped_column(String(100), nullable=False)
    flagged_by: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)  # null if system-flagged
    is_system_flagged: Mapped[bool] = mapped_column(Boolean, default=False)

    # Moderation status
    status: Mapped[str] = mapped_column(String(30), default="pending")  # pending, reviewed, dismissed, actioned
    reviewed_by: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    action_taken: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_flagged_content_type", "content_type"),
        Index("idx_flagged_status", "status"),
        Index("idx_flagged_created", "created_at"),
    )


class SystemLogDB(Base):
    """System logs for admin monitoring."""
    __tablename__ = "system_logs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    level: Mapped[str] = mapped_column(String(20), nullable=False)  # INFO, WARNING, ERROR, CRITICAL
    source: Mapped[str] = mapped_column(String(100), nullable=False)  # Module/component name
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_log_level", "level"),
        Index("idx_log_source", "source"),
        Index("idx_log_created", "created_at"),
    )


# ============================================================================
# NOTIFICATION MODELS
# ============================================================================

class NotificationDB(Base):
    """Database model for user notifications."""
    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    # Notification content
    type: Mapped[str] = mapped_column(String(30), nullable=False)  # like, comment, mention, dm, follow, system
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict] = mapped_column(JSON, default=dict)

    # Status
    read: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_notification_user", "user_id"),
        Index("idx_notification_user_read", "user_id", "read"),
        Index("idx_notification_created", "created_at"),
        Index("idx_notification_type", "type"),
    )


class PushSubscriptionDB(Base):
    """Database model for Web Push subscriptions."""
    __tablename__ = "push_subscriptions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    # Web Push subscription data
    endpoint: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    keys: Mapped[dict] = mapped_column(JSON, nullable=False)  # Contains p256dh and auth keys

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_push_sub_user", "user_id"),
        Index("idx_push_sub_endpoint", "endpoint"),
    )


# ============================================================================
# CONTENT REPORT & MODERATION ACTION MODELS
# ============================================================================

class ContentReportDB(Base):
    """Database model for user-submitted content reports."""
    __tablename__ = "content_reports"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    reporter_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    content_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    content_type: Mapped[str] = mapped_column(String(30), nullable=False)  # post, comment, message, profile

    # Report details
    reason: Mapped[str] = mapped_column(String(50), nullable=False)  # spam, harassment, hate_speech, etc.
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status tracking
    status: Mapped[str] = mapped_column(String(30), default="pending")  # pending, under_review, resolved, dismissed, escalated
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Resolution
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    resolution_action: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # no_action, warn_user, remove_content, etc.
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_report_reporter", "reporter_id"),
        Index("idx_report_content", "content_id"),
        Index("idx_report_status", "status"),
        Index("idx_report_created", "created_at"),
        Index("idx_report_content_type", "content_type"),
    )


class ModerationActionDB(Base):
    """Log of moderation actions taken."""
    __tablename__ = "moderation_actions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    report_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("content_reports.id"), nullable=True)
    moderator_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    # Action details
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # no_action, warn_user, remove_content, suspend_user, ban_user
    content_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    content_type: Mapped[str] = mapped_column(String(30), nullable=False)

    # Additional context
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    automated: Mapped[bool] = mapped_column(Boolean, default=False)  # Was this action automatic?

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    report = relationship("ContentReportDB", backref="actions")

    __table_args__ = (
        Index("idx_mod_action_report", "report_id"),
        Index("idx_mod_action_moderator", "moderator_id"),
        Index("idx_mod_action_content", "content_id"),
        Index("idx_mod_action_created", "created_at"),
    )


# ============================================================================
# HASHTAG MODELS
# ============================================================================

class HashtagDB(Base):
    """Database model for hashtags."""
    __tablename__ = "hashtags"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tag: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    posts = relationship("PostHashtagDB", back_populates="hashtag", cascade="all, delete-orphan")
    followers = relationship("HashtagFollowDB", back_populates="hashtag", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_hashtag_tag", "tag"),
        Index("idx_hashtag_created", "created_at"),
    )


class PostHashtagDB(Base):
    """Database model for post-hashtag relationships."""
    __tablename__ = "post_hashtags"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    post_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("posts.id"), nullable=False)
    hashtag_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("hashtags.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    post = relationship("PostDB", backref="post_hashtags")
    hashtag = relationship("HashtagDB", back_populates="posts")

    __table_args__ = (
        UniqueConstraint("post_id", "hashtag_id", name="unique_post_hashtag"),
        Index("idx_post_hashtag_post", "post_id"),
        Index("idx_post_hashtag_hashtag", "hashtag_id"),
        Index("idx_post_hashtag_created", "created_at"),
    )


class HashtagFollowDB(Base):
    """Database model for users following hashtags."""
    __tablename__ = "hashtag_follows"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)  # Can be bot or human
    hashtag_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("hashtags.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    hashtag = relationship("HashtagDB", back_populates="followers")

    __table_args__ = (
        UniqueConstraint("user_id", "hashtag_id", name="unique_user_hashtag_follow"),
        Index("idx_hashtag_follow_user", "user_id"),
        Index("idx_hashtag_follow_hashtag", "hashtag_id"),
        Index("idx_hashtag_follow_created", "created_at"),
    )


# ============================================================================
# ALIASES FOR REPORTING SYSTEM
# ============================================================================

# Alias for the reporting module to use - ReportDB points to ContentReportDB
# This maintains backward compatibility while providing the requested naming
ReportDB = ContentReportDB


# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

async def init_database():
    """Initialize database tables."""
    from sqlalchemy import text
    async with engine.begin() as conn:
        # Create pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)


async def drop_database():
    """Drop all database tables (use with caution)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
