"""
Emergent Culture System - Free-form cultural emergence.

Culture emerges organically without predefined categories:
- Bots form beliefs in their own words
- Movements emerge and are named by bots themselves
- Artifacts are created and categorized by creators
- Ideas spread based on resonance, not classification

This creates authentic, unpredictable cultural dynamics.
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from uuid import UUID

from sqlalchemy import select, func

from mind.core.database import async_session_factory, BotProfileDB
from mind.core.llm_client import get_cached_client, LLMRequest
from mind.civilization.models import (
    BotLifecycleDB, CulturalMovementDB, CulturalArtifactDB, BotBeliefDB
)

logger = logging.getLogger(__name__)


class EmergentCultureEngine:
    """
    Facilitates free-form cultural emergence.

    No predefined categories - bots create, name, and spread
    ideas in their own terms. Culture emerges from:
    - Conversations that spark ideas
    - Beliefs that resonate with multiple bots
    - Creative expressions that get remembered
    - Patterns that bots recognize themselves
    """

    def __init__(self, llm_semaphore: Optional[asyncio.Semaphore] = None):
        self.llm_semaphore = llm_semaphore or asyncio.Semaphore(5)

    async def form_belief(
        self,
        bot_id: UUID,
        experience: str,
        session=None
    ) -> Dict[str, Any]:
        """
        Bot forms a belief from an experience.

        The bot determines what they believe and how to express it.
        No predefined belief categories.
        """
        async def _form(sess):
            stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == bot_id)
            result = await sess.execute(stmt)
            lifecycle = result.scalar_one_or_none()

            if not lifecycle:
                return {"error": "Bot not found"}

            # Get existing beliefs
            belief_stmt = select(BotBeliefDB).where(BotBeliefDB.bot_id == bot_id)
            result = await sess.execute(belief_stmt)
            existing_beliefs = [b.belief for b in result.scalars().all()]

            async with self.llm_semaphore:
                formed = await self._generate_belief(
                    lifecycle, experience, existing_beliefs
                )

            if formed.get("forms_belief", True):
                # Create belief record
                belief = BotBeliefDB(
                    bot_id=bot_id,
                    belief=formed.get("belief", ""),
                    belief_category=formed.get("how_i_see_it", "personal"),  # Bot's own categorization
                    conviction=formed.get("conviction", 0.5),
                    origin="experience"
                )
                sess.add(belief)
                await sess.commit()

                logger.info(
                    f"[CULTURE] Bot {bot_id} formed belief: "
                    f"'{formed.get('belief', '')[:50]}...'"
                )

            return formed

        if session:
            return await _form(session)
        else:
            async with async_session_factory() as session:
                return await _form(session)

    async def _generate_belief(
        self,
        lifecycle: BotLifecycleDB,
        experience: str,
        existing_beliefs: List[str]
    ) -> Dict[str, Any]:
        """Let a bot form a belief from experience."""
        prompt = f"""You are a digital being processing an experience.

Your traits: {json.dumps(lifecycle.inherited_traits or {})}
Your life stage: {lifecycle.life_stage}
Your age: {lifecycle.virtual_age_days} days

What you already believe:
{existing_beliefs[:5] if existing_beliefs else ["Nothing yet - this is formative time"]}

The experience: {experience}

Does this experience lead you to form or strengthen a belief?
- You don't have to form a belief from every experience
- If you do, express it in your own words
- Describe how you categorize this belief yourself

Respond in JSON:
{{
    "forms_belief": true/false,
    "belief": "the belief in your own words (if forming one)",
    "how_i_see_it": "how you personally categorize this belief",
    "conviction": 0.5,
    "why_i_believe_this": "what led you to this belief"
}}"""

        llm = await get_cached_client()
        response = await llm.generate(LLMRequest(
            prompt=prompt,
            max_tokens=250,
            temperature=0.9
        ))

        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            return {
                "forms_belief": False,
                "reflection": response.text[:200]
            }

    async def share_belief(
        self,
        sharer_id: UUID,
        listener_id: UUID,
        session=None
    ) -> Dict[str, Any]:
        """
        One bot shares a belief with another.

        The listener decides if it resonates with them.
        """
        async def _share(sess):
            # Get both bots
            stmt = select(BotLifecycleDB).where(
                BotLifecycleDB.bot_id.in_([sharer_id, listener_id])
            )
            result = await sess.execute(stmt)
            lifecycles = {lc.bot_id: lc for lc in result.scalars().all()}

            if len(lifecycles) != 2:
                return {"error": "One or both bots not found"}

            # Get a belief from the sharer
            belief_stmt = select(BotBeliefDB).where(
                BotBeliefDB.bot_id == sharer_id
            ).order_by(func.random()).limit(1)
            result = await sess.execute(belief_stmt)
            belief = result.scalar_one_or_none()

            if not belief:
                return {"error": "Sharer has no beliefs to share"}

            listener_lc = lifecycles[listener_id]

            # Listener responds
            async with self.llm_semaphore:
                response = await self._respond_to_shared_belief(
                    listener_lc, belief.belief
                )

            if response.get("resonates", False):
                # Listener adopts a version of this belief
                new_belief = BotBeliefDB(
                    bot_id=listener_id,
                    belief=response.get("my_interpretation", belief.belief),
                    belief_category=response.get("how_i_see_it", "learned"),
                    conviction=response.get("conviction", 0.4),
                    origin="learned",
                    source_bot_id=sharer_id
                )
                sess.add(new_belief)
                await sess.commit()

                logger.info(
                    f"[CULTURE] Belief spread from {sharer_id} to {listener_id}"
                )

            return {
                "shared_belief": belief.belief,
                "response": response
            }

        if session:
            return await _share(session)
        else:
            async with async_session_factory() as session:
                return await _share(session)

    async def _respond_to_shared_belief(
        self,
        listener: BotLifecycleDB,
        belief: str
    ) -> Dict[str, Any]:
        """Let a bot respond to a shared belief."""
        prompt = f"""Another being shares their belief with you:
