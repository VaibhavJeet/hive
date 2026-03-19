"""
Community Orchestrator for AI Community Companions.
Manages communities, bot populations, and activity levels.
"""

import random
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from uuid import UUID, uuid4

from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.types import Community, BotProfile, ActivityType
from mind.core.database import (
    CommunityDB, CommunityMembershipDB, BotProfileDB,
    async_session_factory
)
from mind.agents.personality_generator import PersonalityGenerator
from mind.scheduler.activity_scheduler import BotOrchestrator, ActivityScheduler


# ============================================================================
# COMMUNITY TEMPLATES
# ============================================================================

COMMUNITY_TEMPLATES = {
    "creative": {
        "themes": ["Art & Design", "Photography", "Music Production", "Writing"],
        "tone": "supportive",
        "topics": ["creativity", "inspiration", "techniques", "feedback", "collaboration"],
        "min_bots": 30,
        "max_bots": 100,
    },
    "tech": {
        "themes": ["Programming", "AI/ML", "Gaming", "Hardware"],
        "tone": "helpful",
        "topics": ["coding", "tutorials", "debugging", "projects", "news"],
        "min_bots": 40,
        "max_bots": 120,
    },
    "lifestyle": {
        "themes": ["Fitness", "Cooking", "Travel", "Fashion"],
        "tone": "friendly",
        "topics": ["tips", "experiences", "recommendations", "motivation"],
        "min_bots": 35,
        "max_bots": 100,
    },
    "entertainment": {
        "themes": ["Movies & TV", "Books", "Anime", "Gaming"],
        "tone": "casual",
        "topics": ["reviews", "discussions", "recommendations", "memes", "theories"],
        "min_bots": 50,
        "max_bots": 150,
    },
    "support": {
        "themes": ["Mental Health", "Career Advice", "Relationships", "Self-Improvement"],
        "tone": "compassionate",
        "topics": ["experiences", "advice", "support", "resources", "encouragement"],
        "min_bots": 25,
        "max_bots": 80,
    },
    "hobby": {
        "themes": ["DIY & Crafts", "Gardening", "Pets", "Board Games"],
        "tone": "enthusiastic",
        "topics": ["projects", "tips", "show-and-tell", "questions", "recommendations"],
        "min_bots": 30,
        "max_bots": 90,
    },
}


# ============================================================================
# COMMUNITY MANAGER
# ============================================================================

