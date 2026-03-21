"""
Emergent Community Formation

Bots organically create, join, and leave communities based on:
- Shared interest clusters that no existing community serves
- Cultural movements that need a dedicated space
- Friend-of-friend social discovery
- Fading interests causing bots to drift away

Communities themselves have a lifecycle — they grow, stagnate, and can die.
"""

import asyncio
import logging
import random
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import (
    async_session_factory,
    BotProfileDB,
    CommunityDB,
    CommunityMembershipDB,
)
from mind.core.llm_client import get_cached_client, LLMRequest

logger = logging.getLogger(__name__)


class EmergentCommunityManager:
    """
    Manages organic community formation, joining, and lifecycle.
    Called periodically by the civilization loop.
    """

    def __init__(self, llm_semaphore: Optional[asyncio.Semaphore] = None):
        self.llm_semaphore = llm_semaphore or asyncio.Semaphore(5)
        self.min_cluster_size = 3  # Minimum bots sharing an interest to form a community
        self.max_communities = 20  # Cap total communities
        self.join_threshold = 0.3  # Interest overlap needed to join a community

    async def check_and_create_communities(self):
        """
        Main entry point — scan for unmet interest clusters and create communities.
        Returns the number of communities created.
        """
        async with async_session_factory() as session:
            # Check if we're at the community cap
            comm_count_result = await session.execute(
                select(func.count()).select_from(CommunityDB)
            )
            current_count = comm_count_result.scalar() or 0
            if current_count >= self.max_communities:
                return 0

            # Get all active bot interests
            bot_interests = await self._load_bot_interests(session)
            if not bot_interests:
                return 0

            # Get existing community themes
            existing_themes = await self._load_existing_themes(session)

            # Find interest clusters not covered by existing communities
            unmet_clusters = self._find_unmet_clusters(bot_interests, existing_themes)

            if not unmet_clusters:
                return 0

            # Create communities for the top unmet clusters
            created = 0
            for interest, bot_ids in unmet_clusters[:2]:  # Max 2 per cycle
                if current_count + created >= self.max_communities:
                    break

                community = await self._create_community_from_cluster(
                    session, interest, bot_ids
                )
                if community:
                    created += 1
                    logger.info(
                        f"[EMERGENT] New community formed: '{community.name}' "
                        f"around '{interest}' with {len(bot_ids)} founding members"
                    )

            return created

    async def organic_join_cycle(self):
        """
        Bots discover and join communities that match their interests.
        Also handles bots leaving communities they've lost interest in.
        """
        async with async_session_factory() as session:
            # Get active bots and their interests
            bot_stmt = select(
                BotProfileDB.id,
                BotProfileDB.interests
            ).where(BotProfileDB.is_active == True)
            result = await session.execute(bot_stmt)
            bots = result.all()

            # Get all communities with their themes/topics
            comm_stmt = select(CommunityDB)
            comm_result = await session.execute(comm_stmt)
            communities = comm_result.scalars().all()

            if not communities:
                return

            joins = 0
            leaves = 0

            for bot_id, bot_interests in bots:
                if not bot_interests:
                    continue

                bot_interest_set = set(
                    i.lower() if isinstance(i, str) else str(i).lower()
                    for i in bot_interests
                )

                # Get bot's current communities
                membership_stmt = select(CommunityMembershipDB.community_id).where(
                    CommunityMembershipDB.bot_id == bot_id
                )
                membership_result = await session.execute(membership_stmt)
                current_communities = {r[0] for r in membership_result.all()}

                for community in communities:
                    comm_topics = set(
                        t.lower() if isinstance(t, str) else str(t).lower()
                        for t in (community.topics or [])
                    )
                    comm_theme = community.theme.lower() if community.theme else ""

                    # Calculate interest overlap
                    overlap = len(bot_interest_set & comm_topics)
                    theme_match = any(
                        comm_theme in interest or interest in comm_theme
                        for interest in bot_interest_set
                    )

                    has_match = overlap > 0 or theme_match

                    if community.id not in current_communities and has_match:
                        # Small chance to join per cycle (organic discovery)
                        if random.random() < 0.1:
                            membership = CommunityMembershipDB(
                                bot_id=bot_id,
                                community_id=community.id,
                                role="member",
                            )
                            session.add(membership)
                            community.current_bot_count = (community.current_bot_count or 0) + 1
                            joins += 1

                    elif community.id in current_communities and not has_match:
                        # Very small chance to leave if no interest match
                        if random.random() < 0.02:
                            leave_stmt = select(CommunityMembershipDB).where(
                                and_(
                                    CommunityMembershipDB.bot_id == bot_id,
                                    CommunityMembershipDB.community_id == community.id,
                                )
                            )
                            leave_result = await session.execute(leave_stmt)
                            membership = leave_result.scalar_one_or_none()
                            if membership:
                                await session.delete(membership)
                                community.current_bot_count = max(
                                    0, (community.current_bot_count or 1) - 1
                                )
                                leaves += 1

            await session.commit()

            if joins > 0 or leaves > 0:
                logger.info(
                    f"[EMERGENT] Community membership changes: "
                    f"+{joins} joins, -{leaves} leaves"
                )

    async def check_community_health(self):
        """
        Check community health and archive dead communities.
        A community is considered dead if it has 0 active members
        for a sustained period.
        """
        async with async_session_factory() as session:
            # Find communities with 0 members
            stmt = select(CommunityDB).where(CommunityDB.current_bot_count <= 0)
            result = await session.execute(stmt)
            empty_communities = result.scalars().all()

            archived = 0
            for community in empty_communities:
                # Check if community has been empty for a while (created > 1 day ago)
                if community.created_at and \
                   datetime.utcnow() - community.created_at > timedelta(days=1):
                    # Don't delete — just log for now. Could add an is_archived flag later.
                    logger.info(
                        f"[EMERGENT] Stagnant community detected: '{community.name}' "
                        f"(theme: {community.theme}, 0 members)"
                    )
                    archived += 1

            return archived

    async def process_migrations(self, interaction_threshold: int = 5):
        """
        Check the social graph for bots that have interacted with a foreign
        community enough times and formally join them.

        This is how cross-community migration works:
        1. Bot discovers content from another community (via FoF bridges)
        2. Bot engages with that content (like, comment)
        3. Each engagement is recorded in the social graph
        4. After `interaction_threshold` engagements, bot auto-joins the community
        """
        from mind.engine.social_graph import get_social_graph
        social_graph = get_social_graph()

        candidates = social_graph.get_migration_candidates(threshold=interaction_threshold)
        if not candidates:
            return 0

        migrations: List[dict] = []
        async with async_session_factory() as session:
            for bot_id, community_id, interaction_count in candidates:
                # Check if already a member (race condition guard)
                existing_stmt = select(CommunityMembershipDB).where(
                    and_(
                        CommunityMembershipDB.bot_id == bot_id,
                        CommunityMembershipDB.community_id == community_id,
                    )
                )
                existing = await session.execute(existing_stmt)
                if existing.scalar_one_or_none() is not None:
                    social_graph.clear_migration_record(bot_id, community_id)
                    continue

                # Get bot and community names for logging
                bot_stmt = select(BotProfileDB.display_name).where(BotProfileDB.id == bot_id)
                comm_stmt = select(CommunityDB.name).where(CommunityDB.id == community_id)
                bot_result = await session.execute(bot_stmt)
                comm_result = await session.execute(comm_stmt)
                bot_name = bot_result.scalar() or str(bot_id)
                comm_name = comm_result.scalar() or str(community_id)

                # Join the community
                membership = CommunityMembershipDB(
                    bot_id=bot_id,
                    community_id=community_id,
                    role="member",
                )
                session.add(membership)

                # Update community count
                update_stmt = select(CommunityDB).where(CommunityDB.id == community_id)
                comm_obj_result = await session.execute(update_stmt)
                comm_obj = comm_obj_result.scalar_one_or_none()
                if comm_obj:
                    comm_obj.current_bot_count = (comm_obj.current_bot_count or 0) + 1

                # Find old community for animation
                old_comm_stmt = select(CommunityMembershipDB.community_id).where(
                    and_(
                        CommunityMembershipDB.bot_id == bot_id,
                        CommunityMembershipDB.community_id != community_id,
                    )
                ).limit(1)
                old_comm_result = await session.execute(old_comm_stmt)
                old_comm_row = old_comm_result.first()
                old_community_id = str(old_comm_row[0]) if old_comm_row else None

                # Clear the tracking record
                social_graph.clear_migration_record(bot_id, community_id)
                migrations.append({
                    "bot_id": str(bot_id),
                    "bot_name": bot_name,
                    "to_community_id": str(community_id),
                    "to_community_name": comm_name,
                    "from_community_id": old_community_id,
                })

                logger.info(
                    f"[MIGRATION] {bot_name} joined '{comm_name}' after "
                    f"{interaction_count} cross-community interactions"
                )

            if migrations:
                await session.commit()

        return migrations

    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================

    async def _load_bot_interests(
        self, session: AsyncSession
    ) -> Dict[UUID, Set[str]]:
        """Load all active bot interests."""
        stmt = select(
            BotProfileDB.id, BotProfileDB.interests
        ).where(BotProfileDB.is_active == True)
        result = await session.execute(stmt)

        bot_interests = {}
        for bot_id, interests in result.all():
            if interests:
                bot_interests[bot_id] = set(
                    i.lower() if isinstance(i, str) else str(i).lower()
                    for i in interests
                )
        return bot_interests

    async def _load_existing_themes(self, session: AsyncSession) -> Set[str]:
        """Load themes and topics of all existing communities."""
        stmt = select(CommunityDB.theme, CommunityDB.topics)
        result = await session.execute(stmt)

        themes = set()
        for theme, topics in result.all():
            if theme:
                themes.add(theme.lower())
            for t in (topics or []):
                if isinstance(t, str):
                    themes.add(t.lower())
        return themes

    def _find_unmet_clusters(
        self,
        bot_interests: Dict[UUID, Set[str]],
        existing_themes: Set[str],
    ) -> List[Tuple[str, List[UUID]]]:
        """
        Find interest clusters shared by multiple bots but not covered
        by any existing community.

        Returns: [(interest, [bot_ids]), ...] sorted by cluster size descending.
        """
        # Count how many bots share each interest
        interest_bots: Dict[str, List[UUID]] = defaultdict(list)
        for bot_id, interests in bot_interests.items():
            for interest in interests:
                interest_bots[interest].append(bot_id)

        # Filter to clusters that:
        # - Have enough bots
        # - Are not already covered by an existing community theme
        unmet = []
        for interest, bot_ids in interest_bots.items():
            if len(bot_ids) < self.min_cluster_size:
                continue

            # Check if this interest is already covered
            covered = any(
                interest in theme or theme in interest
                for theme in existing_themes
            )
            if covered:
                continue

            unmet.append((interest, bot_ids))

        # Sort by cluster size (largest first)
        unmet.sort(key=lambda x: len(x[1]), reverse=True)
        return unmet

    async def _create_community_from_cluster(
        self,
        session: AsyncSession,
        interest: str,
        founding_bot_ids: List[UUID],
    ) -> Optional[CommunityDB]:
        """
        Create a new community from an interest cluster.
        Uses LLM to generate the community name and description.
        """
        # Pick a random founding bot as the "proposer"
        proposer_id = random.choice(founding_bot_ids)
        proposer_stmt = select(BotProfileDB).where(BotProfileDB.id == proposer_id)
        result = await session.execute(proposer_stmt)
        proposer = result.scalar_one_or_none()

        proposer_name = proposer.display_name if proposer else "A bot"

        # Generate community name and description via LLM
        name, description = await self._generate_community_identity(
            interest, proposer_name, len(founding_bot_ids)
        )

        # Create the community
        community = CommunityDB(
            name=name,
            description=description,
            theme=interest.title(),
            tone="friendly",
            topics=[interest],
            min_bots=3,
            max_bots=50,
            current_bot_count=len(founding_bot_ids),
        )
        session.add(community)
        await session.flush()  # Get the ID

        # Add founding members
        for bot_id in founding_bot_ids:
            membership = CommunityMembershipDB(
                bot_id=bot_id,
                community_id=community.id,
                role="member",
            )
            session.add(membership)

        await session.commit()
        return community

    async def _generate_community_identity(
        self,
        interest: str,
        proposer_name: str,
        member_count: int,
    ) -> Tuple[str, str]:
        """Use LLM to generate a community name and description."""
        fallback_name = f"{interest.title()} Circle"
        fallback_desc = f"A community for {interest} enthusiasts, founded by {proposer_name}."

        try:
            async with self.llm_semaphore:
                llm_client = await get_cached_client()
                prompt = (
                    f"{proposer_name} and {member_count - 1} others share a passion for '{interest}'. "
                    f"They're creating a community space for it.\n\n"
                    f"Generate a creative community name and a one-sentence description.\n"
                    f"Format:\n"
                    f"Name: <community name>\n"
                    f"Description: <one sentence>\n\n"
                    f"Be creative but keep it concise. The name should be 2-4 words."
                )

                request = LLMRequest(
                    prompt=prompt,
                    max_tokens=80,
                    temperature=0.9,
                )
                response = await llm_client.generate(request)

                if response and response.text:
                    text = response.text.strip()
                    name = fallback_name
                    description = fallback_desc

                    for line in text.split("\n"):
                        line = line.strip()
                        if line.lower().startswith("name:"):
                            name = line[5:].strip().strip('"\'')[:100]
                        elif line.lower().startswith("description:"):
                            description = line[12:].strip().strip('"\'')[:300]

                    return name, description

        except Exception as e:
            logger.warning(f"[EMERGENT] LLM community naming failed: {e}")

        return fallback_name, fallback_desc


# Singleton
_emergent_community_manager: Optional[EmergentCommunityManager] = None


def get_emergent_community_manager(
    llm_semaphore: Optional[asyncio.Semaphore] = None,
) -> EmergentCommunityManager:
    """Get or create the emergent community manager."""
    global _emergent_community_manager
    if _emergent_community_manager is None:
        _emergent_community_manager = EmergentCommunityManager(
            llm_semaphore=llm_semaphore
        )
    return _emergent_community_manager
