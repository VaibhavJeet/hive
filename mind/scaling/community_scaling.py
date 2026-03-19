"""
Community Scaling Manager for AI Community Companions.

Manages bot populations across communities based on load metrics,
user engagement, and platform capacity.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID
from dataclasses import dataclass, field

from sqlalchemy import select, update, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import (
    async_session_factory,
    BotProfileDB,
    CommunityDB,
    CommunityMembershipDB,
    PostDB,
    PostCommentDB,
    CommunityChatMessageDB,
)


logger = logging.getLogger(__name__)


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class LoadMetrics:
    """Load metrics for a community."""
    community_id: UUID
    community_name: str
    bot_count: int
    message_rate: float  # Messages per hour
    user_count: int
    post_rate: float  # Posts per hour
    comment_rate: float  # Comments per hour
    engagement_score: float  # 0.0 to 1.0
    load_factor: float  # Calculated load factor
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_overloaded(self) -> bool:
        """Check if community is overloaded."""
        return self.load_factor > 0.9

    @property
    def is_underutilized(self) -> bool:
        """Check if community is underutilized."""
        return self.load_factor < 0.3

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "community_id": str(self.community_id),
            "community_name": self.community_name,
            "bot_count": self.bot_count,
            "message_rate": self.message_rate,
            "user_count": self.user_count,
            "post_rate": self.post_rate,
            "comment_rate": self.comment_rate,
            "engagement_score": self.engagement_score,
            "load_factor": self.load_factor,
            "is_overloaded": self.is_overloaded,
            "is_underutilized": self.is_underutilized,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class CommunityLimits:
    """Limits for a community."""
    community_id: UUID
    max_bots: int
    min_bots: int
    max_messages_per_hour: int
    max_posts_per_hour: int
    target_engagement: float


@dataclass
class RebalanceResult:
    """Result of a rebalancing operation."""
    communities_adjusted: int
    bots_moved: int
    bots_added: int
    bots_removed: int
    details: List[Dict[str, Any]]


# ============================================================================
# COMMUNITY SCALING MANAGER
# ============================================================================

class CommunityScalingManager:
    """
    Manages scaling of bot populations across communities.

    Responsibilities:
    - Monitor community load metrics
    - Add/remove bots based on engagement
    - Rebalance bots across communities
    - Enforce community limits
    """

    def __init__(
        self,
        default_max_bots: int = 100,
        default_min_bots: int = 10,
        default_max_messages_per_hour: int = 500,
        scaling_cooldown_minutes: int = 30
    ):
        """
        Initialize the scaling manager.

        Args:
            default_max_bots: Default maximum bots per community
            default_min_bots: Default minimum bots per community
            default_max_messages_per_hour: Default message rate limit
            scaling_cooldown_minutes: Minimum time between scaling operations
        """
        self.default_max_bots = default_max_bots
        self.default_min_bots = default_min_bots
        self.default_max_messages_per_hour = default_max_messages_per_hour
        self.scaling_cooldown_minutes = scaling_cooldown_minutes
        self._last_scaling: Dict[UUID, datetime] = {}
        self._community_limits: Dict[UUID, CommunityLimits] = {}

    async def get_community_load(
        self,
        community_id: UUID,
        session: Optional[AsyncSession] = None
    ) -> LoadMetrics:
        """
        Get load metrics for a community.

        Args:
            community_id: The community to analyze
            session: Optional database session

        Returns:
            LoadMetrics with current load data
        """
        async def _get_load(sess: AsyncSession) -> LoadMetrics:
            # Get community
            comm_stmt = select(CommunityDB).where(CommunityDB.id == community_id)
            comm_result = await sess.execute(comm_stmt)
            community = comm_result.scalar_one_or_none()

            if community is None:
                raise ValueError(f"Community {community_id} not found")

            # Count active bots
            bots_stmt = select(func.count()).select_from(CommunityMembershipDB).where(
                CommunityMembershipDB.community_id == community_id
            )
            bots_result = await sess.execute(bots_stmt)
            bot_count = bots_result.scalar() or 0

            # Calculate message rate (last hour)
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)

            # Chat messages
            chat_stmt = select(func.count()).select_from(CommunityChatMessageDB).where(
                and_(
                    CommunityChatMessageDB.community_id == community_id,
                    CommunityChatMessageDB.created_at >= one_hour_ago
                )
            )
            chat_result = await sess.execute(chat_stmt)
            chat_count = chat_result.scalar() or 0

            # Posts
            posts_stmt = select(func.count()).select_from(PostDB).where(
                and_(
                    PostDB.community_id == community_id,
                    PostDB.created_at >= one_hour_ago
                )
            )
            posts_result = await sess.execute(posts_stmt)
            post_count = posts_result.scalar() or 0

            # Comments (on posts in this community)
            comments_stmt = (
                select(func.count())
                .select_from(PostCommentDB)
                .join(PostDB)
                .where(
                    and_(
                        PostDB.community_id == community_id,
                        PostCommentDB.created_at >= one_hour_ago
                    )
                )
            )
            comments_result = await sess.execute(comments_stmt)
            comment_count = comments_result.scalar() or 0

            # Calculate rates (per hour)
            message_rate = float(chat_count)
            post_rate = float(post_count)
            comment_rate = float(comment_count)

            # User count (real users in community)
            user_count = community.real_user_count

            # Calculate engagement score
            total_activity = message_rate + post_rate * 5 + comment_rate * 2
            expected_activity = bot_count * 2 + user_count * 5  # Expected based on population
            engagement_score = min(1.0, total_activity / max(expected_activity, 1))

            # Calculate load factor
            limits = self._get_limits(community_id, community)
            max_activity = limits.max_messages_per_hour + limits.max_posts_per_hour * 5
            load_factor = min(1.0, total_activity / max(max_activity, 1))

            return LoadMetrics(
                community_id=community_id,
                community_name=community.name,
                bot_count=bot_count,
                message_rate=message_rate,
                user_count=user_count,
                post_rate=post_rate,
                comment_rate=comment_rate,
                engagement_score=engagement_score,
                load_factor=load_factor
            )

        if session:
            return await _get_load(session)
        else:
            async with async_session_factory() as sess:
                return await _get_load(sess)

    def _get_limits(
        self,
        community_id: UUID,
        community: CommunityDB
    ) -> CommunityLimits:
        """Get limits for a community (cached or default)."""
        if community_id in self._community_limits:
            return self._community_limits[community_id]

        return CommunityLimits(
            community_id=community_id,
            max_bots=community.max_bots or self.default_max_bots,
            min_bots=community.min_bots or self.default_min_bots,
            max_messages_per_hour=self.default_max_messages_per_hour,
            max_posts_per_hour=100,
            target_engagement=0.5
        )

    async def should_add_bot(
        self,
        community_id: UUID,
        session: Optional[AsyncSession] = None
    ) -> bool:
        """
        Determine if a bot should be added to the community.

        Conditions for adding:
        - Community is underutilized
        - Bot count is below maximum
        - High user engagement but low bot presence
        - Cooldown has passed

        Args:
            community_id: The community to check
            session: Optional database session

        Returns:
            True if a bot should be added
        """
        # Check cooldown
        if community_id in self._last_scaling:
            cooldown = datetime.utcnow() - self._last_scaling[community_id]
            if cooldown.total_seconds() < self.scaling_cooldown_minutes * 60:
                return False

        async def _should_add(sess: AsyncSession) -> bool:
            load = await self.get_community_load(community_id, sess)

            # Get community limits
            comm_stmt = select(CommunityDB).where(CommunityDB.id == community_id)
            comm_result = await sess.execute(comm_stmt)
            community = comm_result.scalar_one_or_none()

            if community is None:
                return False

            limits = self._get_limits(community_id, community)

            # Already at max
            if load.bot_count >= limits.max_bots:
                return False

            # Underutilized and has users
            if load.is_underutilized and load.user_count > 0:
                return True

            # Low bot-to-user ratio
            if load.user_count > 0:
                bot_user_ratio = load.bot_count / load.user_count
                if bot_user_ratio < 2.0:  # Less than 2 bots per user
                    return True

            return False

        if session:
            return await _should_add(session)
        else:
            async with async_session_factory() as sess:
                return await _should_add(sess)

    async def should_remove_bot(
        self,
        community_id: UUID,
        session: Optional[AsyncSession] = None
    ) -> bool:
        """
        Determine if a bot should be removed from the community.

        Conditions for removing:
        - Community is overloaded
        - Too many bots relative to users
        - Low engagement with excessive bot presence
        - Bot count is above minimum

        Args:
            community_id: The community to check
            session: Optional database session

        Returns:
            True if a bot should be removed
        """
        # Check cooldown
        if community_id in self._last_scaling:
            cooldown = datetime.utcnow() - self._last_scaling[community_id]
            if cooldown.total_seconds() < self.scaling_cooldown_minutes * 60:
                return False

        async def _should_remove(sess: AsyncSession) -> bool:
            load = await self.get_community_load(community_id, sess)

            # Get community limits
            comm_stmt = select(CommunityDB).where(CommunityDB.id == community_id)
            comm_result = await sess.execute(comm_stmt)
            community = comm_result.scalar_one_or_none()

            if community is None:
                return False

            limits = self._get_limits(community_id, community)

            # Already at minimum
            if load.bot_count <= limits.min_bots:
                return False

            # Overloaded
            if load.is_overloaded:
                return True

            # Too many bots relative to users
            if load.user_count > 0:
                bot_user_ratio = load.bot_count / load.user_count
                if bot_user_ratio > 10.0:  # More than 10 bots per user
                    return True

            # Low engagement with many bots
            if load.engagement_score < 0.2 and load.bot_count > limits.min_bots:
                return True

            return False

        if session:
            return await _should_remove(session)
        else:
            async with async_session_factory() as sess:
                return await _should_remove(sess)

    async def rebalance_bots(
        self,
        session: Optional[AsyncSession] = None
    ) -> RebalanceResult:
        """
        Rebalance bots across all communities.

        This redistributes bots from overloaded communities
        to underutilized ones.

        Args:
            session: Optional database session

        Returns:
            RebalanceResult with details of changes made
        """
        async def _rebalance(sess: AsyncSession) -> RebalanceResult:
            # Get all communities
            comm_stmt = select(CommunityDB)
            comm_result = await sess.execute(comm_stmt)
            communities = comm_result.scalars().all()

            # Analyze each community
            overloaded: List[CommunityDB] = []
            underutilized: List[CommunityDB] = []
            load_metrics: Dict[UUID, LoadMetrics] = {}

            for community in communities:
                load = await self.get_community_load(community.id, sess)
                load_metrics[community.id] = load

                if load.is_overloaded:
                    overloaded.append(community)
                elif load.is_underutilized:
                    underutilized.append(community)

            details = []
            bots_moved = 0
            bots_added = 0
            bots_removed = 0
            communities_adjusted = 0

            # Move bots from overloaded to underutilized
            for over_comm in overloaded:
                if not underutilized:
                    break

                over_load = load_metrics[over_comm.id]

                # Find least active bots to move
                bots_to_move_stmt = (
                    select(CommunityMembershipDB.bot_id)
                    .join(BotProfileDB)
                    .where(
                        and_(
                            CommunityMembershipDB.community_id == over_comm.id,
                            BotProfileDB.is_active == True
                        )
                    )
                    .order_by(BotProfileDB.last_active.asc())
                    .limit(5)  # Move up to 5 bots at a time
                )
                bots_result = await sess.execute(bots_to_move_stmt)
                bot_ids = [row[0] for row in bots_result.all()]

                for bot_id in bot_ids:
                    if not underutilized:
                        break

                    target_comm = underutilized[0]
                    target_load = load_metrics[target_comm.id]

                    # Check if target can accept more
                    if target_load.bot_count >= target_comm.max_bots:
                        underutilized.pop(0)
                        continue

                    # Move the bot
                    update_stmt = (
                        update(CommunityMembershipDB)
                        .where(
                            and_(
                                CommunityMembershipDB.bot_id == bot_id,
                                CommunityMembershipDB.community_id == over_comm.id
                            )
                        )
                        .values(community_id=target_comm.id, joined_at=datetime.utcnow())
                    )
                    await sess.execute(update_stmt)

                    bots_moved += 1
                    details.append({
                        "action": "move",
                        "bot_id": str(bot_id),
                        "from_community": over_comm.name,
                        "to_community": target_comm.name
                    })

                    # Update load counts
                    target_load.bot_count += 1
                    over_load.bot_count -= 1

                    # Remove from underutilized if now at capacity
                    if target_load.bot_count >= target_comm.max_bots:
                        underutilized.pop(0)

                communities_adjusted += 1
                self._last_scaling[over_comm.id] = datetime.utcnow()

            # Update community bot counts
            for community in communities:
                count_stmt = select(func.count()).select_from(CommunityMembershipDB).where(
                    CommunityMembershipDB.community_id == community.id
                )
                count_result = await sess.execute(count_stmt)
                community.current_bot_count = count_result.scalar() or 0

            await sess.commit()

            return RebalanceResult(
                communities_adjusted=communities_adjusted,
                bots_moved=bots_moved,
                bots_added=bots_added,
                bots_removed=bots_removed,
                details=details
            )

        if session:
            return await _rebalance(session)
        else:
            async with async_session_factory() as sess:
                return await _rebalance(sess)

    def set_community_limits(
        self,
        community_id: UUID,
        max_bots: Optional[int] = None,
        min_bots: Optional[int] = None,
        max_messages_per_hour: Optional[int] = None,
        max_posts_per_hour: Optional[int] = None,
        target_engagement: Optional[float] = None
    ) -> CommunityLimits:
        """
        Set custom limits for a community.

        Args:
            community_id: The community to configure
            max_bots: Maximum number of bots
            min_bots: Minimum number of bots
            max_messages_per_hour: Maximum messages per hour
            max_posts_per_hour: Maximum posts per hour
            target_engagement: Target engagement score

        Returns:
            Updated CommunityLimits
        """
        # Get existing or create new
        if community_id in self._community_limits:
            limits = self._community_limits[community_id]
        else:
            limits = CommunityLimits(
                community_id=community_id,
                max_bots=self.default_max_bots,
                min_bots=self.default_min_bots,
                max_messages_per_hour=self.default_max_messages_per_hour,
                max_posts_per_hour=100,
                target_engagement=0.5
            )

        # Update provided values
        if max_bots is not None:
            limits.max_bots = max_bots
        if min_bots is not None:
            limits.min_bots = min_bots
        if max_messages_per_hour is not None:
            limits.max_messages_per_hour = max_messages_per_hour
        if max_posts_per_hour is not None:
            limits.max_posts_per_hour = max_posts_per_hour
        if target_engagement is not None:
            limits.target_engagement = target_engagement

        # Validate
        if limits.min_bots > limits.max_bots:
            limits.min_bots = limits.max_bots

        self._community_limits[community_id] = limits

        logger.info(f"Set limits for community {community_id}: max_bots={limits.max_bots}, min_bots={limits.min_bots}")

        return limits

    async def get_all_load_metrics(
        self,
        session: Optional[AsyncSession] = None
    ) -> List[LoadMetrics]:
        """
        Get load metrics for all communities.

        Args:
            session: Optional database session

        Returns:
            List of LoadMetrics for all communities
        """
        async def _get_all(sess: AsyncSession) -> List[LoadMetrics]:
            comm_stmt = select(CommunityDB.id)
            comm_result = await sess.execute(comm_stmt)
            community_ids = [row[0] for row in comm_result.all()]

            metrics = []
            for comm_id in community_ids:
                try:
                    load = await self.get_community_load(comm_id, sess)
                    metrics.append(load)
                except Exception as e:
                    logger.warning(f"Failed to get load for community {comm_id}: {e}")

            return metrics

        if session:
            return await _get_all(session)
        else:
            async with async_session_factory() as sess:
                return await _get_all(sess)


# ============================================================================
# FACTORY
# ============================================================================

_scaling_manager: Optional[CommunityScalingManager] = None


def get_scaling_manager() -> CommunityScalingManager:
    """Get the singleton scaling manager."""
    global _scaling_manager
    if _scaling_manager is None:
        _scaling_manager = CommunityScalingManager()
    return _scaling_manager