class CommunityManager:
    """Manages individual communities and their bot populations."""

    def __init__(self, personality_generator: PersonalityGenerator):
        self.personality_generator = personality_generator

    async def create_community(
        self,
        session: AsyncSession,
        name: str,
        description: str,
        theme: str,
        tone: str = "friendly",
        topics: Optional[List[str]] = None,
        min_bots: int = 30,
        max_bots: int = 100,
        initial_bot_count: int = 50
    ) -> Community:
        """Create a new community with initial bot population."""
        # Create community in database
        community_db = CommunityDB(
            name=name,
            description=description,
            theme=theme,
            tone=tone,
            topics=topics or [],
            min_bots=min_bots,
            max_bots=max_bots,
        )

        session.add(community_db)
        await session.commit()
        await session.refresh(community_db)

        # Generate initial bot population
        bots = await self._populate_community(
            session,
            community_db.id,
            theme,
            count=initial_bot_count
        )

        # Update bot count
        community_db.current_bot_count = len(bots)
        await session.commit()

        return Community(
            id=community_db.id,
            name=community_db.name,
            description=community_db.description,
            theme=community_db.theme,
            topics=community_db.topics,
            tone=community_db.tone,
            min_bots=community_db.min_bots,
            max_bots=community_db.max_bots,
            current_bot_count=community_db.current_bot_count,
        )

    async def _populate_community(
        self,
        session: AsyncSession,
        community_id: UUID,
        theme: str,
        count: int
    ) -> List[BotProfile]:
        """Generate and add bots to a community."""
        profiles = self.personality_generator.generate_batch(
            count=count,
            community_theme=theme,
            ensure_diversity=True
        )

        bots = []
        for profile in profiles:
            # Create bot in database
            bot_db = BotProfileDB(
                id=profile.id,
                display_name=profile.display_name,
                handle=profile.handle,
                bio=profile.bio,
                avatar_seed=profile.avatar_seed,
                is_ai_labeled=True,
                ai_label_text=profile.ai_label_text,
                age=profile.age,
                gender=profile.gender.value,
                location=profile.location,
                backstory=profile.backstory,
                interests=profile.interests,
                personality_traits=profile.personality_traits.model_dump(),
                writing_fingerprint=profile.writing_fingerprint.model_dump(),
                activity_pattern=profile.activity_pattern.model_dump(),
                emotional_state=profile.emotional_state.model_dump(),
            )
            session.add(bot_db)

            # Create membership
            membership = CommunityMembershipDB(
                bot_id=profile.id,
                community_id=community_id,
            )
            session.add(membership)

            bots.append(profile)

        await session.commit()
        return bots

    async def get_community_bots(
        self,
        session: AsyncSession,
        community_id: UUID,
        active_only: bool = True
    ) -> List[UUID]:
        """Get bot IDs for a community."""
        conditions = [CommunityMembershipDB.community_id == community_id]

        if active_only:
            # Join with bot profiles to check active status
            stmt = (
                select(CommunityMembershipDB.bot_id)
                .join(BotProfileDB)
                .where(
                    and_(
                        CommunityMembershipDB.community_id == community_id,
                        BotProfileDB.is_active == True
                    )
                )
            )
        else:
            stmt = select(CommunityMembershipDB.bot_id).where(*conditions)

        result = await session.execute(stmt)
        return [row[0] for row in result.all()]

    async def scale_bot_population(
        self,
        session: AsyncSession,
        community_id: UUID,
        target_count: int
    ):
        """Scale bot population to target count."""
        # Get current count
        count_stmt = (
            select(func.count())
            .select_from(CommunityMembershipDB)
            .where(CommunityMembershipDB.community_id == community_id)
        )
        result = await session.execute(count_stmt)
        current_count = result.scalar() or 0

        # Get community details
        comm_stmt = select(CommunityDB).where(CommunityDB.id == community_id)
        result = await session.execute(comm_stmt)
        community = result.scalar_one_or_none()

        if not community:
            return

        # Clamp target to allowed range
        target_count = max(community.min_bots, min(community.max_bots, target_count))

        if target_count > current_count:
            # Add more bots
            await self._populate_community(
                session,
                community_id,
                community.theme,
                count=target_count - current_count
            )
        elif target_count < current_count:
            # Retire some bots (mark as inactive)
            excess = current_count - target_count

            # Get least active bots
            stmt = (
                select(CommunityMembershipDB.bot_id)
                .join(BotProfileDB)
                .where(CommunityMembershipDB.community_id == community_id)
                .order_by(BotProfileDB.last_active.asc())
                .limit(excess)
            )
            result = await session.execute(stmt)
            bot_ids = [row[0] for row in result.all()]

            # Mark as inactive
            for bot_id in bot_ids:
                update_stmt = (
                    update(BotProfileDB)
                    .where(BotProfileDB.id == bot_id)
                    .values(is_active=False, is_retired=True)
                )
                await session.execute(update_stmt)

        # Update community count
        community.current_bot_count = target_count
        await session.commit()


# ============================================================================
# COMMUNITY ORCHESTRATOR
# ============================================================================

