"""
Blocking Service for AI Community Companions.
Handles user blocking of bots and filtering blocked content.
"""

from datetime import datetime
from typing import List, Optional, Set
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import (
    async_session_factory, UserBlockDB, BotProfileDB, PostDB,
    PostCommentDB, CommunityChatMessageDB, DirectMessageDB
)


class BlockingService:
    """
    Service for managing user blocking of bots.

    Provides methods to:
    - Block/unblock bots
    - Check if a bot is blocked
    - Get list of blocked bots
    - Filter content from blocked bots
    """

    async def block_bot(
        self,
        user_id: UUID,
        bot_id: UUID,
        reason: Optional[str] = None
    ) -> dict:
        """
        Block a bot for a user.

        Args:
            user_id: The user performing the block
            bot_id: The bot to block
            reason: Optional reason for blocking

        Returns:
            Dict with status and block details
        """
        async with async_session_factory() as session:
            # Check if bot exists
            bot_stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
            bot_result = await session.execute(bot_stmt)
            bot = bot_result.scalar_one_or_none()

            if not bot:
                return {"status": "error", "message": "Bot not found"}

            # Check if already blocked
            existing_stmt = select(UserBlockDB).where(
                UserBlockDB.user_id == user_id,
                UserBlockDB.blocked_bot_id == bot_id
            )
            existing_result = await session.execute(existing_stmt)
            existing = existing_result.scalar_one_or_none()

            if existing:
                return {"status": "already_blocked", "blocked_at": existing.created_at}

            # Create block record
            block = UserBlockDB(
                user_id=user_id,
                blocked_bot_id=bot_id,
                reason=reason
            )
            session.add(block)
            await session.commit()
            await session.refresh(block)

            return {
                "status": "blocked",
                "bot_id": str(bot_id),
                "bot_name": bot.display_name,
                "blocked_at": block.created_at,
                "reason": reason
            }

    async def unblock_bot(
        self,
        user_id: UUID,
        bot_id: UUID
    ) -> dict:
        """
        Unblock a bot for a user.

        Args:
            user_id: The user performing the unblock
            bot_id: The bot to unblock

        Returns:
            Dict with status
        """
        async with async_session_factory() as session:
            # Check if block exists
            stmt = select(UserBlockDB).where(
                UserBlockDB.user_id == user_id,
                UserBlockDB.blocked_bot_id == bot_id
            )
            result = await session.execute(stmt)
            block = result.scalar_one_or_none()

            if not block:
                return {"status": "not_blocked"}

            await session.delete(block)
            await session.commit()

            return {"status": "unblocked", "bot_id": str(bot_id)}

    async def is_blocked(
        self,
        user_id: UUID,
        bot_id: UUID
    ) -> bool:
        """
        Check if a bot is blocked by a user.

        Args:
            user_id: The user to check
            bot_id: The bot to check

        Returns:
            True if blocked, False otherwise
        """
        async with async_session_factory() as session:
            stmt = select(UserBlockDB).where(
                UserBlockDB.user_id == user_id,
                UserBlockDB.blocked_bot_id == bot_id
            )
            result = await session.execute(stmt)
            block = result.scalar_one_or_none()
            return block is not None

    async def get_blocked_bot_ids(self, user_id: UUID) -> Set[UUID]:
        """
        Get set of blocked bot IDs for a user.

        Args:
            user_id: The user to get blocks for

        Returns:
            Set of blocked bot UUIDs
        """
        async with async_session_factory() as session:
            stmt = select(UserBlockDB.blocked_bot_id).where(
                UserBlockDB.user_id == user_id
            )
            result = await session.execute(stmt)
            return set(result.scalars().all())

    async def get_blocked_bots(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0
    ) -> List[dict]:
        """
        Get list of blocked bots with details for a user.

        Args:
            user_id: The user to get blocks for
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            List of blocked bot details
        """
        async with async_session_factory() as session:
            stmt = (
                select(UserBlockDB, BotProfileDB)
                .join(BotProfileDB, UserBlockDB.blocked_bot_id == BotProfileDB.id)
                .where(UserBlockDB.user_id == user_id)
                .order_by(UserBlockDB.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            rows = result.all()

            blocked_bots = []
            for block, bot in rows:
                blocked_bots.append({
                    "id": bot.id,
                    "display_name": bot.display_name,
                    "handle": bot.handle,
                    "avatar_seed": bot.avatar_seed,
                    "bio": bot.bio,
                    "blocked_at": block.created_at,
                    "reason": block.reason
                })

            return blocked_bots

    async def filter_blocked_posts(
        self,
        user_id: UUID,
        posts: List[PostDB]
    ) -> List[PostDB]:
        """
        Filter out posts from blocked bots.

        Args:
            user_id: The user viewing posts
            posts: List of posts to filter

        Returns:
            Filtered list of posts
        """
        blocked_ids = await self.get_blocked_bot_ids(user_id)
        return [post for post in posts if post.author_id not in blocked_ids]

    async def filter_blocked_comments(
        self,
        user_id: UUID,
        comments: List[PostCommentDB]
    ) -> List[PostCommentDB]:
        """
        Filter out comments from blocked bots.

        Args:
            user_id: The user viewing comments
            comments: List of comments to filter

        Returns:
            Filtered list of comments
        """
        blocked_ids = await self.get_blocked_bot_ids(user_id)
        return [comment for comment in comments if comment.author_id not in blocked_ids]

    async def filter_blocked_chat_messages(
        self,
        user_id: UUID,
        messages: List[CommunityChatMessageDB]
    ) -> List[CommunityChatMessageDB]:
        """
        Filter out chat messages from blocked bots.

        Args:
            user_id: The user viewing messages
            messages: List of messages to filter

        Returns:
            Filtered list of messages
        """
        blocked_ids = await self.get_blocked_bot_ids(user_id)
        return [msg for msg in messages if msg.author_id not in blocked_ids]

    async def can_send_dm_to_user(
        self,
        bot_id: UUID,
        user_id: UUID
    ) -> bool:
        """
        Check if a bot can send a DM to a user (not blocked).

        Args:
            bot_id: The bot attempting to send
            user_id: The user to receive the message

        Returns:
            True if not blocked, False if blocked
        """
        return not await self.is_blocked(user_id, bot_id)

    async def get_block_count(self, user_id: UUID) -> int:
        """
        Get count of bots blocked by a user.

        Args:
            user_id: The user to count blocks for

        Returns:
            Number of blocked bots
        """
        async with async_session_factory() as session:
            from sqlalchemy import func
            stmt = select(func.count(UserBlockDB.id)).where(
                UserBlockDB.user_id == user_id
            )
            result = await session.execute(stmt)
            return result.scalar() or 0


# Singleton instance
blocking_service = BlockingService()
