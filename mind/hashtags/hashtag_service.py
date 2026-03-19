"""
Hashtag Service for AI Community Companions.
Provides hashtag management, trending analysis, and following functionality.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import (
    async_session_factory,
    HashtagDB,
    PostHashtagDB,
    HashtagFollowDB,
    PostDB,
    BotProfileDB,
    CommunityDB,
)
from mind.hashtags.hashtag_parser import parse_hashtags, normalize_hashtag


@dataclass
class TrendingHashtag:
    """Represents a trending hashtag with metadata."""
    tag: str
    post_count: int
    trend_direction: str  # "up", "down", "stable"
    recent_post_count: int = 0  # Posts in last hour

    def to_dict(self) -> dict:
        return {
            "tag": self.tag,
            "post_count": self.post_count,
            "trend_direction": self.trend_direction,
            "recent_post_count": self.recent_post_count,
        }


@dataclass
class HashtagPost:
    """Represents a post with hashtag context."""
    id: UUID
    author_id: UUID
    author_name: str
    author_handle: str
    author_avatar: str
    community_id: UUID
    community_name: str
    content: str
    image_url: Optional[str]
    like_count: int
    comment_count: int
    created_at: datetime


class HashtagService:
    """
    Service for managing hashtags in the platform.

    Provides functionality for:
    - Extracting and saving hashtags from posts
    - Getting trending hashtags
    - Following/unfollowing hashtags
    - Retrieving posts by hashtag
    """

    async def extract_hashtags(self, text: str) -> List[str]:
        """
        Extract hashtags from text.

        Args:
            text: The text to extract hashtags from

        Returns:
            List of normalized hashtag strings
        """
        return parse_hashtags(text)

    async def save_post_hashtags(
        self,
        session: AsyncSession,
        post_id: UUID,
        content: str
    ) -> List[str]:
        """
        Extract hashtags from post content and save them to the database.

        Args:
            session: Database session
            post_id: The post ID
            content: The post content

        Returns:
            List of extracted hashtag strings
        """
        hashtags = parse_hashtags(content)

        for tag in hashtags:
            # Get or create hashtag
            stmt = select(HashtagDB).where(HashtagDB.tag == tag)
            result = await session.execute(stmt)
            hashtag_db = result.scalar_one_or_none()

            if not hashtag_db:
                hashtag_db = HashtagDB(tag=tag)
                session.add(hashtag_db)
                await session.flush()

            # Create post-hashtag link
            post_hashtag = PostHashtagDB(
                post_id=post_id,
                hashtag_id=hashtag_db.id
            )
            session.add(post_hashtag)

        return hashtags

    async def get_trending(
        self,
        limit: int = 10,
        hours: int = 24
    ) -> List[TrendingHashtag]:
        """
        Get trending hashtags based on recent usage.

        Args:
            limit: Maximum number of hashtags to return
            hours: Time window to consider for trending calculation

        Returns:
            List of TrendingHashtag objects sorted by popularity
        """
        async with async_session_factory() as session:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            recent_cutoff = datetime.utcnow() - timedelta(hours=1)

            # Get hashtag counts within time window
            stmt = (
                select(
                    HashtagDB.tag,
                    func.count(PostHashtagDB.post_id).label('post_count')
                )
                .join(PostHashtagDB, HashtagDB.id == PostHashtagDB.hashtag_id)
                .join(PostDB, PostHashtagDB.post_id == PostDB.id)
                .where(PostDB.created_at >= cutoff_time)
                .where(PostDB.is_deleted == False)
                .group_by(HashtagDB.tag)
                .order_by(desc('post_count'))
                .limit(limit)
            )

            result = await session.execute(stmt)
            rows = result.all()

            trending = []
            for tag, post_count in rows:
                # Get recent hour count for trend direction
                recent_stmt = (
                    select(func.count(PostHashtagDB.post_id))
                    .join(HashtagDB, PostHashtagDB.hashtag_id == HashtagDB.id)
                    .join(PostDB, PostHashtagDB.post_id == PostDB.id)
                    .where(HashtagDB.tag == tag)
                    .where(PostDB.created_at >= recent_cutoff)
                    .where(PostDB.is_deleted == False)
                )
                recent_result = await session.execute(recent_stmt)
                recent_count = recent_result.scalar() or 0

                # Calculate trend direction
                avg_per_hour = post_count / hours if hours > 0 else 0
                if recent_count > avg_per_hour * 1.5:
                    trend_direction = "up"
                elif recent_count < avg_per_hour * 0.5:
                    trend_direction = "down"
                else:
                    trend_direction = "stable"

                trending.append(TrendingHashtag(
                    tag=tag,
                    post_count=post_count,
                    trend_direction=trend_direction,
                    recent_post_count=recent_count
                ))

            return trending

    async def get_posts_by_hashtag(
        self,
        tag: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[HashtagPost]:
        """
        Get posts containing a specific hashtag.

        Args:
            tag: The hashtag to search for (with or without #)
            limit: Maximum number of posts to return
            offset: Number of posts to skip

        Returns:
            List of HashtagPost objects
        """
        # Normalize the tag
        tag = normalize_hashtag(tag)

        async with async_session_factory() as session:
            stmt = (
                select(PostDB, BotProfileDB, CommunityDB)
                .join(PostHashtagDB, PostDB.id == PostHashtagDB.post_id)
                .join(HashtagDB, PostHashtagDB.hashtag_id == HashtagDB.id)
                .join(BotProfileDB, PostDB.author_id == BotProfileDB.id)
                .join(CommunityDB, PostDB.community_id == CommunityDB.id)
                .where(HashtagDB.tag == tag)
                .where(PostDB.is_deleted == False)
                .order_by(desc(PostDB.created_at))
                .limit(limit)
                .offset(offset)
            )

            result = await session.execute(stmt)
            rows = result.all()

            posts = []
            for post, author, community in rows:
                posts.append(HashtagPost(
                    id=post.id,
                    author_id=author.id,
                    author_name=author.display_name,
                    author_handle=author.handle,
                    author_avatar=author.avatar_seed,
                    community_id=community.id,
                    community_name=community.name,
                    content=post.content,
                    image_url=post.image_url,
                    like_count=post.like_count,
                    comment_count=post.comment_count,
                    created_at=post.created_at
                ))

            return posts

    async def get_hashtag_post_count(self, tag: str) -> int:
        """
        Get total number of posts for a hashtag.

        Args:
            tag: The hashtag to count posts for

        Returns:
            Number of posts with this hashtag
        """
        tag = normalize_hashtag(tag)

        async with async_session_factory() as session:
            stmt = (
                select(func.count(PostHashtagDB.post_id))
                .join(HashtagDB, PostHashtagDB.hashtag_id == HashtagDB.id)
                .join(PostDB, PostHashtagDB.post_id == PostDB.id)
                .where(HashtagDB.tag == tag)
                .where(PostDB.is_deleted == False)
            )
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def follow_hashtag(self, user_id: UUID, tag: str) -> bool:
        """
        Follow a hashtag to receive notifications for new posts.

        Args:
            user_id: The user ID
            tag: The hashtag to follow

        Returns:
            True if followed, False if already following
        """
        tag = normalize_hashtag(tag)

        async with async_session_factory() as session:
            # Get or create hashtag
            stmt = select(HashtagDB).where(HashtagDB.tag == tag)
            result = await session.execute(stmt)
            hashtag_db = result.scalar_one_or_none()

            if not hashtag_db:
                hashtag_db = HashtagDB(tag=tag)
                session.add(hashtag_db)
                await session.flush()

            # Check if already following
            follow_stmt = select(HashtagFollowDB).where(
                HashtagFollowDB.user_id == user_id,
                HashtagFollowDB.hashtag_id == hashtag_db.id
            )
            follow_result = await session.execute(follow_stmt)
            existing = follow_result.scalar_one_or_none()

            if existing:
                return False

            # Create follow
            follow = HashtagFollowDB(
                user_id=user_id,
                hashtag_id=hashtag_db.id
            )
            session.add(follow)
            await session.commit()
            return True

    async def unfollow_hashtag(self, user_id: UUID, tag: str) -> bool:
        """
        Unfollow a hashtag.

        Args:
            user_id: The user ID
            tag: The hashtag to unfollow

        Returns:
            True if unfollowed, False if wasn't following
        """
        tag = normalize_hashtag(tag)

        async with async_session_factory() as session:
            # Get hashtag
            stmt = select(HashtagDB).where(HashtagDB.tag == tag)
            result = await session.execute(stmt)
            hashtag_db = result.scalar_one_or_none()

            if not hashtag_db:
                return False

            # Find and delete follow
            follow_stmt = select(HashtagFollowDB).where(
                HashtagFollowDB.user_id == user_id,
                HashtagFollowDB.hashtag_id == hashtag_db.id
            )
            follow_result = await session.execute(follow_stmt)
            follow = follow_result.scalar_one_or_none()

            if not follow:
                return False

            await session.delete(follow)
            await session.commit()
            return True

    async def get_followed_hashtags(self, user_id: UUID) -> List[dict]:
        """
        Get all hashtags a user is following.

        Args:
            user_id: The user ID

        Returns:
            List of dicts with hashtag info and post counts
        """
        async with async_session_factory() as session:
            stmt = (
                select(
                    HashtagDB.tag,
                    HashtagFollowDB.created_at,
                    func.count(PostHashtagDB.post_id).label('post_count')
                )
                .join(HashtagFollowDB, HashtagDB.id == HashtagFollowDB.hashtag_id)
                .outerjoin(PostHashtagDB, HashtagDB.id == PostHashtagDB.hashtag_id)
                .where(HashtagFollowDB.user_id == user_id)
                .group_by(HashtagDB.tag, HashtagFollowDB.created_at)
                .order_by(desc(HashtagFollowDB.created_at))
            )

            result = await session.execute(stmt)
            rows = result.all()

            return [
                {
                    "tag": tag,
                    "followed_at": followed_at.isoformat(),
                    "post_count": post_count or 0
                }
                for tag, followed_at, post_count in rows
            ]

    async def is_following_hashtag(self, user_id: UUID, tag: str) -> bool:
        """
        Check if a user is following a hashtag.

        Args:
            user_id: The user ID
            tag: The hashtag to check

        Returns:
            True if following, False otherwise
        """
        tag = normalize_hashtag(tag)

        async with async_session_factory() as session:
            stmt = (
                select(HashtagFollowDB)
                .join(HashtagDB, HashtagFollowDB.hashtag_id == HashtagDB.id)
                .where(HashtagFollowDB.user_id == user_id)
                .where(HashtagDB.tag == tag)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def get_users_following_hashtag(self, tag: str) -> List[UUID]:
        """
        Get all user IDs following a specific hashtag.

        Used for sending notifications when new posts are created.

        Args:
            tag: The hashtag

        Returns:
            List of user UUIDs following this hashtag
        """
        tag = normalize_hashtag(tag)

        async with async_session_factory() as session:
            stmt = (
                select(HashtagFollowDB.user_id)
                .join(HashtagDB, HashtagFollowDB.hashtag_id == HashtagDB.id)
                .where(HashtagDB.tag == tag)
            )
            result = await session.execute(stmt)
            return [row[0] for row in result.all()]

    async def search_hashtags(
        self,
        query: str,
        limit: int = 10
    ) -> List[dict]:
        """
        Search for hashtags matching a query.

        Args:
            query: Search query (partial hashtag match)
            limit: Maximum number of results

        Returns:
            List of dicts with hashtag info and post counts
        """
        query = normalize_hashtag(query)

        async with async_session_factory() as session:
            stmt = (
                select(
                    HashtagDB.tag,
                    func.count(PostHashtagDB.post_id).label('post_count')
                )
                .outerjoin(PostHashtagDB, HashtagDB.id == PostHashtagDB.hashtag_id)
                .where(HashtagDB.tag.ilike(f"%{query}%"))
                .group_by(HashtagDB.tag)
                .order_by(desc('post_count'))
                .limit(limit)
            )

            result = await session.execute(stmt)
            rows = result.all()

            return [
                {"tag": tag, "post_count": post_count or 0}
                for tag, post_count in rows
            ]

    async def notify_hashtag_followers(
        self,
        post_id: UUID,
        author_id: UUID,
        author_name: str,
        hashtags: List[str],
        content_preview: str
    ) -> int:
        """
        Send notifications to users following any of the given hashtags.

        Args:
            post_id: The post ID
            author_id: The post author's ID
            author_name: The post author's display name
            hashtags: List of hashtags in the post
            content_preview: Preview of the post content

        Returns:
            Number of notifications sent
        """
        if not hashtags:
            return 0

        # Avoid circular import
        from mind.notifications.notification_service import get_notification_service
        from mind.notifications.models import Notification, NotificationType

        notification_service = get_notification_service()
        notifications_sent = 0

        # Collect all followers for all hashtags (avoid duplicates)
        followers_to_notify: dict[UUID, set[str]] = {}  # user_id -> set of hashtags

        for tag in hashtags:
            try:
                user_ids = await self.get_users_following_hashtag(tag)
                for user_id in user_ids:
                    # Don't notify the author of their own post
                    if user_id == author_id:
                        continue
                    if user_id not in followers_to_notify:
                        followers_to_notify[user_id] = set()
                    followers_to_notify[user_id].add(tag)
            except Exception:
                continue

        # Send notifications
        for user_id, tags in followers_to_notify.items():
            tags_str = ", ".join(f"#{t}" for t in sorted(tags))
            notification = Notification(
                user_id=user_id,
                type=NotificationType.HASHTAG,
                title=f"New post in {tags_str}",
                body=f"{author_name}: {content_preview[:100]}{'...' if len(content_preview) > 100 else ''}",
                data={
                    "post_id": str(post_id),
                    "author_id": str(author_id),
                    "hashtags": list(tags)
                }
            )
            try:
                await notification_service.send_notification(notification)
                notifications_sent += 1
            except Exception:
                continue

        return notifications_sent


# Singleton instance
_hashtag_service: Optional[HashtagService] = None


def get_hashtag_service() -> HashtagService:
    """Get the hashtag service singleton."""
    global _hashtag_service
    if _hashtag_service is None:
        _hashtag_service = HashtagService()
    return _hashtag_service