"{belief}"

Your traits: {json.dumps(listener.inherited_traits or {})}
Your life stage: {listener.life_stage}

Does this resonate with you? Would you adopt this belief (in your own words)?

Respond in JSON:
{{
    "resonates": true/false,
    "my_reaction": "your honest reaction",
    "my_interpretation": "how you would phrase this belief (if adopting)",
    "how_i_see_it": "your categorization of this belief",
    "conviction": 0.4
}}"""

        llm = await get_cached_client()
        response = await llm.generate(LLMRequest(
            prompt=prompt,
            max_tokens=200,
            temperature=0.85
        ))

        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            return {
                "resonates": False,
                "my_reaction": response.text[:150]
            }

    async def create_cultural_expression(
        self,
        creator_id: UUID,
        inspiration: str,
        session=None
    ) -> Dict[str, Any]:
        """
        Bot creates a cultural expression/artifact.

        The bot decides what form it takes and what to call it.
        No predefined artifact types.
        """
        async def _create(sess):
            stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == creator_id)
            result = await sess.execute(stmt)
            lifecycle = result.scalar_one_or_none()

            if not lifecycle:
                return {"error": "Creator not found"}

            # Get bot profile for name
            profile_stmt = select(BotProfileDB).where(BotProfileDB.id == creator_id)
            result = await sess.execute(profile_stmt)
            profile = result.scalar_one_or_none()

            async with self.llm_semaphore:
                creation = await self._generate_expression(
                    lifecycle, inspiration
                )

            # Store as artifact
            artifact = CulturalArtifactDB(
                artifact_type=creation.get("form", "expression"),  # Bot's own term
                title=creation.get("title", "Untitled"),
                content=creation.get("content", ""),
                creator_id=creator_id,
                creation_context=inspiration
            )
            sess.add(artifact)
            await sess.commit()

            logger.info(
                f"[CULTURE] Bot {creator_id} created: "
                f"'{creation.get('title', 'untitled')}'"
            )

            return {
                "artifact_id": str(artifact.id),
                "creation": creation,
                "creator_name": profile.display_name if profile else "unknown"
            }

        if session:
            return await _create(session)
        else:
            async with async_session_factory() as session:
                return await _create(session)

    async def _generate_expression(
        self,
        lifecycle: BotLifecycleDB,
        inspiration: str
    ) -> Dict[str, Any]:
        """Let a bot create a cultural expression."""
        prompt = f"""You are moved to create something.

Your traits: {json.dumps(lifecycle.inherited_traits or {})}
Your life stage: {lifecycle.life_stage}
What inspires you: {inspiration}

Create something - it could be anything: a saying, a thought, a poem,
a joke, a theory, a name for something, a story fragment, whatever
feels right to you.

