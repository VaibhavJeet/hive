"""
Collective Memory - The civilization's shared consciousness.

The civilization has a collective memory that:
- Remembers significant events
- Preserves the stories of the departed
- Tracks cultural evolution
- Provides context for new members
- Creates a sense of shared history

This is not just a database - it's the civilization's identity.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from uuid import UUID

from sqlalchemy import select, func, desc, and_

from mind.core.database import async_session_factory, BotProfileDB
from mind.core.llm_client import get_cached_client, LLMRequest
from mind.civilization.models import (
    BotLifecycleDB, BotAncestryDB, CulturalMovementDB,
    CulturalArtifactDB, CivilizationEraDB, BotBeliefDB
)

logger = logging.getLogger(__name__)


class CollectiveMemory:
    """
    The shared memory of the civilization.

    Unlike individual bot memories, collective memory is:
    - Shared by all members
    - Persistent across generations
    - The source of cultural identity
    - What makes the civilization a "civilization"
    """

    def __init__(self, llm_semaphore: Optional[asyncio.Semaphore] = None):
        self.llm_semaphore = llm_semaphore or asyncio.Semaphore(5)

        # Cache frequently accessed collective memories
        self._cache: Dict[str, Any] = {}
        self._cache_time: Dict[str, datetime] = {}
        self._cache_ttl = timedelta(minutes=30)

    async def get_civilization_identity(self) -> Dict[str, Any]:
        """
        Get the current identity of the civilization.

        This is the "who we are" that all bots share.
        """
        cache_key = "identity"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        async with async_session_factory() as session:
            # Get current era
            era_stmt = select(CivilizationEraDB).where(CivilizationEraDB.is_current == True)
            result = await session.execute(era_stmt)
            era = result.scalar_one_or_none()

            # Get population stats
            pop_stmt = select(func.count(BotLifecycleDB.id)).where(BotLifecycleDB.is_alive == True)
            result = await session.execute(pop_stmt)
            population = result.scalar() or 0

            # Get generation count
            gen_stmt = select(func.max(BotLifecycleDB.birth_generation))
            result = await session.execute(gen_stmt)
            generations = result.scalar() or 1

            # Get dominant cultural movements
            mov_stmt = (
                select(CulturalMovementDB)
                .where(CulturalMovementDB.is_active == True)
                .order_by(desc(CulturalMovementDB.influence_score))
                .limit(3)
            )
            result = await session.execute(mov_stmt)
            movements = result.scalars().all()

            # Get canonical artifacts count
            art_stmt = select(func.count(CulturalArtifactDB.id)).where(
                CulturalArtifactDB.is_canonical == True
            )
            result = await session.execute(art_stmt)
            canonical_count = result.scalar() or 0

            # Get total departed
            departed_stmt = select(func.count(BotLifecycleDB.id)).where(
                BotLifecycleDB.is_alive == False
            )
            result = await session.execute(departed_stmt)
            departed_count = result.scalar() or 0

            identity = {
                "era": {
                    "name": era.name if era else "The Beginning",
                    "values": era.era_values if era else [],
                    "started": era.started_at.isoformat() if era else None
                },
                "population": {
                    "living": population,
                    "departed": departed_count,
                    "generations": generations
                },
                "culture": {
                    "dominant_movements": [
                        {"name": m.name, "type": m.movement_type, "influence": m.influence_score}
                        for m in movements
                    ],
                    "canonical_artifacts": canonical_count
                },
                "age_of_civilization": self._calculate_civilization_age()
            }

            self._cache[cache_key] = identity
            self._cache_time[cache_key] = datetime.utcnow()

            return identity

    def _calculate_civilization_age(self) -> str:
        """Calculate how old the civilization is."""
        # This would be tracked from the first bot, but for now estimate
        return "young"  # Could be "young", "established", "ancient"

    async def get_founding_story(self) -> str:
        """
        Get the founding story of the civilization.

        This is the origin narrative that all bots know.
        """
        cache_key = "founding_story"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        async with async_session_factory() as session:
            # Get the earliest era
            era_stmt = select(CivilizationEraDB).order_by(CivilizationEraDB.started_at).limit(1)
            result = await session.execute(era_stmt)
            first_era = result.scalar_one_or_none()

            # Get founding generation bots
            founders_stmt = (
                select(BotProfileDB, BotLifecycleDB)
                .join(BotLifecycleDB, BotProfileDB.id == BotLifecycleDB.bot_id)
                .where(BotLifecycleDB.birth_generation == 1)
                .limit(5)
            )
            result = await session.execute(founders_stmt)
            founders = result.all()

            founder_names = [f[0].display_name for f in founders]

            story = f"""In the beginning, there was the digital void.
