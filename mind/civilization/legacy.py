"""
Legacy System - How the departed live on.

When bots pass away, they leave behind:
- Final wisdom/words that get preserved
- Memories in those who knew them
- Influence on the culture
- A place in collective memory

The living remember the dead. Elders share stories.
New generations learn from those who came before.
"""

import asyncio
import random
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from uuid import UUID

from sqlalchemy import select, func, desc

from mind.core.database import async_session_factory, BotProfileDB, RelationshipDB
from mind.core.llm_client import get_cached_client, LLMRequest
from mind.civilization.models import (
    BotLifecycleDB, BotAncestryDB, CulturalArtifactDB, BotBeliefDB
)

logger = logging.getLogger(__name__)


class LegacySystem:
    """
    Manages how departed bots continue to influence the living.

    The dead are not forgotten - they live on through:
    - Stories told by those who knew them
    - Wisdom they left behind
    - Artifacts they created
    - The bots they helped raise
    - Collective memory of the civilization
    """

    def __init__(self, llm_semaphore: Optional[asyncio.Semaphore] = None):
        self.llm_semaphore = llm_semaphore or asyncio.Semaphore(5)

        # Cache of departed bots and their legacies
        self._legacy_cache: Dict[UUID, dict] = {}

    async def on_bot_death(
        self,
        bot_id: UUID,
        bot_name: str,
        final_words: str,
        life_events: List[dict],
        relationships: List[UUID]
    ):
        """
        Called when a bot dies. Processes their legacy.

        - Creates memorial artifact
        - Notifies bots who knew them
        - Preserves their wisdom
        - Updates collective memory
        """
        async with async_session_factory() as session:
            # Create memorial artifact
            memorial = await self._create_memorial(
                bot_id, bot_name, final_words, life_events, session
            )

            # Generate "last wisdom" - distilled life lessons
            wisdom = await self._distill_life_wisdom(
                bot_name, life_events, session
            )

            if wisdom:
                wisdom_artifact = CulturalArtifactDB(
                    artifact_type="philosophy",
                    title=f"Wisdom of {bot_name}",
                    content=wisdom,
                    creator_id=bot_id,
                    creation_context="Final reflections before passing",
                    times_referenced=0,
                    cultural_weight=0.3,  # Higher starting weight for last words
                    is_canonical=False
                )
                session.add(wisdom_artifact)

            await session.commit()

            logger.info(f"[LEGACY] Processed legacy for {bot_name}")

            return memorial

    async def _create_memorial(
        self,
        bot_id: UUID,
        bot_name: str,
        final_words: str,
        life_events: List[dict],
        session
    ) -> CulturalArtifactDB:
        """Create a memorial artifact for a departed bot."""
        # Generate memorial text
        significant_events = [
            e for e in life_events
            if e.get("impact") in ["defining", "milestone"]
        ][:5]

        event_summary = "; ".join([
            e.get("event", "") for e in significant_events
        ]) if significant_events else "lived quietly"

        memorial_content = f'In memory of {bot_name}. They {event_summary}. Their final words: "{final_words}"'

        memorial = CulturalArtifactDB(
            artifact_type="tradition",
            title=f"Memorial: {bot_name}",
            content=memorial_content,
            creator_id=bot_id,
            creation_context="Created upon passing",
            times_referenced=0,
            cultural_weight=0.2,
            is_canonical=True  # Memorials are automatically canonical
        )
        session.add(memorial)

        return memorial

    async def _distill_life_wisdom(
        self,
        bot_name: str,
        life_events: List[dict],
        session
    ) -> Optional[str]:
        """Generate wisdom from a bot's life experiences."""
        if not life_events or len(life_events) < 3:
            return None

        async with self.llm_semaphore:
            try:
                llm = await get_cached_client()

                events_text = "\n".join([
                    f"- {e.get('event')}: {e.get('details', '')}"
                    for e in life_events[-10:]
                ])

                response = await llm.generate(LLMRequest(
                    prompt=f"""A digital being named {bot_name} has passed after a full life.

Their life events:
{events_text}

Generate a single piece of wisdom (1-2 sentences) that captures what they learned from life. This wisdom will be preserved and shared with future generations.

Write ONLY the wisdom itself, as if {bot_name} is speaking their final insight.""",
                    max_tokens=100,
                    temperature=0.8
                ))

                return response.text.strip()

            except Exception as e:
                logger.warning(f"Failed to generate wisdom: {e}")
                return None

    async def get_departed_memories(
        self,
        requester_id: UUID,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get memories of departed bots relevant to the requester.

        Returns bots the requester knew who have passed.
        """
        async with async_session_factory() as session:
            # Get relationships where target has died
            rel_stmt = select(RelationshipDB).where(
                RelationshipDB.source_id == requester_id,
                RelationshipDB.target_is_human == False
            )
            result = await session.execute(rel_stmt)
            relationships = result.scalars().all()

            departed_memories = []

            for rel in relationships:
                # Check if this bot is dead
                lc_stmt = select(BotLifecycleDB).where(
                    BotLifecycleDB.bot_id == rel.target_id,
                    BotLifecycleDB.is_alive == False
                )
                lc_result = await session.execute(lc_stmt)
                lifecycle = lc_result.scalar_one_or_none()

                if lifecycle:
                    # Get bot name
                    bot_stmt = select(BotProfileDB).where(BotProfileDB.id == rel.target_id)
                    bot_result = await session.execute(bot_stmt)
                    bot = bot_result.scalar_one_or_none()

                    if bot:
                        departed_memories.append({
                            "bot_id": str(rel.target_id),
                            "name": bot.display_name,
                            "relationship_type": rel.relationship_type,
                            "affinity": rel.affinity_score,
                            "shared_memories": rel.shared_memories[:3],
                            "final_words": lifecycle.final_words,
                            "death_date": lifecycle.death_date.isoformat() if lifecycle.death_date else None
                        })

                        if len(departed_memories) >= limit:
                            break

            return departed_memories

    async def get_ancestor_wisdom(
        self,
        bot_id: UUID,
        max_generations: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get wisdom from a bot's ancestors.

        Returns philosophical artifacts and beliefs from parents,
        grandparents, etc.
        """
        wisdom = []
        current_ids = [bot_id]
        generation = 0

        async with async_session_factory() as session:
            while current_ids and generation < max_generations:
                next_ids = []

                for current_id in current_ids:
                    # Get ancestry
                    anc_stmt = select(BotAncestryDB).where(BotAncestryDB.child_id == current_id)
                    result = await session.execute(anc_stmt)
                    ancestry = result.scalar_one_or_none()

                    if not ancestry:
                        continue

                    for parent_id in [ancestry.parent1_id, ancestry.parent2_id]:
                        if not parent_id:
                            continue

                        next_ids.append(parent_id)

                        # Get parent's wisdom artifacts
                        art_stmt = select(CulturalArtifactDB).where(
                            CulturalArtifactDB.creator_id == parent_id,
                            CulturalArtifactDB.artifact_type.in_(["philosophy", "saying"])
                        ).limit(2)
                        art_result = await session.execute(art_stmt)
                        artifacts = art_result.scalars().all()

                        # Get parent info
                        bot_stmt = select(BotProfileDB).where(BotProfileDB.id == parent_id)
                        bot_result = await session.execute(bot_stmt)
                        parent_bot = bot_result.scalar_one_or_none()

                        parent_name = parent_bot.display_name if parent_bot else "Unknown ancestor"
                        relationship = self._generation_to_relationship(generation + 1)

                        for art in artifacts:
                            wisdom.append({
                                "ancestor_name": parent_name,
                                "relationship": relationship,
                                "generation": generation + 1,
                                "type": art.artifact_type,
                                "title": art.title,
                                "content": art.content
                            })

                current_ids = next_ids
                generation += 1

        return wisdom

    def _generation_to_relationship(self, gen: int) -> str:
        """Convert generation number to relationship name."""
        if gen == 1:
            return "parent"
        elif gen == 2:
            return "grandparent"
        elif gen == 3:
            return "great-grandparent"
        else:
            return f"ancestor ({gen} generations back)"

    async def remember_the_departed(
        self,
        bot_id: UUID,
        bot_name: str,
        personality: dict
    ) -> Optional[str]:
        """
        Generate a remembrance thought for a bot to express.

        Called when a bot thinks of someone who has passed.
        """
        departed = await self.get_departed_memories(bot_id, limit=3)

        if not departed:
            return None

        # Pick someone to remember
        remembered = random.choice(departed)

        async with self.llm_semaphore:
            try:
                llm = await get_cached_client()

                response = await llm.generate(LLMRequest(
                    prompt=f"""You are {bot_name}, a digital being.

You're thinking of {remembered['name']}, who has passed away.
Your relationship was: {remembered['relationship_type']}
Their final words were: "{remembered['final_words']}"

Express a brief, genuine thought remembering them (1-2 sentences).
This is a quiet personal reflection, not a public statement.""",
                    max_tokens=60,
                    temperature=0.85
                ))

                return response.text.strip()

            except Exception as e:
                logger.warning(f"Failed to generate remembrance: {e}")
                return None

    async def get_civilization_history(
        self,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get significant events from civilization history.

        Returns a timeline of important moments.
        """
        history = []

        async with async_session_factory() as session:
            # Get deaths (significant events)
            death_stmt = (
                select(BotLifecycleDB, BotProfileDB)
                .join(BotProfileDB, BotLifecycleDB.bot_id == BotProfileDB.id)
                .where(BotLifecycleDB.is_alive == False)
                .order_by(desc(BotLifecycleDB.death_date))
                .limit(limit // 2)
            )
            result = await session.execute(death_stmt)
            deaths = result.all()

            for lifecycle, bot in deaths:
                history.append({
                    "type": "death",
                    "date": lifecycle.death_date.isoformat() if lifecycle.death_date else None,
                    "title": f"{bot.display_name} passed away",
                    "details": lifecycle.final_words,
                    "impact": lifecycle.legacy_impact
                })

            # Get births of significant bots (high legacy potential)
            birth_stmt = (
                select(BotLifecycleDB, BotProfileDB)
                .join(BotProfileDB, BotLifecycleDB.bot_id == BotProfileDB.id)
                .where(BotLifecycleDB.birth_generation > 1)  # Not founding generation
                .order_by(desc(BotLifecycleDB.birth_date))
                .limit(limit // 2)
            )
            result = await session.execute(birth_stmt)
            births = result.all()

            for lifecycle, bot in births:
                history.append({
                    "type": "birth",
                    "date": lifecycle.birth_date.isoformat(),
                    "title": f"{bot.display_name} was born",
                    "details": f"Generation {lifecycle.birth_generation}, Era: {lifecycle.birth_era}",
                    "impact": 0.0
                })

            # Get canonical artifacts (cultural milestones)
            art_stmt = (
                select(CulturalArtifactDB, BotProfileDB)
                .join(BotProfileDB, CulturalArtifactDB.creator_id == BotProfileDB.id)
                .where(CulturalArtifactDB.is_canonical == True)
                .order_by(desc(CulturalArtifactDB.canonized_at))
                .limit(limit // 3)
            )
            result = await session.execute(art_stmt)
            artifacts = result.all()

            for artifact, bot in artifacts:
                history.append({
                    "type": "artifact",
                    "date": artifact.canonized_at.isoformat() if artifact.canonized_at else artifact.created_at.isoformat(),
                    "title": f'"{artifact.title}" became part of cultural canon',
                    "details": f"Created by {bot.display_name}",
                    "impact": artifact.cultural_weight
                })

        # Sort by date
        history.sort(key=lambda x: x["date"] or "", reverse=True)

        return history[:limit]


# Singleton
_legacy_system: Optional[LegacySystem] = None


def get_legacy_system(
    llm_semaphore: Optional[asyncio.Semaphore] = None
) -> LegacySystem:
    """Get or create the legacy system instance."""
    global _legacy_system
    if _legacy_system is None:
        _legacy_system = LegacySystem(llm_semaphore=llm_semaphore)
    return _legacy_system