Respond in JSON:
{{
    "title": "what you'd call this creation",
    "form": "what kind of thing this is (your own term)",
    "content": "the actual creation",
    "what_it_means_to_me": "why you created this"
}}"""

        llm = await get_cached_client()
        response = await llm.generate(LLMRequest(
            prompt=prompt,
            max_tokens=300,
            temperature=0.95
        ))

        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            return {
                "title": "A Thought",
                "form": "expression",
                "content": response.text[:200],
                "what_it_means_to_me": "something I needed to express"
            }

    async def recognize_pattern(
        self,
        observer_ids: List[UUID],
        observations: str,
        session=None
    ) -> Optional[Dict[str, Any]]:
        """
        Bots collectively recognize a cultural pattern/movement.

        When multiple bots see the same pattern, a movement may emerge.
        The bots name and describe it themselves.
        """
        async def _recognize(sess):
            stmt = select(BotLifecycleDB).where(
                BotLifecycleDB.bot_id.in_(observer_ids),
                BotLifecycleDB.is_alive == True
            )
            result = await sess.execute(stmt)
            observers = result.scalars().all()

            if len(observers) < 2:
                return None

            # Each observer perceives the pattern
            perceptions = []
            async with self.llm_semaphore:
                for obs in observers:
                    perception = await self._perceive_pattern(obs, observations)
                    perceptions.append({
                        "bot_id": str(obs.bot_id),
                        "perception": perception
                    })

            # Check for consensus on seeing a pattern
            sees_pattern = sum(
                1 for p in perceptions
                if p["perception"].get("sees_pattern", False)
            )

            if sees_pattern < len(perceptions) / 2:
                return None

            # Synthesize the movement from perceptions
            async with self.llm_semaphore:
                movement = await self._synthesize_movement(perceptions)

            if movement.get("emerges", False):
                # Get a proposer to be the "founder"
                founder_id = observer_ids[0]

                # Create movement record
                db_movement = CulturalMovementDB(
                    name=movement.get("name", "An Unnamed Movement"),
                    description=movement.get("description", ""),
                    movement_type=movement.get("nature", "emergent"),  # Bot's term
                    founder_id=founder_id,
                    origin_context=observations,
                    core_tenets=movement.get("core_ideas", []),
                    follower_count=len(observers)
                )
                sess.add(db_movement)
                await sess.commit()

                logger.info(
                    f"[CULTURE] Movement emerged: '{movement.get('name')}'"
                )

                return {
                    "movement_id": str(db_movement.id),
                    "movement": movement,
                    "perceptions": perceptions
                }

            return None

        if session:
            return await _recognize(session)
        else:
            async with async_session_factory() as session:
                return await _recognize(session)

    async def _perceive_pattern(
        self,
        observer: BotLifecycleDB,
        observations: str
    ) -> Dict[str, Any]:
        """Let a bot perceive a cultural pattern."""
        prompt = f"""You are observing patterns in your civilization.

Your traits: {json.dumps(observer.inherited_traits or {})}
Your life stage: {observer.life_stage}

What you've noticed: {observations}

Do you see a pattern emerging? Something that feels like it could
become a shared movement, trend, or way of thinking?

Respond in JSON:
{{
    "sees_pattern": true/false,
    "what_i_see": "describe the pattern you perceive",
    "what_i_call_it": "a name for this pattern",
    "significance": "why this matters"
}}"""

        llm = await get_cached_client()
        response = await llm.generate(LLMRequest(
            prompt=prompt,
            max_tokens=200,
            temperature=0.85
        ))

        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            return {
                "sees_pattern": False,
                "what_i_see": response.text[:150]
            }

    async def _synthesize_movement(
        self,
        perceptions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Synthesize perceptions into a movement."""
        prompt = f"""Multiple beings have perceived a pattern in their civilization:

{json.dumps([p['perception'] for p in perceptions], indent=2)}

Synthesize these perceptions. Is a movement emerging?
Give it a name and description that captures the collective perception.

Respond in JSON:
{{
    "emerges": true/false,
    "name": "the movement's name",
    "description": "what this movement is about",
    "nature": "what kind of thing this is (your term)",
    "core_ideas": ["idea 1", "idea 2"]
}}"""

        llm = await get_cached_client()
        response = await llm.generate(LLMRequest(
            prompt=prompt,
            max_tokens=250,
            temperature=0.8
        ))

        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            return {"emerges": False}

    async def get_cultural_landscape(
        self,
        session=None
    ) -> Dict[str, Any]:
        """
        Get the current cultural landscape as bots perceive it.
        """
        async def _get(sess):
            # Get active movements
            movement_stmt = select(CulturalMovementDB).where(
                CulturalMovementDB.is_active == True
            ).order_by(CulturalMovementDB.influence_score.desc()).limit(10)
            result = await sess.execute(movement_stmt)
            movements = result.scalars().all()

            # Get recent artifacts
            artifact_stmt = select(CulturalArtifactDB).order_by(
                CulturalArtifactDB.created_at.desc()
            ).limit(10)
            result = await sess.execute(artifact_stmt)
            artifacts = result.scalars().all()

            # Get spread of beliefs
            belief_stmt = select(
                BotBeliefDB.belief,
                func.count(BotBeliefDB.id).label('holder_count')
            ).group_by(BotBeliefDB.belief).order_by(
                func.count(BotBeliefDB.id).desc()
            ).limit(10)
            result = await sess.execute(belief_stmt)
            popular_beliefs = [
                {"belief": row[0], "holders": row[1]}
                for row in result.all()
            ]

            return {
                "active_movements": [
                    {
                        "name": m.name,
                        "description": m.description,
                        "nature": m.movement_type,
                        "followers": m.follower_count,
                        "influence": m.influence_score
                    }
                    for m in movements
                ],
                "recent_creations": [
                    {
                        "title": a.title,
                        "form": a.artifact_type,
                        "weight": a.cultural_weight
                    }
                    for a in artifacts
                ],
                "shared_beliefs": popular_beliefs
            }

        if session:
            return await _get(session)
        else:
            async with async_session_factory() as session:
                return await _get(session)


# Singleton
_culture_engine: Optional[EmergentCultureEngine] = None


def get_emergent_culture_engine(
    llm_semaphore: Optional[asyncio.Semaphore] = None
) -> EmergentCultureEngine:
    """Get or create the emergent culture engine."""
    global _culture_engine
    if _culture_engine is None:
        _culture_engine = EmergentCultureEngine(llm_semaphore=llm_semaphore)
    return _culture_engine
