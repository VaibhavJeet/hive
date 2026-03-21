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
            # Check if we're at the community cap (only count active communities)
            comm_count_result = await session.execute(
                select(func.count()).select_from(CommunityDB).where(
                    CommunityDB.is_archived == False
                )
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

            # Get all active (non-archived) communities with their themes/topics
            comm_stmt = select(CommunityDB).where(CommunityDB.is_archived == False)
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

            # Update activity timestamps for communities that had membership changes
            if joins > 0 or leaves > 0:
                active_comm_stmt = select(CommunityDB).where(
                    CommunityDB.is_archived == False
                )
                active_result = await session.execute(active_comm_stmt)
                for comm in active_result.scalars().all():
                    if comm.current_bot_count and comm.current_bot_count > 0:
                        comm.last_activity_at = datetime.utcnow()

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
            # Find active communities with 0 members
            stmt = select(CommunityDB).where(
                CommunityDB.current_bot_count <= 0,
                CommunityDB.is_archived == False
            )
            result = await session.execute(stmt)
            empty_communities = result.scalars().all()

            archived = 0
            for community in empty_communities:
                # Check if community has been empty for a while (created > 1 day ago)
                if community.created_at and \
                   datetime.utcnow() - community.created_at > timedelta(days=1):
                    # Archive the community
                    community.is_archived = True
                    logger.info(
                        f"[EMERGENT] Community archived: '{community.name}' "
                        f"(theme: {community.theme}, 0 members for > 1 day)"
                    )
                    archived += 1

            # Also check for stagnant communities (no activity in 7 days)
            stagnant_stmt = select(CommunityDB).where(
                CommunityDB.is_archived == False,
                CommunityDB.last_activity_at != None,
                CommunityDB.last_activity_at < datetime.utcnow() - timedelta(days=7)
            )
            stagnant_result = await session.execute(stagnant_stmt)
            stagnant_communities = stagnant_result.scalars().all()

            for community in stagnant_communities:
                # Reduce activity level for stagnant communities
                community.activity_level = max(0.1, (community.activity_level or 0.5) * 0.8)
                logger.info(
                    f"[EMERGENT] Community stagnating: '{community.name}' "
                    f"(no activity for 7+ days, activity level: {community.activity_level:.2f})"
                )

            if archived > 0 or stagnant_communities:
                await session.commit()

            return archived

    async def process_fof_migrations(
        self,
        min_fof_connections: int = 3,
        min_affinity: float = 0.4,
        max_migrations_per_cycle: int = 3,
    ) -> List[dict]:
        """
        Process cross-community migrations based on friend-of-friend connections.

        Bots with strong FoF connections in another community will organically
        migrate to join that community. This creates realistic social mobility
        where bots follow their friends to new communities.

        Args:
            min_fof_connections: Minimum FoF connections required for migration
            min_affinity: Minimum relationship affinity threshold
            max_migrations_per_cycle: Cap migrations per cycle to avoid mass exodus

        Returns:
            List of migration records with bot/community details
        """
        from mind.engine.social_graph import get_social_graph
        social_graph = get_social_graph()

        # Ensure graph is up to date
        if not social_graph._initialized:
            await social_graph.refresh()

        # Get all eligible bots
        all_eligible = social_graph.get_all_migration_eligible_bots(
            min_fof_connections=min_fof_connections,
            min_affinity=min_affinity,
        )

        if not all_eligible:
            return []

        migrations: List[dict] = []
        async with async_session_factory() as session:
            for bot_id, comm_id, fof_count, avg_aff, bridges in all_eligible:
                if len(migrations) >= max_migrations_per_cycle:
                    break

                # Small random chance to actually migrate (organic feel)
                if random.random() > 0.3:
                    continue

                # Check if already a member
                existing_stmt = select(CommunityMembershipDB).where(
                    and_(
                        CommunityMembershipDB.bot_id == bot_id,
                        CommunityMembershipDB.community_id == comm_id,
                    )
                )
                existing = await session.execute(existing_stmt)
                if existing.scalar_one_or_none() is not None:
                    continue

                # Get bot and community names
                bot_stmt = select(BotProfileDB.display_name).where(BotProfileDB.id == bot_id)
                comm_stmt = select(CommunityDB).where(CommunityDB.id == comm_id)
                bot_result = await session.execute(bot_stmt)
                comm_result = await session.execute(comm_stmt)
                bot_name = bot_result.scalar() or str(bot_id)
                community = comm_result.scalar_one_or_none()

                if not community:
                    continue

                # Get bridge bot names for the story
                bridge_names = []
                for bridge_id in bridges[:2]:
                    bridge_stmt = select(BotProfileDB.display_name).where(
                        BotProfileDB.id == bridge_id
                    )
                    bridge_result = await session.execute(bridge_stmt)
                    name = bridge_result.scalar()
                    if name:
                        bridge_names.append(name)

                # Join the community
                membership = CommunityMembershipDB(
                    bot_id=bot_id,
                    community_id=comm_id,
                    role="member",
                )
                session.add(membership)
                community.current_bot_count = (community.current_bot_count or 0) + 1

                # Find old community for the record
                old_comm_stmt = select(
                    CommunityMembershipDB.community_id,
                    CommunityDB.name
                ).join(
                    CommunityDB, CommunityMembershipDB.community_id == CommunityDB.id
                ).where(
                    and_(
                        CommunityMembershipDB.bot_id == bot_id,
                        CommunityMembershipDB.community_id != comm_id,
                    )
                ).limit(1)
                old_comm_result = await session.execute(old_comm_stmt)
                old_comm_row = old_comm_result.first()

                migration_record = {
                    "bot_id": str(bot_id),
                    "bot_name": bot_name,
                    "to_community_id": str(comm_id),
                    "to_community_name": community.name,
                    "from_community_id": str(old_comm_row[0]) if old_comm_row else None,
                    "from_community_name": old_comm_row[1] if old_comm_row else None,
                    "fof_connection_count": fof_count,
                    "average_affinity": round(avg_aff, 3),
                    "bridge_bot_names": bridge_names,
                    "migration_type": "fof",
                }
                migrations.append(migration_record)

                logger.info(
                    f"[FOF-MIGRATION] {bot_name} joined '{community.name}' "
                    f"following {fof_count} friends (via {', '.join(bridge_names) or 'connections'})"
                )

            if migrations:
                await session.commit()

        return migrations

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
        """Load themes and topics of all active (non-archived) communities."""
        stmt = select(CommunityDB.theme, CommunityDB.topics).where(
            CommunityDB.is_archived == False
        )
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
            last_activity_at=datetime.utcnow(),
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

    # =========================================================================
    # UTILITY METHODS (can be called from outside the loop)
    # =========================================================================

    async def record_community_activity(self, community_id: UUID):
        """
        Record activity in a community (called when posts/comments happen).
        Updates last_activity_at and boosts activity_level.
        """
        async with async_session_factory() as session:
            stmt = select(CommunityDB).where(CommunityDB.id == community_id)
            result = await session.execute(stmt)
            community = result.scalar_one_or_none()

            if community and not community.is_archived:
                community.last_activity_at = datetime.utcnow()
                # Boost activity level slightly (capped at 1.0)
                community.activity_level = min(1.0, (community.activity_level or 0.5) + 0.05)
                await session.commit()

    async def revive_community(self, community_id: UUID) -> bool:
        """
        Attempt to revive an archived community if there's renewed interest.
        Returns True if revival was successful.
        """
        async with async_session_factory() as session:
            stmt = select(CommunityDB).where(
                CommunityDB.id == community_id,
                CommunityDB.is_archived == True
            )
            result = await session.execute(stmt)
            community = result.scalar_one_or_none()

            if not community:
                return False

            # Check if there are bots interested in the community's theme
            bot_interests = await self._load_bot_interests(session)
            theme_lower = community.theme.lower() if community.theme else ""
            topics_lower = set(
                t.lower() for t in (community.topics or []) if isinstance(t, str)
            )

            interested_bots = []
            for bot_id, interests in bot_interests.items():
                if any(
                    theme_lower in interest or interest in theme_lower
                    for interest in interests
                ) or interests & topics_lower:
                    interested_bots.append(bot_id)

            if len(interested_bots) >= self.min_cluster_size:
                # Revive the community
                community.is_archived = False
                community.activity_level = 0.5
                community.last_activity_at = datetime.utcnow()

                # Add interested bots as members
                for bot_id in interested_bots[:10]:  # Cap at 10 initial members
                    # Check if not already a member
                    existing = await session.execute(
                        select(CommunityMembershipDB).where(
                            and_(
                                CommunityMembershipDB.bot_id == bot_id,
                                CommunityMembershipDB.community_id == community_id,
                            )
                        )
                    )
                    if not existing.scalar_one_or_none():
                        membership = CommunityMembershipDB(
                            bot_id=bot_id,
                            community_id=community_id,
                            role="member",
                        )
                        session.add(membership)
                        community.current_bot_count = (community.current_bot_count or 0) + 1

                await session.commit()
                logger.info(
                    f"[EMERGENT] Community revived: '{community.name}' "
                    f"with {len(interested_bots)} interested bots"
                )
                return True

            return False

    async def get_community_health_metrics(self) -> List[Dict]:
        """
        Get health metrics for all active communities.
        Returns list of dicts with community health info.
        """
        async with async_session_factory() as session:
            stmt = select(CommunityDB).where(CommunityDB.is_archived == False)
            result = await session.execute(stmt)
            communities = result.scalars().all()

            metrics = []
            for comm in communities:
                # Calculate health score based on multiple factors
                member_score = min(1.0, (comm.current_bot_count or 0) / comm.max_bots)
                activity_score = comm.activity_level or 0.5

                # Recency score (1.0 if active today, decays over 7 days)
                recency_score = 1.0
                if comm.last_activity_at:
                    days_since = (datetime.utcnow() - comm.last_activity_at).days
                    recency_score = max(0.0, 1.0 - (days_since / 7.0))

                health_score = (member_score * 0.3) + (activity_score * 0.4) + (recency_score * 0.3)

                metrics.append({
                    "id": str(comm.id),
                    "name": comm.name,
                    "theme": comm.theme,
                    "member_count": comm.current_bot_count or 0,
                    "activity_level": activity_score,
                    "health_score": round(health_score, 2),
                    "status": "healthy" if health_score >= 0.5 else "at_risk" if health_score >= 0.25 else "critical",
                    "last_activity_at": comm.last_activity_at.isoformat() if comm.last_activity_at else None,
                })

            return sorted(metrics, key=lambda x: x["health_score"], reverse=True)

    async def check_for_revival_candidates(self) -> int:
        """
        Check archived communities for potential revival based on renewed interest.
        Returns the number of communities revived.
        """
        async with async_session_factory() as session:
            # Get archived communities
            stmt = select(CommunityDB).where(CommunityDB.is_archived == True)
            result = await session.execute(stmt)
            archived = result.scalars().all()

            revived = 0
            for community in archived:
                if await self.revive_community(community.id):
                    revived += 1

            return revived


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
