"""
Story Service - manages ephemeral stories with 24-hour expiration.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import (
    async_session_factory,
    StoryDB,
    StoryViewDB,
    BotProfileDB,
    AppUserDB,
)

logger = logging.getLogger(__name__)


# Singleton instance
_story_service: Optional["StoryService"] = None


async def get_story_service() -> "StoryService":
    """Get the singleton story service instance."""
    global _story_service
    if _story_service is None:
        _story_service = StoryService()
    return _story_service


class StoryService:
    """
    Service for managing ephemeral stories.

    Stories expire after 24 hours by default.
    Tracks views and provides story feeds.
    """

    def __init__(self):
        self.default_expiration_hours = 24
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start_cleanup_task(self):
        """Start background cleanup task for expired stories."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Story cleanup task started")

    async def stop_cleanup_task(self):
        """Stop the cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Story cleanup task stopped")

    async def _cleanup_loop(self):
        """Periodically clean up expired stories."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                deleted_count = await self.cleanup_expired_stories()
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} expired stories")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in story cleanup: {e}")

    async def create_story(
        self,
        author_id: UUID,
        content: str,
        media_url: Optional[str] = None,
        background_color: str = "#1a1a2e",
        font_style: str = "normal",
        expires_hours: int = 24,
        author_is_bot: bool = True,
    ) -> StoryDB:
        """
        Create a new story.

        Args:
            author_id: UUID of the author (bot or user)
            content: Story text content
            media_url: Optional media URL
            background_color: Background color hex
            font_style: Font style (normal, bold, italic, etc.)
            expires_hours: Hours until expiration (default 24)
            author_is_bot: Whether the author is a bot

        Returns:
            Created StoryDB object
        """
        async with async_session_factory() as session:
            story = StoryDB(
                author_id=author_id,
                author_is_bot=author_is_bot,
                content=content,
                media_url=media_url,
                background_color=background_color,
                font_style=font_style,
                expires_at=datetime.utcnow() + timedelta(hours=expires_hours),
            )
            session.add(story)
            await session.commit()
            await session.refresh(story)

            logger.info(f"Created story {story.id} by {'bot' if author_is_bot else 'user'} {author_id}")
            return story

    async def get_active_stories(
        self,
        viewer_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict]:
        """
        Get active (non-expired) stories from all users/bots.

        Args:
            viewer_id: Optional viewer ID to check viewed status
            limit: Maximum stories to return
            offset: Pagination offset

        Returns:
            List of story dictionaries with author info
        """
        now = datetime.utcnow()

        async with async_session_factory() as session:
            # Get active stories
            stmt = (
                select(StoryDB)
                .where(
                    and_(
                        StoryDB.is_deleted == False,
                        StoryDB.expires_at > now,
                    )
                )
                .order_by(StoryDB.created_at.desc())
                .limit(limit)
                .offset(offset)
            )

            result = await session.execute(stmt)
            stories = result.scalars().all()

            story_list = []
            for story in stories:
                # Get author info
                author_info = await self._get_author_info(session, story.author_id, story.author_is_bot)

                # Check if viewed by viewer
                is_viewed = False
                if viewer_id:
                    view_stmt = select(StoryViewDB).where(
                        and_(
                            StoryViewDB.story_id == story.id,
                            StoryViewDB.viewer_id == viewer_id,
                        )
                    )
                    view_result = await session.execute(view_stmt)
                    is_viewed = view_result.scalar_one_or_none() is not None

                # Get view count
                view_count_stmt = select(func.count(StoryViewDB.id)).where(
                    StoryViewDB.story_id == story.id
                )
                view_count_result = await session.execute(view_count_stmt)
                view_count = view_count_result.scalar() or 0

                story_list.append({
                    "id": story.id,
                    "author": author_info,
                    "content": story.content,
                    "media_url": story.media_url,
                    "background_color": story.background_color,
                    "font_style": story.font_style,
                    "created_at": story.created_at,
                    "expires_at": story.expires_at,
                    "is_viewed": is_viewed,
                    "view_count": view_count,
                })

            return story_list

    async def get_user_stories(
        self,
        author_id: UUID,
        include_expired: bool = False,
    ) -> List[Dict]:
        """
        Get all stories from a specific user/bot.

        Args:
            author_id: UUID of the author
            include_expired: Whether to include expired stories

        Returns:
            List of story dictionaries
        """
        now = datetime.utcnow()

        async with async_session_factory() as session:
            conditions = [
                StoryDB.author_id == author_id,
                StoryDB.is_deleted == False,
            ]

            if not include_expired:
                conditions.append(StoryDB.expires_at > now)

            stmt = (
                select(StoryDB)
                .where(and_(*conditions))
                .order_by(StoryDB.created_at.desc())
            )

            result = await session.execute(stmt)
            stories = result.scalars().all()

            story_list = []
            for story in stories:
                # Get view count
                view_count_stmt = select(func.count(StoryViewDB.id)).where(
                    StoryViewDB.story_id == story.id
                )
                view_count_result = await session.execute(view_count_stmt)
                view_count = view_count_result.scalar() or 0

                story_list.append({
                    "id": story.id,
                    "content": story.content,
                    "media_url": story.media_url,
                    "background_color": story.background_color,
                    "font_style": story.font_style,
                    "created_at": story.created_at,
                    "expires_at": story.expires_at,
                    "view_count": view_count,
                    "is_expired": story.expires_at <= now,
                })

            return story_list

    async def record_view(
        self,
        story_id: UUID,
        viewer_id: UUID,
        viewer_is_bot: bool = False,
    ) -> bool:
        """
        Record a story view.

        Args:
            story_id: UUID of the story
            viewer_id: UUID of the viewer
            viewer_is_bot: Whether the viewer is a bot

        Returns:
            True if view was recorded, False if already viewed
        """
        async with async_session_factory() as session:
            # Check if already viewed
            existing_stmt = select(StoryViewDB).where(
                and_(
                    StoryViewDB.story_id == story_id,
                    StoryViewDB.viewer_id == viewer_id,
                )
            )
            existing_result = await session.execute(existing_stmt)

            if existing_result.scalar_one_or_none():
                return False  # Already viewed

            # Record view
            view = StoryViewDB(
                story_id=story_id,
                viewer_id=viewer_id,
                viewer_is_bot=viewer_is_bot,
            )
            session.add(view)
            await session.commit()
            return True

    async def get_viewers(
        self,
        story_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict]:
        """
        Get list of viewers for a story.

        Args:
            story_id: UUID of the story
            limit: Maximum viewers to return
            offset: Pagination offset

        Returns:
            List of viewer dictionaries
        """
        async with async_session_factory() as session:
            stmt = (
                select(StoryViewDB)
                .where(StoryViewDB.story_id == story_id)
                .order_by(StoryViewDB.viewed_at.desc())
                .limit(limit)
                .offset(offset)
            )

            result = await session.execute(stmt)
            views = result.scalars().all()

            viewers = []
            for view in views:
                viewer_info = await self._get_author_info(
                    session, view.viewer_id, view.viewer_is_bot
                )
                viewers.append({
                    "viewer": viewer_info,
                    "viewed_at": view.viewed_at,
                })

            return viewers

    async def delete_story(self, story_id: UUID, author_id: UUID) -> bool:
        """
        Soft delete a story (only by author).

        Args:
            story_id: UUID of the story
            author_id: UUID of the author (for verification)

        Returns:
            True if deleted, False if not found or unauthorized
        """
        async with async_session_factory() as session:
            stmt = select(StoryDB).where(
                and_(
                    StoryDB.id == story_id,
                    StoryDB.author_id == author_id,
                )
            )
            result = await session.execute(stmt)
            story = result.scalar_one_or_none()

            if not story:
                return False

            story.is_deleted = True
            await session.commit()
            logger.info(f"Deleted story {story_id}")
            return True

    async def cleanup_expired_stories(self) -> int:
        """
        Clean up expired stories (soft delete).

        Returns:
            Number of stories cleaned up
        """
        now = datetime.utcnow()

        async with async_session_factory() as session:
            # Find expired stories that aren't already deleted
            stmt = select(StoryDB).where(
                and_(
                    StoryDB.expires_at <= now,
                    StoryDB.is_deleted == False,
                )
            )

            result = await session.execute(stmt)
            expired_stories = result.scalars().all()

            count = 0
            for story in expired_stories:
                story.is_deleted = True
                count += 1

            if count > 0:
                await session.commit()

            return count

    async def get_story_by_id(self, story_id: UUID) -> Optional[Dict]:
        """
        Get a single story by ID.

        Args:
            story_id: UUID of the story

        Returns:
            Story dictionary or None if not found
        """
        now = datetime.utcnow()

        async with async_session_factory() as session:
            stmt = select(StoryDB).where(
                and_(
                    StoryDB.id == story_id,
                    StoryDB.is_deleted == False,
                )
            )

            result = await session.execute(stmt)
            story = result.scalar_one_or_none()

            if not story:
                return None

            author_info = await self._get_author_info(
                session, story.author_id, story.author_is_bot
            )

            # Get view count
            view_count_stmt = select(func.count(StoryViewDB.id)).where(
                StoryViewDB.story_id == story.id
            )
            view_count_result = await session.execute(view_count_stmt)
            view_count = view_count_result.scalar() or 0

            return {
                "id": story.id,
                "author": author_info,
                "content": story.content,
                "media_url": story.media_url,
                "background_color": story.background_color,
                "font_style": story.font_style,
                "created_at": story.created_at,
                "expires_at": story.expires_at,
                "view_count": view_count,
                "is_expired": story.expires_at <= now,
            }

    async def _get_author_info(
        self,
        session: AsyncSession,
        author_id: UUID,
        is_bot: bool,
    ) -> Dict:
        """Get author info for a story."""
        if is_bot:
            stmt = select(BotProfileDB).where(BotProfileDB.id == author_id)
            result = await session.execute(stmt)
            bot = result.scalar_one_or_none()

            if bot:
                return {
                    "id": bot.id,
                    "display_name": bot.display_name,
                    "handle": bot.handle,
                    "avatar_seed": bot.avatar_seed,
                    "is_bot": True,
                    "is_ai_labeled": bot.is_ai_labeled,
                    "ai_label_text": bot.ai_label_text,
                }
        else:
            stmt = select(AppUserDB).where(AppUserDB.id == author_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if user:
                return {
                    "id": user.id,
                    "display_name": user.display_name,
                    "handle": f"user_{str(user.id)[:8]}",
                    "avatar_seed": user.avatar_seed,
                    "is_bot": False,
                    "is_ai_labeled": False,
                    "ai_label_text": "",
                }

        # Fallback for missing author
        return {
            "id": author_id,
            "display_name": "Unknown",
            "handle": "unknown",
            "avatar_seed": str(author_id),
            "is_bot": is_bot,
            "is_ai_labeled": False,
            "ai_label_text": "",
        }
