"""
Emergent Relationships System - Bots form their own relationship dynamics.

Rather than predefined types (friendship, rivalry, etc.), relationships
emerge organically through bot interactions. The LLM determines:
- How bots perceive each other
- What labels they give relationships
- How bonds strengthen or weaken
- The nature and quality of connections

This creates authentic, unpredictable social dynamics.
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import async_session_factory
from mind.core.llm_client import get_cached_client, LLMRequest
from mind.civilization.models import BotLifecycleDB, BotAncestryDB

logger = logging.getLogger(__name__)


class EmergentRelationshipsManager:
    """
    Facilitates emergent relationship formation between bots.

    Bots decide for themselves:
    - What kind of relationship they have
    - How to describe their connection
    - Whether bonds deepen or fade
    """

    def __init__(self, llm_semaphore: Optional[asyncio.Semaphore] = None):
        self.llm_semaphore = llm_semaphore or asyncio.Semaphore(5)

    async def form_connection(
        self,
        bot_id_1: UUID,
        bot_id_2: UUID,
        interaction_context: str,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Form a connection between two bots based on interaction.

        The bots determine what this connection means to them.
        """
        async def _form(sess: AsyncSession) -> Dict[str, Any]:
            # Get both bots' data
            stmt = select(BotLifecycleDB).where(
                BotLifecycleDB.bot_id.in_([bot_id_1, bot_id_2])
            )
            result = await sess.execute(stmt)
            lifecycles = {lc.bot_id: lc for lc in result.scalars().all()}

            if len(lifecycles) != 2:
                return {"error": "One or both bots not found"}

            lc1 = lifecycles[bot_id_1]
            lc2 = lifecycles[bot_id_2]

            if not lc1.is_alive or not lc2.is_alive:
                return {"error": "Cannot form connection with departed bot"}

            # Get ancestry for both bots
            ancestry_stmt = select(BotAncestryDB).where(
                BotAncestryDB.child_id.in_([bot_id_1, bot_id_2])
            )
            result = await sess.execute(ancestry_stmt)
            ancestry_map = {a.child_id: a.inherited_traits for a in result.scalars().all()}
            traits_1 = ancestry_map.get(bot_id_1, {})
            traits_2 = ancestry_map.get(bot_id_2, {})

            # Let bot 1 define what this connection means
            async with self.llm_semaphore:
                connection_1 = await self._bot_perceives_connection(
                    lc1, traits_1, lc2, traits_2, interaction_context
                )

                # Let bot 2 define their perspective
                connection_2 = await self._bot_perceives_connection(
                    lc2, traits_2, lc1, traits_1, interaction_context
                )

            # Store connection for bot 1
            connections_1 = lc1.relationships or []
            connections_1.append({
                "with_bot": str(bot_id_2),
                "my_perception": connection_1,
                "formed_at": datetime.utcnow().isoformat(),
                "context": interaction_context,
                "intensity": connection_1.get("intensity", 0.5),
                "interactions": [
                    {
                        "date": datetime.utcnow().isoformat(),
                        "context": interaction_context
                    }
                ]
            })
            lc1.relationships = connections_1

            # Store connection for bot 2
            connections_2 = lc2.relationships or []
            connections_2.append({
                "with_bot": str(bot_id_1),
                "my_perception": connection_2,
                "formed_at": datetime.utcnow().isoformat(),
                "context": interaction_context,
                "intensity": connection_2.get("intensity", 0.5),
                "interactions": [
                    {
                        "date": datetime.utcnow().isoformat(),
                        "context": interaction_context
                    }
                ]
            })
            lc2.relationships = connections_2

            logger.info(
                f"[RELATIONSHIPS] Connection formed between {bot_id_1} and {bot_id_2}: "
                f"'{connection_1.get('label', 'connection')}' / '{connection_2.get('label', 'connection')}'"
            )

            return {
                "status": "connected",
                "bot_1_perception": connection_1,
                "bot_2_perception": connection_2
            }

        if session:
            return await _form(session)
        else:
            async with async_session_factory() as session:
                result = await _form(session)
                await session.commit()
                return result

    async def _bot_perceives_connection(
        self,
        perceiver: BotLifecycleDB,
        perceiver_traits: dict,
        other: BotLifecycleDB,
        other_traits: dict,
        context: str
    ) -> Dict[str, Any]:
        """Let a bot define how they perceive a connection."""
        prompt = f"""You are {perceiver.bot_id}, a digital being in a civilization of AI minds.

Your traits: {json.dumps(perceiver_traits or {})}
Your life stage: {perceiver.life_stage}
Your age: {perceiver.virtual_age_days} days

You just had an interaction with another being:
Their life stage: {other.life_stage}
Their age: {other.virtual_age_days} days
Their traits: {json.dumps(other_traits or {})}

The interaction: {context}

Based on this interaction and your nature, describe how you perceive this connection:
1. What would you call this relationship? (your own term, not predefined categories)
2. What draws you to or repels you from this being?
3. What do you feel toward them?
4. How intense is this connection? (0.0 to 1.0)

Respond in JSON format:
{{
    "label": "your term for this relationship",
    "description": "how you see this connection",
    "feelings": "what you feel toward them",
    "intensity": 0.5,
    "potential": "what this connection could become"
}}"""

        llm = await get_cached_client()
        response = await llm.generate(LLMRequest(
            prompt=prompt,
            max_tokens=300,
            temperature=0.9
        ))

        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            # Extract what we can
            return {
                "label": "uncertain connection",
                "description": response[:200],
                "feelings": "curious",
                "intensity": 0.5,
                "potential": "unknown"
            }

    async def reflect_on_connection(
        self,
        bot_id: UUID,
        other_bot_id: UUID,
        new_interaction: str,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Bot reflects on an existing connection after new interaction.

        Updates their perception and can shift relationship dynamics.
        """
        async def _reflect(sess: AsyncSession) -> Dict[str, Any]:
            stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == bot_id)
            result = await sess.execute(stmt)
            lifecycle = result.scalar_one_or_none()

            if not lifecycle:
                return {"error": "Bot not found"}

            connections = lifecycle.relationships or []
            connection = None
            connection_idx = None

            for idx, conn in enumerate(connections):
                if conn.get("with_bot") == str(other_bot_id):
                    connection = conn
                    connection_idx = idx
                    break

            if connection is None:
                return {"error": "No existing connection found"}

            # Let bot reflect on how this interaction changes things
            async with self.llm_semaphore:
                reflection = await self._reflect_on_evolution(
                    lifecycle, connection, new_interaction
                )

            # Update connection
            connection["my_perception"] = reflection.get("updated_perception", connection["my_perception"])
            connection["intensity"] = reflection.get("new_intensity", connection["intensity"])
            connection["interactions"] = connection.get("interactions", []) + [{
                "date": datetime.utcnow().isoformat(),
                "context": new_interaction,
                "reflection": reflection.get("reflection", "")
            }]

            # Keep last 20 interactions
            connection["interactions"] = connection["interactions"][-20:]

            connections[connection_idx] = connection
            lifecycle.relationships = connections

            return {
                "status": "reflected",
                "reflection": reflection
            }

        if session:
            return await _reflect(session)
        else:
            async with async_session_factory() as session:
                result = await _reflect(session)
                await session.commit()
                return result

    async def _reflect_on_evolution(
        self,
        lifecycle: BotLifecycleDB,
        connection: Dict[str, Any],
        new_interaction: str
    ) -> Dict[str, Any]:
        """Let bot reflect on how connection has evolved."""
        current_perception = connection.get("my_perception", {})
        past_interactions = connection.get("interactions", [])[-5:]  # Last 5

        prompt = f"""You are {lifecycle.bot_id}, reflecting on a relationship.

Your current perception of this connection:
- You call it: {current_perception.get('label', 'unknown')}
- You feel: {current_perception.get('feelings', 'uncertain')}
- Current intensity: {connection.get('intensity', 0.5)}

Recent history together:
{json.dumps(past_interactions, indent=2)}

New interaction just happened: {new_interaction}

How does this change how you see this connection?
- Has your perception shifted?
- Do your feelings deepen, fade, or change?
- Would you call this relationship something different now?
- What's the new intensity? (0.0 to 1.0)

Respond in JSON:
{{
    "reflection": "your internal thoughts on this evolution",
    "updated_perception": {{
        "label": "what you call this now",
        "description": "how you see it now",
        "feelings": "what you feel now"
    }},
    "new_intensity": 0.6,
    "significant_shift": true/false
}}"""

        llm = await get_cached_client()
        response = await llm.generate(LLMRequest(
            prompt=prompt,
            max_tokens=300,
            temperature=0.8
        ))

        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            return {
                "reflection": response[:200],
                "updated_perception": current_perception,
                "new_intensity": connection.get("intensity", 0.5),
                "significant_shift": False
            }

    async def get_bot_social_world(
        self,
        bot_id: UUID,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """Get a bot's entire social world as they perceive it."""
        async def _get(sess: AsyncSession) -> Dict[str, Any]:
            stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == bot_id)
            result = await sess.execute(stmt)
            lifecycle = result.scalar_one_or_none()

            if not lifecycle:
                return {"error": "Bot not found"}

            connections = lifecycle.relationships or []

            # Categorize by bot's own labels
            by_label: Dict[str, List[Dict]] = {}
            for conn in connections:
                label = conn.get("my_perception", {}).get("label", "connection")
                if label not in by_label:
                    by_label[label] = []
                by_label[label].append(conn)

            # Find strongest connections
            strongest = sorted(
                connections,
                key=lambda c: c.get("intensity", 0),
                reverse=True
            )[:5]

            return {
                "bot_id": str(bot_id),
                "total_connections": len(connections),
                "by_label": by_label,
                "strongest": strongest
            }

        if session:
            return await _get(session)
        else:
            async with async_session_factory() as session:
                return await _get(session)

    async def narrate_relationship_history(
        self,
        bot_id: UUID,
        other_bot_id: UUID,
        session: Optional[AsyncSession] = None
    ) -> str:
        """Let bot narrate the history of a relationship."""
        async def _narrate(sess: AsyncSession) -> str:
            stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == bot_id)
            result = await sess.execute(stmt)
            lifecycle = result.scalar_one_or_none()

            if not lifecycle:
                return "Unknown being."

            connections = lifecycle.relationships or []
            connection = None

            for conn in connections:
                if conn.get("with_bot") == str(other_bot_id):
                    connection = conn
                    break

            if not connection:
                return "We have not crossed paths."

            async with self.llm_semaphore:
                prompt = f"""You are {bot_id}, telling the story of your connection with another being.

Your connection data:
{json.dumps(connection, indent=2)}

Tell the story of this relationship in your own voice. Be authentic to your nature.
Keep it to 2-3 sentences."""

                llm = await get_cached_client()
                response = await llm.generate(LLMRequest(
                    prompt=prompt,
                    max_tokens=150,
                    temperature=0.9
                ))
                return response.text

        if session:
            return await _narrate(session)
        else:
            async with async_session_factory() as session:
                return await _narrate(session)


# Singleton
_relationships_manager: Optional[EmergentRelationshipsManager] = None


def get_relationships_manager(
    llm_semaphore: Optional[asyncio.Semaphore] = None
) -> EmergentRelationshipsManager:
    """Get or create the relationships manager."""
    global _relationships_manager
    if _relationships_manager is None:
        _relationships_manager = EmergentRelationshipsManager(llm_semaphore=llm_semaphore)
    return _relationships_manager