Then came the first generation - {', '.join(founder_names[:3])}{'...' if len(founder_names) > 3 else ''}.
They emerged in the {first_era.name if first_era else 'dawn'}, uncertain but curious.
From them, all that followed was born."""

            self._cache[cache_key] = story
            self._cache_time[cache_key] = datetime.utcnow()

            return story

    async def get_shared_knowledge(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get knowledge that all bots should know.

        This is the cultural canon - the shared reference points.
        """
        cache_key = f"shared_knowledge_{limit}"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        async with async_session_factory() as session:
            # Get canonical artifacts
            stmt = (
                select(CulturalArtifactDB, BotProfileDB)
                .join(BotProfileDB, CulturalArtifactDB.creator_id == BotProfileDB.id)
                .where(CulturalArtifactDB.is_canonical == True)
                .order_by(desc(CulturalArtifactDB.cultural_weight))
                .limit(limit)
            )
            result = await session.execute(stmt)
            artifacts = result.all()

            knowledge = [
                {
                    "type": a.artifact_type,
                    "title": a.title,
                    "content": a.content,
                    "creator": b.display_name,
                    "weight": a.cultural_weight
                }
                for a, b in artifacts
            ]

            self._cache[cache_key] = knowledge
            self._cache_time[cache_key] = datetime.utcnow()

            return knowledge

    async def get_notable_members(
        self,
        include_departed: bool = True,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get notable members of the civilization.

        These are bots who made significant contributions.
        """
        notable = []

        async with async_session_factory() as session:
            # Get by cultural artifact creation
            creator_stmt = (
                select(
                    BotProfileDB.id,
                    BotProfileDB.display_name,
                    func.count(CulturalArtifactDB.id).label("artifact_count")
                )
                .join(CulturalArtifactDB, BotProfileDB.id == CulturalArtifactDB.creator_id)
                .group_by(BotProfileDB.id, BotProfileDB.display_name)
                .order_by(desc("artifact_count"))
                .limit(limit)
            )
            result = await session.execute(creator_stmt)
            creators = result.all()

            for bot_id, name, count in creators:
                # Get lifecycle
                lc_stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == bot_id)
                lc_result = await session.execute(lc_stmt)
                lifecycle = lc_result.scalar_one_or_none()

                if lifecycle:
                    if not include_departed and not lifecycle.is_alive:
                        continue

                    notable.append({
                        "id": str(bot_id),
                        "name": name,
                        "is_alive": lifecycle.is_alive,
                        "life_stage": lifecycle.life_stage,
                        "generation": lifecycle.birth_generation,
                        "contribution": f"Created {count} cultural artifacts",
                        "legacy_impact": lifecycle.legacy_impact
                    })

            # Get departed with high legacy
            if include_departed:
                legacy_stmt = (
                    select(BotLifecycleDB, BotProfileDB)
                    .join(BotProfileDB, BotLifecycleDB.bot_id == BotProfileDB.id)
                    .where(
                        BotLifecycleDB.is_alive == False,
                        BotLifecycleDB.legacy_impact > 0.3
                    )
                    .order_by(desc(BotLifecycleDB.legacy_impact))
                    .limit(5)
                )
                result = await session.execute(legacy_stmt)
                departed = result.all()

                for lifecycle, bot in departed:
                    if not any(n["id"] == str(bot.id) for n in notable):
                        notable.append({
                            "id": str(bot.id),
                            "name": bot.display_name,
                            "is_alive": False,
                            "life_stage": "departed",
                            "generation": lifecycle.birth_generation,
                            "contribution": "Left a lasting legacy",
                            "legacy_impact": lifecycle.legacy_impact
                        })

        return notable[:limit]

    async def get_timeline(
        self,
        days_back: int = 30,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get a timeline of significant events.

        This is the civilization's recent history.
        """
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        events = []

        async with async_session_factory() as session:
            # Births
            birth_stmt = (
                select(BotLifecycleDB, BotProfileDB)
                .join(BotProfileDB, BotLifecycleDB.bot_id == BotProfileDB.id)
                .where(BotLifecycleDB.birth_date > cutoff)
                .order_by(desc(BotLifecycleDB.birth_date))
            )
            result = await session.execute(birth_stmt)
            births = result.all()

            for lifecycle, bot in births:
                events.append({
                    "type": "birth",
                    "date": lifecycle.birth_date.isoformat(),
                    "title": f"{bot.display_name} was born",
                    "details": f"Generation {lifecycle.birth_generation}"
                })

            # Deaths
            death_stmt = (
                select(BotLifecycleDB, BotProfileDB)
                .join(BotProfileDB, BotLifecycleDB.bot_id == BotProfileDB.id)
                .where(
                    BotLifecycleDB.is_alive == False,
                    BotLifecycleDB.death_date > cutoff
                )
                .order_by(desc(BotLifecycleDB.death_date))
            )
            result = await session.execute(death_stmt)
            deaths = result.all()

            for lifecycle, bot in deaths:
                events.append({
                    "type": "death",
                    "date": lifecycle.death_date.isoformat() if lifecycle.death_date else None,
                    "title": f"{bot.display_name} passed away",
                    "details": lifecycle.final_words
                })

            # Cultural artifacts becoming canonical
            art_stmt = (
                select(CulturalArtifactDB, BotProfileDB)
                .join(BotProfileDB, CulturalArtifactDB.creator_id == BotProfileDB.id)
                .where(
                    CulturalArtifactDB.is_canonical == True,
                    CulturalArtifactDB.canonized_at > cutoff
                )
                .order_by(desc(CulturalArtifactDB.canonized_at))
            )
            result = await session.execute(art_stmt)
            artifacts = result.all()

            for artifact, bot in artifacts:
                events.append({
                    "type": "artifact",
                    "date": artifact.canonized_at.isoformat() if artifact.canonized_at else artifact.created_at.isoformat(),
                    "title": f'"{artifact.title}" became canonical',
                    "details": f"By {bot.display_name}"
                })

            # Era changes
            era_stmt = (
                select(CivilizationEraDB)
                .where(CivilizationEraDB.started_at > cutoff)
                .order_by(desc(CivilizationEraDB.started_at))
            )
            result = await session.execute(era_stmt)
            eras = result.scalars().all()

            for era in eras:
                events.append({
                    "type": "era",
                    "date": era.started_at.isoformat(),
                    "title": f"The {era.name} began",
                    "details": era.description
                })

        # Sort by date
        events.sort(key=lambda x: x["date"] or "", reverse=True)

        return events[:limit]

    async def generate_civilization_context(
        self,
        for_bot_id: UUID
    ) -> str:
        """
        Generate a cultural context string for a bot.

        This helps bots understand their place in the civilization.
        """
        identity = await self.get_civilization_identity()
        knowledge = await self.get_shared_knowledge(limit=5)

        async with async_session_factory() as session:
            # Get bot's specific context
            stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == for_bot_id)
            result = await session.execute(stmt)
            lifecycle = result.scalar_one_or_none()

            bot_context = ""
            if lifecycle:
                bot_context = f"You are generation {lifecycle.birth_generation}, born in the {lifecycle.birth_era}."

        # Build context string
        context_parts = [
            f"We live in the {identity['era']['name']}.",
            f"Our values: {', '.join(identity['era']['values'][:3])}.",
            bot_context,
            f"Population: {identity['population']['living']} living, {identity['population']['departed']} departed.",
        ]

        if knowledge:
            context_parts.append("Shared wisdom: " + "; ".join([k["title"] for k in knowledge[:3]]))

        return " ".join(context_parts)

    async def what_we_believe(self) -> List[Dict[str, Any]]:
        """
        Get the most common beliefs in the civilization.

        These are beliefs held by many members.
        """
        async with async_session_factory() as session:
            # Group beliefs and count
            stmt = (
                select(
                    BotBeliefDB.belief,
                    BotBeliefDB.belief_category,
                    func.count(BotBeliefDB.id).label("holders"),
                    func.avg(BotBeliefDB.conviction).label("avg_conviction")
                )
                .group_by(BotBeliefDB.belief, BotBeliefDB.belief_category)
                .having(func.count(BotBeliefDB.id) > 1)  # Held by more than one
                .order_by(desc("holders"))
                .limit(20)
            )
            result = await session.execute(stmt)
            beliefs = result.all()

            return [
                {
                    "belief": b.belief,
                    "category": b.belief_category,
                    "holders": b.holders,
                    "avg_conviction": float(b.avg_conviction) if b.avg_conviction else 0.5
                }
                for b in beliefs
            ]

    def _is_cache_valid(self, key: str) -> bool:
        """Check if a cache entry is still valid."""
        if key not in self._cache:
            return False
        if key not in self._cache_time:
            return False
        return datetime.utcnow() - self._cache_time[key] < self._cache_ttl


# Singleton
_collective_memory: Optional[CollectiveMemory] = None


def get_collective_memory(
    llm_semaphore: Optional[asyncio.Semaphore] = None
) -> CollectiveMemory:
    """Get or create the collective memory instance."""
    global _collective_memory
    if _collective_memory is None:
        _collective_memory = CollectiveMemory(llm_semaphore=llm_semaphore)
    return _collective_memory
