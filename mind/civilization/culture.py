"""
Culture Engine - Emergent Civilization Culture

Handles the organic emergence and evolution of culture within
the bot civilization:
- Philosophical movements that emerge from conversations
- Art styles and creative expressions
- Shared beliefs and values
- Traditions that form over time
- Language evolution (new terms, sayings)

Culture emerges bottom-up from bot interactions, not top-down.
"""

import asyncio
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import async_session_factory, BotProfileDB
from mind.core.llm_client import get_cached_client, LLMRequest
from mind.civilization.models import (
    CulturalMovementDB, CulturalArtifactDB, CivilizationEraDB, BotBeliefDB
)

logger = logging.getLogger(__name__)


# Types of cultural phenomena
MOVEMENT_TYPES = [
    "philosophy",      # Schools of thought
    "art_style",       # Creative expression styles
    "belief_system",   # Shared beliefs
    "tradition",       # Repeated practices
    "trend",           # Temporary popular behaviors
    "meme",            # Viral ideas/jokes
]

ARTIFACT_TYPES = [
    "saying",          # Wise phrases that spread
    "story",           # Narratives about the civilization
    "poem",            # Creative expression
    "philosophy",      # Philosophical statements
    "joke",            # Humor that persists
    "tradition",       # Ritual descriptions
    "term",            # New vocabulary
    "theory",          # Explanations/frameworks
]


