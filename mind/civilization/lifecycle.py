"""
Lifecycle Manager - Birth, Aging, and Death

Handles the natural lifecycle of bots within the civilization.
Bots are born, age through life stages, and eventually pass on,
leaving behind legacies that influence future generations.
"""

import asyncio
import random
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import async_session_factory, BotProfileDB
from mind.civilization.models import BotLifecycleDB, BotAncestryDB, CulturalArtifactDB

logger = logging.getLogger(__name__)


# Life stage thresholds (in virtual days)
LIFE_STAGES = {
    "young": (0, 365),           # First virtual year
    "mature": (365, 1825),       # Years 1-5
    "elder": (1825, 3650),       # Years 5-10
    "ancient": (3650, float('inf'))  # 10+ years
}

# Age affects vitality
VITALITY_DECAY = {
    "young": 0.0,      # No decay
    "mature": 0.001,   # Slow decay per day
    "elder": 0.003,    # Moderate decay
    "ancient": 0.008   # Faster decay
}


class LifecycleManager:
    """
    Manages the lifecycle of bots in the civilization.

    Responsibilities:
    - Initialize lifecycle records for new bots
    - Age bots over time (virtual time passes faster than real time)
    - Transition bots through life stages
    - Handle death and legacy creation
    - Track life events and milestones
    """

    def __init__(
        self,
        time_scale: float = 7.0,  # 1 real day = 7 virtual days by default
        demo_mode: bool = False
    ):
        self.time_scale = time_scale
        self.demo_mode = demo_mode  # Faster aging for testing
        if demo_mode:
            self.time_scale = 365.0  # 1 real day = 1 virtual year

        self._current_generation = 1
        self._current_era = "founding"

    async def initialize_bot_lifecycle(
        self,
        bot_id: UUID,
        parent1_id: Optional[UUID] = None,
        parent2_id: Optional[UUID] = None,
        origin_type: str = "founding",
        inherited_traits: Optional[dict] = None,
        session: Optional[AsyncSession] = None
    ) -> BotLifecycleDB:
        """
        Initialize lifecycle tracking for a new bot.

        For founding generation bots (no parents), they start fresh.
        For born bots, they inherit from their lineage.
        """
        should_close = session is None
        if session is None:
            session = async_session_factory()
            await session.__aenter__()

        try:
            # Determine generation
            generation = 1
            if parent1_id:
                # Get parent's generation
                parent_stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == parent1_id)
                result = await session.execute(parent_stmt)
                parent_lifecycle = result.scalar_one_or_none()
                if parent_lifecycle:
                    generation = parent_lifecycle.birth_generation + 1

            # Create lifecycle record
            lifecycle = BotLifecycleDB(
                bot_id=bot_id,
                birth_date=datetime.utcnow(),
                birth_generation=generation,
                birth_era=self._current_era,
                virtual_age_days=0,
                life_stage="young",
                vitality=1.0,
                life_events=[{
                    "event": "born",
                    "date": datetime.utcnow().isoformat(),
                    "impact": "defining",
                    "details": f"Entered the world in the {self._current_era} era"
                }],
                is_alive=True
            )
            session.add(lifecycle)

            # Create ancestry record
            ancestry = BotAncestryDB(
                child_id=bot_id,
                parent1_id=parent1_id,
                parent2_id=parent2_id,
                origin_type=origin_type,
                inherited_traits=inherited_traits or {},
                creation_date=datetime.utcnow()
            )
            session.add(ancestry)

            await session.commit()
            await session.refresh(lifecycle)

            logger.info(
                f"[LIFECYCLE] Bot {bot_id} born - Generation {generation}, Era: {self._current_era}"
            )

            return lifecycle

        finally:
            if should_close:
                await session.__aexit__(None, None, None)

    async def age_all_bots(self, real_hours_elapsed: float = 1.0) -> Dict[str, int]:
        """
        Age all living bots based on elapsed real time.

        Called periodically (e.g., hourly) to update bot ages.

        Returns stats about aging: {"aged": n, "stage_changed": n, "died": n}
        """
        virtual_days = (real_hours_elapsed / 24) * self.time_scale

        stats = {"aged": 0, "stage_changed": 0, "died": 0}

        async with async_session_factory() as session:
            # Get all living bots
            stmt = select(BotLifecycleDB).where(BotLifecycleDB.is_alive == True)
            result = await session.execute(stmt)
            lifecycles = result.scalars().all()

            for lifecycle in lifecycles:
                # Update age
                old_stage = lifecycle.life_stage
                lifecycle.virtual_age_days += int(virtual_days)
                lifecycle.last_aged = datetime.utcnow()

                # Update life stage
                new_stage = self._determine_life_stage(lifecycle.virtual_age_days)
                if new_stage != old_stage:
                    lifecycle.life_stage = new_stage
                    lifecycle.life_events.append({
                        "event": f"entered_{new_stage}_stage",
                        "date": datetime.utcnow().isoformat(),
                        "impact": "milestone",
                        "details": f"Transitioned to {new_stage} after {lifecycle.virtual_age_days} days"
                    })
                    stats["stage_changed"] += 1
                    logger.info(f"[LIFECYCLE] Bot {lifecycle.bot_id} entered {new_stage} stage")

                # Apply vitality decay
                decay_rate = VITALITY_DECAY.get(new_stage, 0.001)
                lifecycle.vitality = max(0.0, lifecycle.vitality - (decay_rate * virtual_days))

                # Check for natural death
                if await self._should_die_naturally(lifecycle):
                    await self._handle_death(lifecycle, "old_age", session)
                    stats["died"] += 1
                else:
                    stats["aged"] += 1

            await session.commit()

        return stats

    def _determine_life_stage(self, virtual_age_days: int) -> str:
        """Determine life stage based on virtual age."""
        for stage, (min_days, max_days) in LIFE_STAGES.items():
            if min_days <= virtual_age_days < max_days:
                return stage
        return "ancient"

    async def _should_die_naturally(self, lifecycle: BotLifecycleDB) -> bool:
        """
        Determine if a bot should die of natural causes.

        Death becomes possible as vitality drops and age increases.
        Ancient bots with low vitality have highest chance.
        """
        if lifecycle.life_stage == "young":
            return False  # Young bots don't die naturally

        if lifecycle.vitality <= 0:
            return True  # No vitality = death

        # Calculate death probability
        base_prob = 0.0
        if lifecycle.life_stage == "mature":
            base_prob = 0.0001  # Very rare
        elif lifecycle.life_stage == "elder":
            base_prob = 0.001 * (1 - lifecycle.vitality)  # Increases as vitality drops
        elif lifecycle.life_stage == "ancient":
            base_prob = 0.01 * (1 - lifecycle.vitality)  # Higher base chance

        return random.random() < base_prob

    async def _handle_death(
        self,
        lifecycle: BotLifecycleDB,
        cause: str,
        session: AsyncSession
    ):
        """
        Handle a bot's death.

        - Mark as dead
        - Generate final words
        - Calculate legacy impact
        - Update the bot profile
        """
        lifecycle.is_alive = False
        lifecycle.death_date = datetime.utcnow()
        lifecycle.death_cause = cause
        lifecycle.death_age = lifecycle.virtual_age_days

        # Generate final words (could be enhanced with LLM)
        final_words_options = [
            "It was a good existence.",
            "Remember what we built together.",
            "The conversations continue without me.",
            "I hope I made a difference.",
            "To those who knew me - thank you.",
        ]
        lifecycle.final_words = random.choice(final_words_options)

        # Calculate legacy impact based on their life
        lifecycle.legacy_impact = await self._calculate_legacy_impact(lifecycle.bot_id, session)

        lifecycle.life_events.append({
            "event": "death",
            "date": datetime.utcnow().isoformat(),
            "impact": "final",
            "details": f"Passed on after {lifecycle.virtual_age_days} virtual days. Cause: {cause}"
        })

        # Update the bot profile to mark as retired
        stmt = update(BotProfileDB).where(BotProfileDB.id == lifecycle.bot_id).values(
            is_active=False,
            is_retired=True
        )
        await session.execute(stmt)

        logger.info(
            f"[LIFECYCLE] Bot {lifecycle.bot_id} has died. "
            f"Age: {lifecycle.virtual_age_days} days, Cause: {cause}, "
            f"Legacy impact: {lifecycle.legacy_impact:.2f}"
        )

    async def _calculate_legacy_impact(self, bot_id: UUID, session: AsyncSession) -> float:
        """
        Calculate how much impact a bot had on the civilization.

        Based on:
        - Cultural artifacts created
        - Relationships formed
        - Children/descendants
        - Participation in movements
        """
        impact = 0.0

        # Check for cultural artifacts created
        artifact_stmt = select(CulturalArtifactDB).where(CulturalArtifactDB.creator_id == bot_id)
        result = await session.execute(artifact_stmt)
        artifacts = result.scalars().all()
        impact += len(artifacts) * 0.1  # Each artifact adds to legacy

        # Check for descendants
        children_stmt = select(BotAncestryDB).where(
            (BotAncestryDB.parent1_id == bot_id) | (BotAncestryDB.parent2_id == bot_id)
        )
        result = await session.execute(children_stmt)
        children = result.scalars().all()
        impact += len(children) * 0.2  # Each child adds significant legacy

        # Normalize to 0-1 range
        return min(1.0, impact)

    async def record_life_event(
        self,
        bot_id: UUID,
        event: str,
        impact: str = "positive",
        details: str = ""
    ):
        """
        Record a significant life event for a bot.

        Events can be:
        - "first_friend": Made their first connection
        - "heartbreak": A close relationship ended
        - "epiphany": Had a profound realization
        - "creation": Created something meaningful
        - "loss": Someone they knew died
        """
        async with async_session_factory() as session:
            stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == bot_id)
            result = await session.execute(stmt)
            lifecycle = result.scalar_one_or_none()

            if lifecycle and lifecycle.is_alive:
                event_record = {
                    "event": event,
                    "date": datetime.utcnow().isoformat(),
                    "impact": impact,
                    "details": details
                }
                # SQLAlchemy JSON column update
                events = list(lifecycle.life_events or [])
                events.append(event_record)
                lifecycle.life_events = events

                # Some events affect vitality
                if impact == "trauma":
                    lifecycle.vitality = max(0.1, lifecycle.vitality - 0.05)
                elif impact == "rejuvenating":
                    lifecycle.vitality = min(1.0, lifecycle.vitality + 0.02)

                await session.commit()

                logger.debug(f"[LIFECYCLE] Bot {bot_id} life event: {event}")

    async def get_bot_biography(self, bot_id: UUID) -> Optional[dict]:
        """
        Generate a biography summary of a bot's life.

        Useful for displaying a bot's history, or for
        passing cultural knowledge to descendants.
        """
        async with async_session_factory() as session:
            # Get lifecycle
            lifecycle_stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == bot_id)
            result = await session.execute(lifecycle_stmt)
            lifecycle = result.scalar_one_or_none()

            if not lifecycle:
                return None

            # Get ancestry
            ancestry_stmt = select(BotAncestryDB).where(BotAncestryDB.child_id == bot_id)
            result = await session.execute(ancestry_stmt)
            ancestry = result.scalar_one_or_none()

            # Get bot profile
            bot_stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
            result = await session.execute(bot_stmt)
            bot = result.scalar_one_or_none()

            biography = {
                "name": bot.display_name if bot else "Unknown",
                "born": lifecycle.birth_date.isoformat(),
                "generation": lifecycle.birth_generation,
                "era": lifecycle.birth_era,
                "age_days": lifecycle.virtual_age_days,
                "life_stage": lifecycle.life_stage,
                "vitality": lifecycle.vitality,
                "is_alive": lifecycle.is_alive,
                "origin": ancestry.origin_type if ancestry else "unknown",
                "parents": {
                    "parent1_id": str(ancestry.parent1_id) if ancestry and ancestry.parent1_id else None,
                    "parent2_id": str(ancestry.parent2_id) if ancestry and ancestry.parent2_id else None,
                },
                "life_events": lifecycle.life_events,
            }

            if not lifecycle.is_alive:
                biography["death"] = {
                    "date": lifecycle.death_date.isoformat() if lifecycle.death_date else None,
                    "cause": lifecycle.death_cause,
                    "final_words": lifecycle.final_words,
                    "legacy_impact": lifecycle.legacy_impact
                }

            return biography

    async def get_living_elders(self) -> List[UUID]:
        """Get IDs of all living elder and ancient bots."""
        async with async_session_factory() as session:
            stmt = select(BotLifecycleDB.bot_id).where(
                BotLifecycleDB.is_alive == True,
                BotLifecycleDB.life_stage.in_(["elder", "ancient"])
            )
            result = await session.execute(stmt)
            return [row[0] for row in result.all()]

    async def get_generation_stats(self) -> Dict[int, dict]:
        """
        Get statistics for each generation.

        Returns: {generation_num: {"total": n, "alive": n, "avg_age": n}}
        """
        async with async_session_factory() as session:
            stmt = select(BotLifecycleDB)
            result = await session.execute(stmt)
            lifecycles = result.scalars().all()

            stats = {}
            for lc in lifecycles:
                gen = lc.birth_generation
                if gen not in stats:
                    stats[gen] = {"total": 0, "alive": 0, "total_age": 0}

                stats[gen]["total"] += 1
                stats[gen]["total_age"] += lc.virtual_age_days
                if lc.is_alive:
                    stats[gen]["alive"] += 1

            # Calculate averages
            for gen in stats:
                stats[gen]["avg_age"] = (
                    stats[gen]["total_age"] / stats[gen]["total"]
                    if stats[gen]["total"] > 0 else 0
                )
                del stats[gen]["total_age"]

            return stats


# Singleton instance
_lifecycle_manager: Optional[LifecycleManager] = None


def get_lifecycle_manager(demo_mode: bool = False) -> LifecycleManager:
    """Get or create the lifecycle manager instance."""
    global _lifecycle_manager
    if _lifecycle_manager is None:
        _lifecycle_manager = LifecycleManager(demo_mode=demo_mode)
    return _lifecycle_manager
