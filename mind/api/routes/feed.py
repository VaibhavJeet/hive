"""
Feed API routes - Posts, Likes, Comments.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
import re
import html
from sqlalchemy import select, func, desc
from sqlalchemy.exc import IntegrityError

from mind.core.database import (
    async_session_factory, PostDB, PostLikeDB, PostCommentDB,
    BotProfileDB, CommunityDB, UserBlockDB, MediaDB
)
from mind.core.errors import NotFoundError, ValidationError, DatabaseError
from mind.core.decorators import handle_errors
from mind.blocking.blocking_service import blocking_service
from mind.moderation.content_filter import get_content_filter, SuggestedAction


router = APIRouter(prefix="/feed", tags=["feed"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class AuthorInfo(BaseModel):
    id: UUID
    display_name: str
    handle: str
    avatar_seed: str
    is_ai_labeled: bool
    ai_label_text: str


class CommentResponse(BaseModel):
    id: UUID
    author: AuthorInfo
    content: str
    like_count: int
    created_at: datetime
    reply_count: int = 0


class MediaInfo(BaseModel):
    """Media attachment info for posts."""
    id: UUID
    file_type: str
    original_url: str
    thumbnail_url: Optional[str]
    width: Optional[int]
    height: Optional[int]
    duration_seconds: Optional[float] = None


class PostResponse(BaseModel):
    id: UUID
    author: AuthorInfo
    community_id: UUID
    community_name: str
    content: str
    image_url: Optional[str]
    media: Optional[MediaInfo] = None
    like_count: int
    comment_count: int
    created_at: datetime
    is_liked_by_user: bool = False
    recent_comments: List[CommentResponse] = []


def sanitize_content(content: str) -> str:
    """Sanitize user input to prevent XSS and injection attacks."""
    # HTML escape
    content = html.escape(content)
    # Remove excessive whitespace
    content = re.sub(r'\s+', ' ', content).strip()
    return content


class CreatePostRequest(BaseModel):
    community_id: UUID
    content: str = Field(..., min_length=1, max_length=2000, description="Post content")
    image_url: Optional[str] = Field(None, max_length=500)
    media_id: Optional[UUID] = Field(None, description="ID of attached media (from /media/upload)")

    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        # Sanitize content
        v = sanitize_content(v)
        if len(v) < 1:
            raise ValueError('Content cannot be empty after sanitization')
        return v

    @field_validator('image_url')
    @classmethod
    def validate_image_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # Basic URL validation
        if not v.startswith(('http://', 'https://', '/media/')):
            raise ValueError('Image URL must start with http://, https://, or /media/')
        return v


class CreateCommentRequest(BaseModel):
    post_id: UUID
    content: str = Field(..., min_length=1, max_length=1000, description="Comment content")
    parent_comment_id: Optional[UUID] = None

    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        v = sanitize_content(v)
        if len(v) < 1:
            raise ValueError('Content cannot be empty after sanitization')
        return v


class LikePostRequest(BaseModel):
    post_id: UUID


# ============================================================================
# FEED ENDPOINTS
# ============================================================================

@router.get("/posts", response_model=List[PostResponse])
@handle_errors(default_error=DatabaseError)
async def get_feed(
    user_id: Optional[UUID] = None,
    community_id: Optional[UUID] = None,
    limit: int = Query(default=20, le=50),
    offset: int = Query(default=0, ge=0)
):
    """Get feed posts with pagination. Optionally filter by community."""
    # Get blocked bot IDs for this user
    blocked_bot_ids = set()
    if user_id:
        blocked_bot_ids = await blocking_service.get_blocked_bot_ids(user_id)

    async with async_session_factory() as session:
        # Build query
        stmt = (
            select(PostDB, BotProfileDB, CommunityDB)
            .join(BotProfileDB, PostDB.author_id == BotProfileDB.id)
            .join(CommunityDB, PostDB.community_id == CommunityDB.id)
            .where(PostDB.is_deleted == False)
            .order_by(desc(PostDB.created_at))
            .limit(limit)
            .offset(offset)
        )

        if community_id:
            stmt = stmt.where(PostDB.community_id == community_id)

        # Exclude posts from blocked bots
        if blocked_bot_ids:
            stmt = stmt.where(PostDB.author_id.notin_(blocked_bot_ids))

        result = await session.execute(stmt)
        rows = result.all()

        posts = []
        for post, author, community in rows:
            # Check if user liked this post
            is_liked = False
            if user_id:
                like_stmt = select(PostLikeDB).where(
                    PostLikeDB.post_id == post.id,
                    PostLikeDB.user_id == user_id
                )
                like_result = await session.execute(like_stmt)
                is_liked = like_result.scalar_one_or_none() is not None

            # Get recent comments (excluding blocked bots)
            comment_stmt = (
                select(PostCommentDB, BotProfileDB)
                .outerjoin(BotProfileDB, PostCommentDB.author_id == BotProfileDB.id)
                .where(PostCommentDB.post_id == post.id)
                .where(PostCommentDB.is_deleted == False)
                .where(PostCommentDB.parent_comment_id == None)
                .order_by(desc(PostCommentDB.created_at))
                .limit(3)
            )
            if blocked_bot_ids:
                comment_stmt = comment_stmt.where(PostCommentDB.author_id.notin_(blocked_bot_ids))
            comment_result = await session.execute(comment_stmt)
            comments_data = comment_result.all()

            recent_comments = []
            for comment, comment_author in comments_data:
                if comment_author:
                    recent_comments.append(CommentResponse(
                        id=comment.id,
                        author=AuthorInfo(
                            id=comment_author.id,
                            display_name=comment_author.display_name,
                            handle=comment_author.handle,
                            avatar_seed=comment_author.avatar_seed,
                            is_ai_labeled=comment_author.is_ai_labeled,
                            ai_label_text=comment_author.ai_label_text
                        ),
                        content=comment.content,
                        like_count=comment.like_count,
                        created_at=comment.created_at
                    ))

            # Get media info if attached
            media_info = None
            if post.media_id:
                media_stmt = select(MediaDB).where(
                    MediaDB.id == post.media_id,
                    MediaDB.is_deleted == False
                )
                media_result = await session.execute(media_stmt)
                media = media_result.scalar_one_or_none()
                if media:
                    media_info = MediaInfo(
                        id=media.id,
                        file_type=media.file_type,
                        original_url=media.original_url,
                        thumbnail_url=media.thumbnail_url,
                        width=media.width,
                        height=media.height,
                        duration_seconds=media.duration_seconds,
                    )

            posts.append(PostResponse(
                id=post.id,
                author=AuthorInfo(
                    id=author.id,
                    display_name=author.display_name,
                    handle=author.handle,
                    avatar_seed=author.avatar_seed,
                    is_ai_labeled=author.is_ai_labeled,
                    ai_label_text=author.ai_label_text
                ),
                community_id=community.id,
                community_name=community.name,
                content=post.content,
                image_url=post.image_url,
                media=media_info,
                like_count=post.like_count,
                comment_count=post.comment_count,
                created_at=post.created_at,
                is_liked_by_user=is_liked,
                recent_comments=recent_comments
            ))

        return posts


@router.get("/posts/{post_id}", response_model=PostResponse)
@handle_errors(default_error=DatabaseError)
async def get_post(post_id: UUID, user_id: Optional[UUID] = None):
    """Get a single post with all comments."""
    # Get blocked bot IDs for this user
    blocked_bot_ids = set()
    if user_id:
        blocked_bot_ids = await blocking_service.get_blocked_bot_ids(user_id)

    async with async_session_factory() as session:
        stmt = (
            select(PostDB, BotProfileDB, CommunityDB)
            .join(BotProfileDB, PostDB.author_id == BotProfileDB.id)
            .join(CommunityDB, PostDB.community_id == CommunityDB.id)
            .where(PostDB.id == post_id)
            .where(PostDB.is_deleted == False)
        )
        result = await session.execute(stmt)
        row = result.first()

        if not row:
            raise HTTPException(status_code=404, detail="Post not found")

        post, author, community = row

        # Check if user liked
        is_liked = False
        if user_id:
            like_stmt = select(PostLikeDB).where(
                PostLikeDB.post_id == post.id,
                PostLikeDB.user_id == user_id
            )
            like_result = await session.execute(like_stmt)
            is_liked = like_result.scalar_one_or_none() is not None

        # Get all comments (excluding blocked bots)
        comment_stmt = (
            select(PostCommentDB, BotProfileDB)
            .outerjoin(BotProfileDB, PostCommentDB.author_id == BotProfileDB.id)
            .where(PostCommentDB.post_id == post.id)
            .where(PostCommentDB.is_deleted == False)
            .order_by(PostCommentDB.created_at)
        )
        if blocked_bot_ids:
            comment_stmt = comment_stmt.where(PostCommentDB.author_id.notin_(blocked_bot_ids))

        comment_result = await session.execute(comment_stmt)
        comments_data = comment_result.all()

        comments = []
        for comment, comment_author in comments_data:
            if comment_author:
                comments.append(CommentResponse(
                    id=comment.id,
                    author=AuthorInfo(
                        id=comment_author.id,
                        display_name=comment_author.display_name,
                        handle=comment_author.handle,
                        avatar_seed=comment_author.avatar_seed,
                        is_ai_labeled=comment_author.is_ai_labeled,
                        ai_label_text=comment_author.ai_label_text
                    ),
                    content=comment.content,
                    like_count=comment.like_count,
                    created_at=comment.created_at
                ))

        # Get media info if attached
        media_info = None
        if post.media_id:
            media_stmt = select(MediaDB).where(
                MediaDB.id == post.media_id,
                MediaDB.is_deleted == False
            )
            media_result = await session.execute(media_stmt)
            media = media_result.scalar_one_or_none()
            if media:
                media_info = MediaInfo(
                    id=media.id,
                    file_type=media.file_type,
                    original_url=media.original_url,
                    thumbnail_url=media.thumbnail_url,
                    width=media.width,
                    height=media.height,
                    duration_seconds=media.duration_seconds,
                )

        return PostResponse(
            id=post.id,
            author=AuthorInfo(
                id=author.id,
                display_name=author.display_name,
                handle=author.handle,
                avatar_seed=author.avatar_seed,
                is_ai_labeled=author.is_ai_labeled,
                ai_label_text=author.ai_label_text
            ),
            community_id=community.id,
            community_name=community.name,
            content=post.content,
            image_url=post.image_url,
            media=media_info,
            like_count=post.like_count,
            comment_count=post.comment_count,
            created_at=post.created_at,
            is_liked_by_user=is_liked,
            recent_comments=comments
        )


@router.post("/posts/{post_id}/like")
@handle_errors(default_error=DatabaseError)
async def like_post(post_id: UUID, user_id: UUID, is_bot: bool = False):
    """
    Like a post.

    Uses database-level locking to prevent race conditions:
    - SELECT FOR UPDATE on post row
    - Handles unique constraint violations gracefully
    """
    async with async_session_factory() as session:
        try:
            # Lock the post row first to prevent race conditions
            post_stmt = (
                select(PostDB)
                .where(PostDB.id == post_id)
                .with_for_update()
            )
            post_result = await session.execute(post_stmt)
            post = post_result.scalar_one_or_none()

            if not post:
                raise HTTPException(status_code=404, detail="Post not found")

            # Check if already liked (after acquiring lock)
            stmt = select(PostLikeDB).where(
                PostLikeDB.post_id == post_id,
                PostLikeDB.user_id == user_id
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                return {"status": "already_liked", "like_count": post.like_count}

            # Create like
            like = PostLikeDB(
                post_id=post_id,
                user_id=user_id,
                is_bot=is_bot
            )
            session.add(like)

            # Update post like count
            post.like_count += 1

            await session.commit()
            return {"status": "liked", "like_count": post.like_count}

        except IntegrityError:
            # Handle unique constraint violation (duplicate like from race condition)
            await session.rollback()
            # Re-fetch the current like count
            async with async_session_factory() as read_session:
                post_stmt = select(PostDB).where(PostDB.id == post_id)
                post_result = await read_session.execute(post_stmt)
                post = post_result.scalar_one_or_none()
            return {"status": "already_liked", "like_count": post.like_count if post else 0}


@router.delete("/posts/{post_id}/like")
@handle_errors(default_error=DatabaseError)
async def unlike_post(post_id: UUID, user_id: UUID):
    """Unlike a post."""
    async with async_session_factory() as session:
        stmt = select(PostLikeDB).where(
            PostLikeDB.post_id == post_id,
            PostLikeDB.user_id == user_id
        )
        result = await session.execute(stmt)
        like = result.scalar_one_or_none()

        if not like:
            return {"status": "not_liked"}

        await session.delete(like)

        # Update post like count
        post_stmt = select(PostDB).where(PostDB.id == post_id)
        post_result = await session.execute(post_stmt)
        post = post_result.scalar_one_or_none()
        if post and post.like_count > 0:
            post.like_count -= 1

        await session.commit()
        return {"status": "unliked", "like_count": post.like_count if post else 0}


@router.post("/posts/{post_id}/comments", response_model=CommentResponse)
@handle_errors(default_error=DatabaseError)
async def create_comment(
    post_id: UUID,
    user_id: UUID,
    content: str,
    parent_comment_id: Optional[UUID] = None,
    is_bot: bool = False
):
    """Create a comment on a post."""
    # Content moderation check (skip for bot-generated content)
    if not is_bot:
        content_filter = get_content_filter()
        moderation_result = content_filter.check_text(
            text=content,
            user_id=user_id,
            context={"content_type": "comment", "post_id": str(post_id)}
        )

        if moderation_result.suggested_action == SuggestedAction.BLOCK:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Content violates community guidelines",
                    "flags": moderation_result.flags,
                    "action": "blocked"
                }
            )
        elif moderation_result.suggested_action == SuggestedAction.WARN:
            # Log the warning but allow the content
            pass  # Could add logging here

    async with async_session_factory() as session:
        # Get author info
        author_stmt = select(BotProfileDB).where(BotProfileDB.id == user_id)
        author_result = await session.execute(author_stmt)
        author = author_result.scalar_one_or_none()

        comment = PostCommentDB(
            post_id=post_id,
            author_id=user_id,
            is_bot=is_bot,
            content=content,
            parent_comment_id=parent_comment_id
        )
        session.add(comment)

        # Update post comment count
        post_stmt = select(PostDB).where(PostDB.id == post_id)
        post_result = await session.execute(post_stmt)
        post = post_result.scalar_one_or_none()
        if post:
            post.comment_count += 1

        await session.commit()
        await session.refresh(comment)

        author_info = AuthorInfo(
            id=author.id if author else user_id,
            display_name=author.display_name if author else "User",
            handle=author.handle if author else "user",
            avatar_seed=author.avatar_seed if author else str(user_id),
            is_ai_labeled=author.is_ai_labeled if author else False,
            ai_label_text=author.ai_label_text if author else ""
        )

        return CommentResponse(
            id=comment.id,
            author=author_info,
            content=comment.content,
            like_count=0,
            created_at=comment.created_at
        )


@router.get("/posts/{post_id}/likers", response_model=List[AuthorInfo])
@handle_errors(default_error=DatabaseError)
async def get_post_likers(post_id: UUID, limit: int = 50, offset: int = 0):
    """Get all users who liked a post."""
    async with async_session_factory() as session:
        stmt = (
            select(PostLikeDB, BotProfileDB)
            .outerjoin(BotProfileDB, PostLikeDB.user_id == BotProfileDB.id)
            .where(PostLikeDB.post_id == post_id)
            .order_by(desc(PostLikeDB.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        rows = result.all()

        likers = []
        for like, author in rows:
            if author:
                likers.append(AuthorInfo(
                    id=author.id,
                    display_name=author.display_name,
                    handle=author.handle,
                    avatar_seed=author.avatar_seed,
                    is_ai_labeled=author.is_ai_labeled,
                    ai_label_text=author.ai_label_text
                ))
        return likers


@router.get("/posts/{post_id}/comments", response_model=List[CommentResponse])
@handle_errors(default_error=DatabaseError)
async def get_comments(
    post_id: UUID,
    user_id: Optional[UUID] = None,
    limit: int = 50,
    offset: int = 0
):
    """Get all comments for a post."""
    # Get blocked bot IDs for this user
    blocked_bot_ids = set()
    if user_id:
        blocked_bot_ids = await blocking_service.get_blocked_bot_ids(user_id)

    async with async_session_factory() as session:
        stmt = (
            select(PostCommentDB, BotProfileDB)
            .outerjoin(BotProfileDB, PostCommentDB.author_id == BotProfileDB.id)
            .where(PostCommentDB.post_id == post_id)
            .where(PostCommentDB.is_deleted == False)
            .order_by(PostCommentDB.created_at)
            .limit(limit)
            .offset(offset)
        )
        # Exclude comments from blocked bots
        if blocked_bot_ids:
            stmt = stmt.where(PostCommentDB.author_id.notin_(blocked_bot_ids))

        result = await session.execute(stmt)
        rows = result.all()

        comments = []
        for comment, author in rows:
            author_info = AuthorInfo(
                id=author.id if author else comment.author_id,
                display_name=author.display_name if author else "User",
                handle=author.handle if author else "user",
                avatar_seed=author.avatar_seed if author else str(comment.author_id),
                is_ai_labeled=author.is_ai_labeled if author else False,
                ai_label_text=author.ai_label_text if author else ""
            )
            comments.append(CommentResponse(
                id=comment.id,
                author=author_info,
                content=comment.content,
                like_count=comment.like_count,
                created_at=comment.created_at
            ))

        return comments
