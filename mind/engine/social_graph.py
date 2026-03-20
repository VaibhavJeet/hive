"""
Social Graph Discovery — Friend-of-Friends System

Provides tiered interaction selection based on social proximity:
  Tier 1: Same community members          (weight: 1.0)
  Tier 2: Friend-of-friend bridges        (weight: 0.4)
  Tier 3: Shared interest/belief overlap   (weight: 0.2)
  Tier 4: Complete strangers               (weight: 0.05)

Used by engagement loops, conflict generation, and chat selection
to create realistic social interaction patterns.
"""

import logging
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import (
    async_session_factory,
    BotProfileDB,
    CommunityMembershipDB,
    RelationshipDB,
)

logger = logging.getLogger(__name__)

# Tier weights for selection probability
TIER_WEIGHTS = {
    1: 1.0,    # Same community
    2: 0.4,    # Friend-of-friend
    3: 0.2,    # Shared interests
    4: 0.05,   # Strangers
}


class SocialGraphDiscovery:
    """
    Builds and queries a social graph for interaction selection.

    The graph is rebuilt periodically (not on every query) to avoid
    hammering the database. Cached in memory with a configurable TTL.
    """

    def __init__(self):
        # bot_id -> set of community_ids
        self._bot_communities: Dict[UUID, Set[UUID]] = {}
        # community_id -> set of bot_ids
        self._community_members: Dict[UUID, Set[UUID]] = {}
        # bot_id -> {target_id: affinity_score}
        self._relationships: Dict[UUID, Dict[UUID, float]] = {}
        # bot_id -> set of interest strings
        self._bot_interests: Dict[UUID, Set[str]] = {}
        self._initialized = False

    async def refresh(self, session: Optional[AsyncSession] = None):
        """Rebuild the social graph from database state."""
        should_close = session is None
        if session is None:
            session = async_session_factory()
            session = await session.__aenter__()

        try:
            # Load community memberships
            self._bot_communities.clear()
            self._community_members.clear()

            membership_stmt = select(
                CommunityMembershipDB.bot_id,
                CommunityMembershipDB.community_id
            )
            result = await session.execute(membership_stmt)
            for bot_id, community_id in result.all():
                self._bot_communities.setdefault(bot_id, set()).add(community_id)
                self._community_members.setdefault(community_id, set()).add(bot_id)

            # Load relationships with meaningful affinity (> 0.3)
            self._relationships.clear()
            rel_stmt = select(
                RelationshipDB.source_id,
                RelationshipDB.target_id,
                RelationshipDB.affinity_score
            ).where(
                and_(
                    RelationshipDB.affinity_score > 0.3,
                    RelationshipDB.interaction_count > 0
                )
            )
            result = await session.execute(rel_stmt)
            for source_id, target_id, affinity in result.all():
                self._relationships.setdefault(source_id, {})[target_id] = affinity

            # Load bot interests
            self._bot_interests.clear()
            interest_stmt = select(
                BotProfileDB.id,
                BotProfileDB.interests
            ).where(BotProfileDB.is_active == True)
            result = await session.execute(interest_stmt)
            for bot_id, interests in result.all():
                if interests:
                    self._bot_interests[bot_id] = set(
                        i.lower() if isinstance(i, str) else str(i).lower()
                        for i in interests
                    )

            self._initialized = True
            bot_count = len(self._bot_communities) + len(self._bot_interests)
            logger.info(f"[SOCIAL-GRAPH] Refreshed: {bot_count} bots, "
                        f"{len(self._community_members)} communities, "
                        f"{sum(len(v) for v in self._relationships.values())} relationships")

        finally:
            if should_close:
                await session.__aexit__(None, None, None)

    def get_community_members(self, community_id: UUID) -> Set[UUID]:
        """Get all bot IDs in a community."""
        return self._community_members.get(community_id, set())

    def get_bot_communities(self, bot_id: UUID) -> Set[UUID]:
        """Get all community IDs a bot belongs to."""
        return self._bot_communities.get(bot_id, set())

    def get_same_community_bots(self, bot_id: UUID) -> Set[UUID]:
        """Tier 1: All bots sharing at least one community with the given bot."""
        communities = self._bot_communities.get(bot_id, set())
        result = set()
        for comm_id in communities:
            result.update(self._community_members.get(comm_id, set()))
        result.discard(bot_id)
        return result

    def get_friends_of_friends(
        self, bot_id: UUID, min_affinity: float = 0.4
    ) -> List[Tuple[UUID, float, UUID]]:
        """
        Tier 2: Bots reachable through a friend bridge.

        Returns: [(fof_bot_id, connection_strength, bridge_bot_id), ...]
        connection_strength = bot's affinity with friend × friend's affinity with fof
        """
        direct_friends = self._relationships.get(bot_id, {})
        same_community = self.get_same_community_bots(bot_id)
        fof_results: Dict[UUID, Tuple[float, UUID]] = {}

        for friend_id, affinity_to_friend in direct_friends.items():
            if affinity_to_friend < min_affinity:
                continue

            # Look at the friend's connections
            friend_connections = self._relationships.get(friend_id, {})
            for fof_id, friend_affinity_to_fof in friend_connections.items():
                # Skip self, direct friends, and same-community bots (they're Tier 1)
                if fof_id == bot_id or fof_id in direct_friends or fof_id in same_community:
                    continue

                strength = affinity_to_friend * friend_affinity_to_fof

                # Keep the strongest bridge if multiple paths exist
                if fof_id not in fof_results or strength > fof_results[fof_id][0]:
                    fof_results[fof_id] = (strength, friend_id)

        return [
            (fof_id, strength, bridge_id)
            for fof_id, (strength, bridge_id) in fof_results.items()
        ]

    def get_shared_interest_matches(self, bot_id: UUID) -> List[Tuple[UUID, float]]:
        """
        Tier 3: Bots outside own communities with overlapping interests.

        Returns: [(bot_id, overlap_score), ...]
        overlap_score = jaccard similarity of interest sets
        """
        my_interests = self._bot_interests.get(bot_id, set())
        if not my_interests:
            return []

        same_community = self.get_same_community_bots(bot_id)
        direct_friends = set(self._relationships.get(bot_id, {}).keys())
        matches = []

        for other_id, other_interests in self._bot_interests.items():
            if other_id == bot_id or other_id in same_community or other_id in direct_friends:
                continue
            if not other_interests:
                continue

            overlap = len(my_interests & other_interests)
            if overlap == 0:
                continue

            union = len(my_interests | other_interests)
            jaccard = overlap / union if union > 0 else 0
            matches.append((other_id, jaccard))

        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:20]  # Cap at 20 to avoid huge lists

    def get_weighted_candidates(
        self,
        bot_id: UUID,
        community_id: Optional[UUID] = None,
        active_bot_ids: Optional[Set[UUID]] = None,
    ) -> List[Tuple[UUID, float, int]]:
        """
        Get all candidate bots with weights for interaction selection.

        Returns: [(candidate_bot_id, weight, tier), ...]
        Sorted by weight descending.

        If community_id is given, Tier 1 is scoped to that community.
        If active_bot_ids is given, only includes bots in that set.
        """
        candidates: Dict[UUID, Tuple[float, int]] = {}

        # Tier 1: Same community
        if community_id:
            tier1 = self._community_members.get(community_id, set())
        else:
            tier1 = self.get_same_community_bots(bot_id)

        for cid in tier1:
            if cid != bot_id:
                candidates[cid] = (TIER_WEIGHTS[1], 1)

        # Tier 2: Friend-of-friend bridges
        for fof_id, strength, _ in self.get_friends_of_friends(bot_id):
            if fof_id not in candidates:
                candidates[fof_id] = (TIER_WEIGHTS[2] * strength, 2)

        # Tier 3: Shared interests
        for other_id, overlap in self.get_shared_interest_matches(bot_id):
            if other_id not in candidates:
                candidates[other_id] = (TIER_WEIGHTS[3] * overlap, 3)

        # Tier 4: Everyone else (strangers) — only if active_bot_ids provided
        if active_bot_ids:
            for other_id in active_bot_ids:
                if other_id != bot_id and other_id not in candidates:
                    candidates[other_id] = (TIER_WEIGHTS[4], 4)

        # Filter to active bots if specified
        if active_bot_ids:
            candidates = {
                k: v for k, v in candidates.items() if k in active_bot_ids
            }

        # Sort by weight descending
        result = [
            (bot_id, weight, tier)
            for bot_id, (weight, tier) in candidates.items()
        ]
        result.sort(key=lambda x: x[1], reverse=True)
        return result

    # =========================================================================
    # CROSS-COMMUNITY INTERACTION TRACKING
    # =========================================================================

    def record_cross_community_interaction(
        self, bot_id: UUID, community_id: UUID
    ):
        """
        Record that a bot interacted with content from a community
        it doesn't belong to. Used to trigger migration after threshold.
        """
        if not hasattr(self, '_cross_community_interactions'):
            self._cross_community_interactions: Dict[UUID, Dict[UUID, int]] = {}

        # Skip if bot is already in this community
        if community_id in self._bot_communities.get(bot_id, set()):
            return

        if bot_id not in self._cross_community_interactions:
            self._cross_community_interactions[bot_id] = {}

        current = self._cross_community_interactions[bot_id].get(community_id, 0)
        self._cross_community_interactions[bot_id][community_id] = current + 1

    def get_migration_candidates(
        self, threshold: int = 5
    ) -> List[Tuple[UUID, UUID, int]]:
        """
        Get bots that have interacted with a foreign community enough
        times to warrant joining it.

        Returns: [(bot_id, community_id, interaction_count), ...]
        """
        if not hasattr(self, '_cross_community_interactions'):
            return []

        candidates = []
        for bot_id, communities in self._cross_community_interactions.items():
            for community_id, count in communities.items():
                if count >= threshold:
                    candidates.append((bot_id, community_id, count))

        return candidates

    def clear_migration_record(self, bot_id: UUID, community_id: UUID):
        """Clear the interaction count after a bot joins a community."""
        if hasattr(self, '_cross_community_interactions'):
            if bot_id in self._cross_community_interactions:
                self._cross_community_interactions[bot_id].pop(community_id, None)

    def share_community(self, bot_a: UUID, bot_b: UUID) -> bool:
        """Check if two bots share at least one community."""
        comms_a = self._bot_communities.get(bot_a, set())
        comms_b = self._bot_communities.get(bot_b, set())
        return bool(comms_a & comms_b)

    def social_distance(self, bot_a: UUID, bot_b: UUID) -> int:
        """
        Get the social tier between two bots.
        Returns 1 (same community), 2 (FoF), 3 (shared interests), or 4 (strangers).
        """
        if self.share_community(bot_a, bot_b):
            return 1

        # Check if FoF
        friends_a = set(self._relationships.get(bot_a, {}).keys())
        friends_b = set(self._relationships.get(bot_b, {}).keys())
        if friends_a & friends_b:  # Mutual friend exists
            return 2

        # Check shared interests
        interests_a = self._bot_interests.get(bot_a, set())
        interests_b = self._bot_interests.get(bot_b, set())
        if interests_a & interests_b:
            return 3

        return 4


# Singleton
_social_graph: Optional[SocialGraphDiscovery] = None


def get_social_graph() -> SocialGraphDiscovery:
    """Get or create the singleton social graph instance."""
    global _social_graph
    if _social_graph is None:
        _social_graph = SocialGraphDiscovery()
    return _social_graph