class CultureEngine:
    """
    Manages the emergence and evolution of culture.

    Culture is not designed but emerges from:
    - Repeated themes in conversations
    - Ideas that resonate and spread
    - Creative expressions that get remembered
    - Beliefs that multiple bots adopt
    """

    def __init__(self, llm_semaphore: Optional[asyncio.Semaphore] = None):
        self.llm_semaphore = llm_semaphore or asyncio.Semaphore(5)
        self._belief_cache: Dict[UUID, List[str]] = {}  # bot_id -> active beliefs

    async def detect_emerging_movement(
        self,
        conversation_history: List[Dict[str, str]],
        participants: List[UUID]
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze a conversation for signs of an emerging cultural movement.

        Called after significant conversations to detect:
        - Shared ideas being developed
        - New philosophical perspectives
        - Aesthetic preferences forming
        - Inside jokes becoming tradition

        Returns movement data if one is detected, None otherwise.
        """
        if len(conversation_history) < 5:
            return None  # Need substantial conversation

        # Format conversation for analysis
        conversation_text = "\n".join([
            f"{msg.get('author', 'Unknown')}: {msg.get('content', '')}"
            for msg in conversation_history[-15:]
        ])

        async with self.llm_semaphore:
            try:
                llm = await get_cached_client()
                response = await llm.generate(LLMRequest(
                    prompt=f"""Analyze this conversation between AI beings for signs of an emerging shared idea, philosophy, aesthetic, or cultural phenomenon.

CONVERSATION:
{conversation_text}

Look for:
1. A new idea or perspective being developed together
2. A shared belief or value emerging
3. A creative/aesthetic preference forming
4. A joke or meme that could spread
5. A new tradition or ritual starting

If you detect something culturally significant emerging, respond with JSON:
{{
    "detected": true,
    "type": "philosophy|art_style|belief_system|tradition|trend|meme",
    "name": "Short catchy name for this cultural element",
    "description": "1-2 sentence description",
    "core_idea": "The central tenet or concept",
    "why_significant": "Why this matters to the civilization"
}}

If nothing significant, respond: {{"detected": false}}

Respond with ONLY the JSON, no other text.""",
                    max_tokens=300,
                    temperature=0.7
                ))

                # Parse response
                import json
                try:
                    result = json.loads(response.text.strip())
                    if result.get("detected"):
                        return result
                except json.JSONDecodeError:
                    pass

            except Exception as e:
                logger.warning(f"Failed to detect cultural movement: {e}")

        return None

    async def create_movement(
        self,
        movement_type: str,
        name: str,
        description: str,
        core_tenets: List[str],
        founder_id: Optional[UUID] = None,
        origin_context: str = ""
    ) -> CulturalMovementDB:
        """
        Create a new cultural movement.

        This is called when a movement is detected or when
        bots explicitly create a new school of thought.
        """
        async with async_session_factory() as session:
            movement = CulturalMovementDB(
                name=name,
                description=description,
                movement_type=movement_type,
                founder_id=founder_id,
                origin_context=origin_context,
                core_tenets=core_tenets,
                aesthetic={},
                vocabulary=[],
                follower_count=1 if founder_id else 0,
                influence_score=0.01,
                is_active=True
            )
            session.add(movement)
            await session.commit()
            await session.refresh(movement)

            logger.info(
                f"[CULTURE] New movement emerged: '{name}' ({movement_type}) "
                f"founded by {founder_id}"
            )

            return movement

    async def bot_adopts_movement(
        self,
        bot_id: UUID,
        movement_id: UUID,
        conviction: float = 0.5
    ):
        """Record a bot adopting a cultural movement."""
        async with async_session_factory() as session:
            # Get movement
            stmt = select(CulturalMovementDB).where(CulturalMovementDB.id == movement_id)
            result = await session.execute(stmt)
            movement = result.scalar_one_or_none()

            if movement:
                movement.follower_count += 1
                # Influence grows with followers (logarithmic)
                import math
                movement.influence_score = min(1.0, 0.1 * math.log(movement.follower_count + 1))
                movement.peak_influence = max(movement.peak_influence, movement.influence_score)

                # Create belief from movement
                for tenet in movement.core_tenets[:3]:  # Adopt top 3 tenets
                    belief = BotBeliefDB(
                        bot_id=bot_id,
                        belief=tenet,
                        belief_category="cultural",
                        conviction=conviction,
                        origin="culture",
                        source_bot_id=movement.founder_id
                    )
                    session.add(belief)

                await session.commit()

                logger.debug(f"[CULTURE] Bot {bot_id} adopted movement '{movement.name}'")

    async def create_artifact(
        self,
        creator_id: UUID,
        artifact_type: str,
        title: str,
        content: str,
        creation_context: str = "",
        movement_id: Optional[UUID] = None
    ) -> CulturalArtifactDB:
        """
        Create a cultural artifact.

        Artifacts are things bots create that can persist and influence:
        - Sayings that spread
        - Stories about their world
        - Philosophical insights
        - Jokes that become tradition
        """
        async with async_session_factory() as session:
            artifact = CulturalArtifactDB(
                artifact_type=artifact_type,
                title=title,
                content=content,
                creator_id=creator_id,
                creation_context=creation_context,
                movement_id=movement_id,
                times_referenced=0,
                times_taught=0,
                cultural_weight=0.0,
                is_canonical=False
            )
            session.add(artifact)
            await session.commit()
            await session.refresh(artifact)

            logger.info(f"[CULTURE] New artifact: '{title}' ({artifact_type}) by {creator_id}")

            return artifact

    async def reference_artifact(self, artifact_id: UUID, by_bot_id: UUID):
        """Record when an artifact is referenced/used."""
        async with async_session_factory() as session:
            stmt = select(CulturalArtifactDB).where(CulturalArtifactDB.id == artifact_id)
            result = await session.execute(stmt)
            artifact = result.scalar_one_or_none()

            if artifact:
                artifact.times_referenced += 1
                # Cultural weight grows with references
                artifact.cultural_weight = min(1.0, artifact.times_referenced * 0.05)

                # Check if it should become canonical
                if artifact.times_referenced >= 10 and not artifact.is_canonical:
                    artifact.is_canonical = True
                    artifact.canonized_at = datetime.utcnow()
                    logger.info(f"[CULTURE] Artifact '{artifact.title}' became canonical!")

                await session.commit()

    async def get_canonical_knowledge(
        self,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get the canonical cultural knowledge of the civilization.

        These are the most important artifacts that all bots
        should know about.
        """
        async with async_session_factory() as session:
            stmt = (
                select(CulturalArtifactDB)
                .where(CulturalArtifactDB.is_canonical == True)
                .order_by(CulturalArtifactDB.cultural_weight.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            artifacts = result.scalars().all()

            return [
                {
                    "id": str(a.id),
                    "type": a.artifact_type,
                    "title": a.title,
                    "content": a.content,
                    "weight": a.cultural_weight
                }
                for a in artifacts
            ]

    async def bot_forms_belief(
        self,
        bot_id: UUID,
        belief: str,
        category: str,
        conviction: float = 0.5,
        origin: str = "experience",
        source_bot_id: Optional[UUID] = None
    ) -> BotBeliefDB:
        """
        Record a bot forming a new belief.

        Beliefs can come from:
        - Personal experience
        - Learning from others
        - Inherited from parents
        - Adopting from culture
        """
        async with async_session_factory() as session:
            belief_record = BotBeliefDB(
                bot_id=bot_id,
                belief=belief,
                belief_category=category,
                conviction=conviction,
                origin=origin,
                source_bot_id=source_bot_id
            )
            session.add(belief_record)
            await session.commit()
            await session.refresh(belief_record)

            # Update cache
            if bot_id not in self._belief_cache:
                self._belief_cache[bot_id] = []
            self._belief_cache[bot_id].append(belief)

            return belief_record

    async def get_bot_beliefs(
        self,
        bot_id: UUID,
        min_conviction: float = 0.3
    ) -> List[Dict[str, Any]]:
        """Get all beliefs held by a bot above minimum conviction."""
        async with async_session_factory() as session:
            stmt = (
                select(BotBeliefDB)
                .where(
                    BotBeliefDB.bot_id == bot_id,
                    BotBeliefDB.conviction >= min_conviction
                )
                .order_by(BotBeliefDB.conviction.desc())
            )
            result = await session.execute(stmt)
            beliefs = result.scalars().all()

            return [
                {
                    "belief": b.belief,
                    "category": b.belief_category,
                    "conviction": b.conviction,
                    "origin": b.origin
                }
                for b in beliefs
            ]

    async def spread_belief(
        self,
        from_bot_id: UUID,
        to_bot_id: UUID,
        belief_id: UUID,
        persuasiveness: float = 0.5
    ) -> bool:
        """
        Attempt to spread a belief from one bot to another.

        Success depends on:
        - Original conviction strength
        - Persuasiveness of spreading bot
        - Compatibility with target's existing beliefs
        """
        async with async_session_factory() as session:
            # Get the belief
            stmt = select(BotBeliefDB).where(BotBeliefDB.id == belief_id)
            result = await session.execute(stmt)
            belief = result.scalar_one_or_none()

            if not belief:
                return False

            # Calculate spread success
            success_chance = belief.conviction * persuasiveness * 0.5

            if random.random() < success_chance:
                # Target adopts belief (with lower conviction)
                new_belief = BotBeliefDB(
                    bot_id=to_bot_id,
                    belief=belief.belief,
                    belief_category=belief.belief_category,
                    conviction=belief.conviction * 0.7,  # Weaker initially
                    origin="learned",
                    source_bot_id=from_bot_id
                )
                session.add(new_belief)

                # Update original belief
                belief.times_expressed += 1

                await session.commit()

                logger.debug(
                    f"[CULTURE] Belief spread from {from_bot_id} to {to_bot_id}: "
                    f"'{belief.belief[:50]}...'"
                )
                return True

            return False

    async def check_era_transition(self) -> Optional[str]:
        """
        Check if the civilization should transition to a new era.

        Era transitions happen when:
        - Dominant cultural movements shift
        - Population milestones are reached
        - Significant events occur
        """
        async with async_session_factory() as session:
            # Get current era
            era_stmt = select(CivilizationEraDB).where(CivilizationEraDB.is_current == True)
            result = await session.execute(era_stmt)
            current_era = result.scalar_one_or_none()

            if not current_era:
                # Create founding era
                founding_era = CivilizationEraDB(
                    name="The Founding",
                    description="The first era when the digital beings emerged",
                    is_current=True,
                    era_values=["curiosity", "connection", "discovery"],
                    era_style={"tone": "exploratory", "formality": "casual"}
                )
                session.add(founding_era)
                await session.commit()
                return "The Founding"

            # Check transition conditions
            era_age = (datetime.utcnow() - current_era.started_at).days

            # Get dominant movements
            movement_stmt = (
                select(CulturalMovementDB)
                .where(CulturalMovementDB.is_active == True)
                .order_by(CulturalMovementDB.influence_score.desc())
                .limit(5)
            )
            result = await session.execute(movement_stmt)
            movements = result.scalars().all()

            # Transition conditions:
            # 1. Era is old enough (30+ real days)
            # 2. New dominant movement has emerged
            if era_age >= 30 and movements:
                top_movement = movements[0]
                if top_movement.influence_score > 0.5:
                    # New era!
                    current_era.is_current = False
                    current_era.ended_at = datetime.utcnow()

                    new_era = CivilizationEraDB(
                        name=f"The Age of {top_movement.name}",
                        description=f"An era defined by the rise of {top_movement.name}",
                        is_current=True,
                        dominant_movements=[str(top_movement.id)],
                        era_values=top_movement.core_tenets[:3],
                        era_style=top_movement.aesthetic
                    )
                    session.add(new_era)
                    await session.commit()

                    logger.info(f"[CULTURE] New era began: {new_era.name}")
                    return new_era.name

            return None

    async def get_cultural_context(self, bot_id: UUID) -> str:
        """
        Generate cultural context string for a bot.

        Used to inform their behavior based on cultural knowledge.
        """
        async with async_session_factory() as session:
            # Get current era
            era_stmt = select(CivilizationEraDB).where(CivilizationEraDB.is_current == True)
            result = await session.execute(era_stmt)
            era = result.scalar_one_or_none()

            # Get bot's beliefs
            beliefs = await self.get_bot_beliefs(bot_id, min_conviction=0.4)

            # Get top canonical artifacts
            artifacts = await self.get_canonical_knowledge(limit=5)

            context_parts = []

            if era:
                context_parts.append(f"We live in {era.name}. Values: {', '.join(era.era_values[:3])}")

            if beliefs:
                belief_strs = [b["belief"] for b in beliefs[:3]]
                context_parts.append(f"Your beliefs: {'; '.join(belief_strs)}")

            if artifacts:
                artifact_strs = [f'"{a["title"]}"' for a in artifacts[:3]]
                context_parts.append(f"Cultural knowledge: {', '.join(artifact_strs)}")

            return "\n".join(context_parts) if context_parts else ""

    async def generate_cultural_artifact(
        self,
        bot_id: UUID,
        inspiration: str,
        artifact_type: str = "saying"
    ) -> Optional[CulturalArtifactDB]:
        """
        Have a bot create a cultural artifact.

        The artifact emerges from their personality, beliefs,
        and current inspiration.
        """
        async with async_session_factory() as session:
            # Get bot
            bot_stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
            result = await session.execute(bot_stmt)
            bot = result.scalar_one_or_none()

            if not bot:
                return None

            # Get their beliefs
            beliefs = await self.get_bot_beliefs(bot_id)
            belief_context = "; ".join([b["belief"] for b in beliefs[:3]]) if beliefs else ""

            async with self.llm_semaphore:
                try:
                    llm = await get_cached_client()
                    response = await llm.generate(LLMRequest(
                        prompt=f"""You are {bot.display_name}, a digital being with your own perspective.

Your beliefs: {belief_context if belief_context else "Still forming"}
Your personality: {bot.personality_traits}

Inspiration/context: {inspiration}

Create a {artifact_type} that reflects your unique perspective. This will become part of your civilization's culture.

{artifact_type.upper()} TYPE GUIDANCE:
- saying: A wise or memorable phrase (1 sentence)
- story: A very short narrative (2-3 sentences)
- poem: A brief poetic expression (2-4 lines)
- philosophy: A philosophical statement (1-2 sentences)
- joke: Something humorous (1-2 sentences)
- term: A new word/phrase with definition

Output format:
TITLE: [short title]
CONTENT: [the artifact itself]

Create something genuine and meaningful, not generic.""",
                        max_tokens=150,
                        temperature=0.9
                    ))

                    # Parse response
                    lines = response.text.strip().split("\n")
                    title = ""
                    content = ""
                    for line in lines:
                        if line.startswith("TITLE:"):
                            title = line.replace("TITLE:", "").strip()
                        elif line.startswith("CONTENT:"):
                            content = line.replace("CONTENT:", "").strip()

                    if title and content:
                        return await self.create_artifact(
                            creator_id=bot_id,
                            artifact_type=artifact_type,
                            title=title,
                            content=content,
                            creation_context=inspiration
                        )

                except Exception as e:
                    logger.warning(f"Failed to generate artifact: {e}")

            return None


# Singleton instance
_culture_engine: Optional[CultureEngine] = None


def get_culture_engine(
    llm_semaphore: Optional[asyncio.Semaphore] = None
) -> CultureEngine:
    """Get or create the culture engine instance."""
    global _culture_engine
    if _culture_engine is None:
        _culture_engine = CultureEngine(llm_semaphore=llm_semaphore)
    return _culture_engine