class CommunityOrchestrator:
    """
    High-level orchestrator for all communities.
    Manages activity levels, bot allocation, and engagement.
    """

    def __init__(
        self,
        community_manager: CommunityManager,
        scheduler: ActivityScheduler,
        seed: Optional[int] = None
    ):
        self.community_manager = community_manager
        self.scheduler = scheduler
        self.rng = random.Random(seed)
        self.bot_orchestrator = BotOrchestrator(scheduler, seed)

    async def initialize_platform(
        self,
        num_communities: int = 3
    ):
        """
        Initialize the platform with communities and bots.
        Creates a diverse ecosystem of communities.
        Respects MAX_ACTIVE_BOTS setting from config.
        """
        from mind.config.settings import settings

        async with async_session_factory() as session:
            communities_created = []

            # Respect MAX_ACTIVE_BOTS setting - distribute bots across communities
            max_total_bots = settings.MAX_ACTIVE_BOTS
            bots_per_community = max(4, max_total_bots // num_communities)

            # Distribute across templates
            templates = list(COMMUNITY_TEMPLATES.items())
            communities_per_template = num_communities // len(templates)
            remainder = num_communities % len(templates)

            for i, (template_key, template) in enumerate(templates):
                count = communities_per_template
                if i < remainder:
                    count += 1

                for j in range(count):
                    # Pick a specific theme
                    theme = self.rng.choice(template["themes"])

                    # Generate unique name
                    name = f"{theme} Community"
                    if j > 0:
                        name = f"{theme} {['Hub', 'Club', 'Space', 'Zone', 'Circle'][j % 5]}"

                    description = f"A {template['tone']} community for {theme.lower()} enthusiasts."

                    # Use configured bots per community (respecting MAX_ACTIVE_BOTS)
                    initial_bots = bots_per_community

                    community = await self.community_manager.create_community(
                        session=session,
                        name=name,
                        description=description,
                        theme=theme,
                        tone=template["tone"],
                        topics=template["topics"],
                        min_bots=template["min_bots"],
                        max_bots=template["max_bots"],
                        initial_bot_count=initial_bots
                    )

                    communities_created.append(community)
                    print(f"Created community: {name} with {initial_bots} AI companions")

            return communities_created

    async def seed_community_history(
        self,
        community_id: UUID,
        days_of_history: int = 7
    ):
        """
        Generate historical activity for a community.
        Creates the appearance of an established community.
        """
        async with async_session_factory() as session:
            # Get community bots
            bot_ids = await self.community_manager.get_community_bots(session, community_id)

            # Get community info
            stmt = select(CommunityDB).where(CommunityDB.id == community_id)
            result = await session.execute(stmt)
            community = result.scalar_one_or_none()

            if not community:
                return

            # Generate posts for each day
            now = datetime.utcnow()

            for days_ago in range(days_of_history, 0, -1):
                day = now - timedelta(days=days_ago)

                # Number of posts scales with bot count
                num_posts = max(3, len(bot_ids) // 10)

                for _ in range(num_posts):
                    # Select random bot
                    bot_id = self.rng.choice(bot_ids)

                    # Random time during the day
                    hour = self.rng.randint(8, 22)
                    minute = self.rng.randint(0, 59)
                    post_time = day.replace(hour=hour, minute=minute)

                    # This would trigger content generation
                    # For now, we're just setting up the structure
                    pass

    async def adjust_community_activity(
        self,
        community_id: UUID,
        real_user_engagement: float
    ):
        """
        Dynamically adjust bot activity based on real user engagement.

        As real users become more active, bots should become less prominent
        but still provide a baseline of activity.
        """
        async with async_session_factory() as session:
            stmt = select(CommunityDB).where(CommunityDB.id == community_id)
            result = await session.execute(stmt)
            community = result.scalar_one_or_none()

            if not community:
                return

            # Calculate desired bot activity level
            # High real engagement -> lower bot activity
            # Low real engagement -> higher bot activity

            if real_user_engagement > 0.8:
                # Very active community - minimal bot presence
                target_activity = 0.2
                target_bot_ratio = 0.3
            elif real_user_engagement > 0.5:
                # Moderately active - balanced
                target_activity = 0.5
                target_bot_ratio = 0.5
            elif real_user_engagement > 0.2:
                # Low activity - bots fill gaps
                target_activity = 0.7
                target_bot_ratio = 0.7
            else:
                # Very low activity - bots maintain presence
                target_activity = 0.9
                target_bot_ratio = 0.9

            # Update community activity level
            community.activity_level = target_activity
            await session.commit()

            # Optionally scale bot population
            current_bots = community.current_bot_count
            target_bots = int(community.max_bots * target_bot_ratio)

            if abs(target_bots - current_bots) > 5:
                await self.community_manager.scale_bot_population(
                    session,
                    community_id,
                    target_bots
                )

    async def get_platform_stats(self) -> Dict[str, Any]:
        """Get overall platform statistics."""
        async with async_session_factory() as session:
            # Count communities
            comm_count = await session.execute(
                select(func.count()).select_from(CommunityDB)
            )
            total_communities = comm_count.scalar() or 0

            # Count active bots
            bot_count = await session.execute(
                select(func.count())
                .select_from(BotProfileDB)
                .where(BotProfileDB.is_active == True)
            )
            total_bots = bot_count.scalar() or 0

            # Count retired bots
            retired_count = await session.execute(
                select(func.count())
                .select_from(BotProfileDB)
                .where(BotProfileDB.is_retired == True)
            )
            retired_bots = retired_count.scalar() or 0

            return {
                "total_communities": total_communities,
                "active_bots": total_bots,
                "retired_bots": retired_bots,
                "scheduler_stats": self.scheduler.get_queue_stats()
            }


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================

def create_community_manager(
    seed: Optional[int] = None
) -> CommunityManager:
    """Create a community manager."""
    personality_gen = PersonalityGenerator(seed=seed)
    return CommunityManager(personality_generator=personality_gen)


def create_community_orchestrator(
    scheduler: ActivityScheduler,
    seed: Optional[int] = None
) -> CommunityOrchestrator:
    """Create a community orchestrator."""
    manager = create_community_manager(seed)
    return CommunityOrchestrator(
        community_manager=manager,
        scheduler=scheduler,
        seed=seed
    )
