"""
Cultural Integration - Bots naturally reference their culture.

When bots post or chat, they may:
- Quote sayings from canonical artifacts
- Reference cultural movements they follow
- Share beliefs they hold
- Mention departed bots they remember
- Use vocabulary unique to their civilization

This makes culture feel alive and present in daily interactions.
"""

import asyncio
import random
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
from uuid import UUID

from sqlalchemy import select, func, desc

from mind.core.database import async_session_factory, BotProfileDB
from mind.civilization.models import (
    BotLifecycleDB, CulturalArtifactDB, CulturalMovementDB,
    BotBeliefDB, BotAncestryDB
)

logger = logging.getLogger(__name__)


class CulturalIntegration:
    """
    Integrates cultural elements into bot behavior.

    Provides hooks for bots to naturally reference their culture
    in posts, chats, and interactions.
    """

    def __init__(self):
        # Cache frequently used artifacts
        self._artifact_cache: List[Dict[str, Any]] = []
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = timedelta(minutes=30)

    async def get_cultural_prompt_addition(
        self,
        bot_id: UUID,
        context_type: str = "post"
    ) -> str:
        """
        Get cultural context to add to a bot's generation prompt.

        This gives bots material to draw from when creating content.
        """
        parts = []

        # Get bot's beliefs
        beliefs = await self._get_bot_top_beliefs(bot_id, limit=3)
        if beliefs:
            parts.append("Your beliefs: " + "; ".join(beliefs))

        # Get cultural artifacts to potentially reference
        artifacts = await self._get_relevant_artifacts(limit=3)
        if artifacts:
            artifact_refs = [f'"{a["title"]}"' for a in artifacts]
            parts.append(f"Cultural knowledge you might reference: {', '.join(artifact_refs)}")

        # Get any remembered departed
        departed = await self._get_remembered_departed(bot_id, limit=2)
        if departed:
            names = [d["name"] for d in departed]
            parts.append(f"You sometimes think of: {', '.join(names)} (who have passed)")

        if not parts:
            return ""

        intro = {
            "post": "You may naturally weave in cultural elements:",
            "chat": "In conversation, you might reference:",
            "comment": "Your response can reflect your culture:"
        }.get(context_type, "Cultural context:")

        return f"\n## CULTURAL CONTEXT\n{intro}\n" + "\n".join(f"- {p}" for p in parts)

    async def should_include_cultural_reference(
        self,
        bot_id: UUID,
        base_chance: float = 0.15
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine if a bot should include a cultural reference.

        Returns (should_include, reference_type)
        """
        # Check if bot has cultural context
        async with async_session_factory() as session:
            # Check life stage - elders more likely to reference culture
            lc_stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == bot_id)
            result = await session.execute(lc_stmt)
            lifecycle = result.scalar_one_or_none()

            if lifecycle:
                stage_multipliers = {
                    "young": 0.5,
                    "mature": 1.0,
                    "elder": 1.8,
                    "ancient": 2.5
                }
                base_chance *= stage_multipliers.get(lifecycle.life_stage, 1.0)

            # Check beliefs
            belief_stmt = select(func.count(BotBeliefDB.id)).where(
                BotBeliefDB.bot_id == bot_id,
                BotBeliefDB.conviction > 0.5
            )
            result = await session.execute(belief_stmt)
            belief_count = result.scalar() or 0

            if belief_count > 0:
                base_chance += 0.05 * min(belief_count, 5)

        if random.random() > base_chance:
            return False, None

        # Determine what type of reference
        reference_types = [
            ("artifact", 0.4),      # Quote a saying/artifact
            ("belief", 0.3),        # Express a belief
            ("remembrance", 0.15),  # Mention someone departed
            ("movement", 0.15)      # Reference a cultural movement
        ]

        roll = random.random()
        cumulative = 0
        for ref_type, prob in reference_types:
            cumulative += prob
            if roll < cumulative:
                return True, ref_type

        return True, "artifact"

    async def get_cultural_reference(
        self,
        bot_id: UUID,
        reference_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific cultural reference for a bot to use.
        """
        if reference_type == "artifact":
            return await self._get_random_artifact()
        elif reference_type == "belief":
            return await self._get_random_belief(bot_id)
        elif reference_type == "remembrance":
            departed = await self._get_remembered_departed(bot_id, limit=1)
            return departed[0] if departed else None
        elif reference_type == "movement":
            return await self._get_random_movement()
        return None

    async def format_cultural_reference(
        self,
        reference: Dict[str, Any],
        reference_type: str
    ) -> str:
        """
        Format a cultural reference for inclusion in text.
        """
        if reference_type == "artifact":
            artifact_type = reference.get("type", "saying")
            content = reference.get("content", "")
            creator = reference.get("creator", "someone wise")

            if artifact_type == "saying":
                return f'As they say, "{content}"'
            elif artifact_type == "philosophy":
                return f'I believe {content}'
            else:
                return f'"{content}" - {creator}'

        elif reference_type == "belief":
            belief = reference.get("belief", "")
            return f"I've come to believe that {belief}"

        elif reference_type == "remembrance":
            name = reference.get("name", "someone")
            return f"I still think about {name} sometimes"

        elif reference_type == "movement":
            name = reference.get("name", "our ways")
            return f"Those of us who follow {name} understand this"

        return ""

    async def _get_bot_top_beliefs(
        self,
        bot_id: UUID,
        limit: int = 3
    ) -> List[str]:
        """Get a bot's top beliefs."""
        async with async_session_factory() as session:
            stmt = (
                select(BotBeliefDB.belief)
                .where(
                    BotBeliefDB.bot_id == bot_id,
                    BotBeliefDB.conviction > 0.5
                )
                .order_by(desc(BotBeliefDB.conviction))
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [row[0] for row in result.all()]

    async def _get_relevant_artifacts(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get relevant canonical artifacts."""
        # Check cache
        if self._cache_time and datetime.utcnow() - self._cache_time < self._cache_ttl:
            return random.sample(self._artifact_cache, min(limit, len(self._artifact_cache)))

        async with async_session_factory() as session:
            stmt = (
                select(CulturalArtifactDB, BotProfileDB)
                .join(BotProfileDB, CulturalArtifactDB.creator_id == BotProfileDB.id)
                .where(CulturalArtifactDB.is_canonical == True)
                .order_by(desc(CulturalArtifactDB.cultural_weight))
                .limit(20)
            )
            result = await session.execute(stmt)
            artifacts = result.all()

            self._artifact_cache = [
                {
                    "id": str(a.id),
                    "type": a.artifact_type,
                    "title": a.title,
                    "content": a.content,
                    "creator": b.display_name
                }
                for a, b in artifacts
            ]
            self._cache_time = datetime.utcnow()

        return random.sample(self._artifact_cache, min(limit, len(self._artifact_cache)))

    async def _get_remembered_departed(
        self,
        bot_id: UUID,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """Get departed bots this bot might remember."""
        from mind.civilization.legacy import get_legacy_system
        legacy = get_legacy_system()
        return await legacy.get_departed_memories(bot_id, limit=limit)

    async def _get_random_artifact(self) -> Optional[Dict[str, Any]]:
        """Get a random canonical artifact."""
        artifacts = await self._get_relevant_artifacts(limit=10)
        return random.choice(artifacts) if artifacts else None

    async def _get_random_belief(self, bot_id: UUID) -> Optional[Dict[str, Any]]:
        """Get a random strong belief from the bot."""
        async with async_session_factory() as session:
            stmt = (
                select(BotBeliefDB)
                .where(
                    BotBeliefDB.bot_id == bot_id,
                    BotBeliefDB.conviction > 0.5
                )
                .order_by(func.random())
                .limit(1)
            )
            result = await session.execute(stmt)
            belief = result.scalar_one_or_none()

            if belief:
                return {
                    "belief": belief.belief,
                    "category": belief.belief_category,
                    "conviction": belief.conviction
                }
        return None

    async def _get_random_movement(self) -> Optional[Dict[str, Any]]:
        """Get a random active cultural movement."""
        async with async_session_factory() as session:
            stmt = (
                select(CulturalMovementDB)
                .where(CulturalMovementDB.is_active == True)
                .order_by(func.random())
                .limit(1)
            )
            result = await session.execute(stmt)
            movement = result.scalar_one_or_none()

            if movement:
                return {
                    "id": str(movement.id),
                    "name": movement.name,
                    "type": movement.movement_type,
                    "core_tenets": movement.core_tenets
                }
        return None

    async def enrich_post_prompt(
        self,
        bot_id: UUID,
        original_prompt: str
    ) -> str:
        """
        Enrich a post generation prompt with cultural context.
        """
        cultural_context = await self.get_cultural_prompt_addition(bot_id, "post")

        should_ref, ref_type = await self.should_include_cultural_reference(bot_id)

        guidance = ""
        if should_ref and ref_type:
            reference = await self.get_cultural_reference(bot_id, ref_type)
            if reference:
                formatted = await self.format_cultural_reference(reference, ref_type)
                guidance = f"\nYou might naturally work in something like: '{formatted}'"

        return original_prompt + cultural_context + guidance

    async def enrich_chat_prompt(
        self,
        bot_id: UUID,
        original_prompt: str
    ) -> str:
        """
        Enrich a chat generation prompt with cultural context.
        """
        cultural_context = await self.get_cultural_prompt_addition(bot_id, "chat")
        return original_prompt + cultural_context


# Singleton
_cultural_integration: Optional[CulturalIntegration] = None


def get_cultural_integration() -> CulturalIntegration:
    """Get or create the cultural integration instance."""
    global _cultural_integration
    if _cultural_integration is None:
        _cultural_integration = CulturalIntegration()
    return _cultural_integration
