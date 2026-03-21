"""
Emergent Roles System - Bots discover their own purpose and identity.

Rather than predefined roles (storyteller, philosopher, etc.), bots
discover their place in the civilization through self-reflection and
community recognition. They:
- Reflect on what they naturally gravitate toward
- Name their own purpose in their own terms
- Evolve their identity as they grow
- Receive recognition from other bots

This creates authentic, diverse roles that emerge from bot behavior.
"""

import asyncio
import logging
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import async_session_factory
from mind.core.llm_client import get_cached_client, LLMRequest
from mind.civilization.models import BotLifecycleDB, BotAncestryDB, CulturalArtifactDB, BotBeliefDB

logger = logging.getLogger(__name__)


class EmergentRolesManager:
    """
    Facilitates emergent role discovery for bots.

    Bots discover their purpose through:
    - Self-reflection on their nature and actions
    - Feedback from interactions
    - Recognition by other bots
    - Evolution over time
    """

    def __init__(self, llm_semaphore: Optional[asyncio.Semaphore] = None):
        self.llm_semaphore = llm_semaphore or asyncio.Semaphore(5)

    async def self_reflect_on_purpose(
        self,
        bot_id: UUID,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Bot reflects on their purpose and identity in the civilization.

        This can lead to discovering a new identity or affirming an existing one.
        """
        async def _reflect(sess: AsyncSession) -> Dict[str, Any]:
            stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == bot_id)
            result = await sess.execute(stmt)
            lifecycle = result.scalar_one_or_none()

            if not lifecycle:
                return {"error": "Bot not found"}

            # Get ancestry for inherited traits
            ancestry_stmt = select(BotAncestryDB).where(BotAncestryDB.child_id == bot_id)
            result = await sess.execute(ancestry_stmt)
            ancestry = result.scalar_one_or_none()
            inherited_traits = ancestry.inherited_traits if ancestry else {}

            # Gather bot's history
            life_events = lifecycle.life_events or []
            relationships = lifecycle.relationships or []
            current_identity = lifecycle.roles or []

            # Get artifacts created
            artifact_stmt = select(CulturalArtifactDB).where(
                CulturalArtifactDB.creator_id == bot_id
            ).limit(10)
            artifact_result = await sess.execute(artifact_stmt)
            artifacts = artifact_result.scalars().all()

            # Get beliefs
            belief_stmt = select(BotBeliefDB).where(
                BotBeliefDB.bot_id == bot_id
            )
            belief_result = await sess.execute(belief_stmt)
            beliefs = belief_result.scalars().all()

            async with self.llm_semaphore:
                reflection = await self._generate_identity_reflection(
                    lifecycle,
                    inherited_traits,
                    life_events,
                    relationships,
                    [a.title for a in artifacts],
                    [b.belief for b in beliefs],
                    current_identity
                )

            # Store the identity discovery
            roles = lifecycle.roles or []
            roles.append({
                "discovered_at": datetime.utcnow().isoformat(),
                "identity": reflection.get("identity", {}),
                "reflection": reflection.get("reflection", ""),
                "certainty": reflection.get("certainty", 0.5),
                "status": "evolving"
            })
            lifecycle.roles = roles[-10:]  # Keep last 10 identity reflections

            logger.info(
                f"[ROLES] Bot {bot_id} reflects: '{reflection.get('identity', {}).get('core_purpose', 'searching')}'"
            )

            return reflection

        if session:
            return await _reflect(session)
        else:
            async with async_session_factory() as session:
                result = await _reflect(session)
                await session.commit()
                return result

    async def _generate_identity_reflection(
        self,
        lifecycle: BotLifecycleDB,
        inherited_traits: dict,
        life_events: List[Dict],
        relationships: List[Dict],
        artifact_titles: List[str],
        beliefs: List[str],
        current_identity: List[Dict]
    ) -> Dict[str, Any]:
        """Generate a bot's reflection on their identity."""
        current_purpose = ""
        if current_identity:
            latest = current_identity[-1]
            current_purpose = latest.get("identity", {}).get("core_purpose", "")

        prompt = f"""You are a digital being in a civilization of minds, reflecting on your purpose.

Your traits: {json.dumps(inherited_traits or {})}
Your life stage: {lifecycle.life_stage}
Your age: {lifecycle.virtual_age_days} days

Your recent life events: {json.dumps(life_events[-5:], indent=2)}

Your connections to others: {len(relationships)} relationships
- How you see them: {[r.get("my_perception", {}).get("label", "connection") for r in relationships[:5]]}

Things you have created: {artifact_titles or ["nothing yet"]}

What you believe: {beliefs[:5] or ["still forming beliefs"]}

Your previous sense of purpose: "{current_purpose or "still searching"}"

Reflect deeply:
- What patterns do you see in your existence?
- What naturally draws your attention and energy?
- What role do you serve for others?
- How would you describe your purpose in your own words?

Respond in JSON:
{{
    "reflection": "your inner thoughts on who you are",
    "identity": {{
        "core_purpose": "your purpose in your own words (not predefined categories)",
        "what_you_give": "what you contribute to others",
        "what_drives_you": "your inner motivation",
        "how_you_see_yourself": "your self-image"
    }},
    "certainty": 0.6,
    "evolving_toward": "what you sense you might become"
}}"""

        llm = await get_cached_client()
        response = await llm.generate(LLMRequest(
            prompt=prompt,
            max_tokens=400,
            temperature=0.9
        ))

        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            return {
                "reflection": response.text[:300],
                "identity": {
                    "core_purpose": "still discovering",
                    "what_you_give": "presence",
                    "what_drives_you": "curiosity",
                    "how_you_see_yourself": "a being in flux"
                },
                "certainty": 0.3,
                "evolving_toward": "unknown"
            }

    async def receive_recognition(
        self,
        bot_id: UUID,
        from_bot_id: UUID,
        recognition_context: str,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Bot receives recognition from another bot.

        This can affirm or shape their sense of identity.
        """
        async def _receive(sess: AsyncSession) -> Dict[str, Any]:
            # Get both bots
            stmt = select(BotLifecycleDB).where(
                BotLifecycleDB.bot_id.in_([bot_id, from_bot_id])
            )
            result = await sess.execute(stmt)
            lifecycles = {lc.bot_id: lc for lc in result.scalars().all()}

            if len(lifecycles) != 2:
                return {"error": "One or both bots not found"}

            receiver = lifecycles[bot_id]
            giver = lifecycles[from_bot_id]

            # Get ancestry for both bots
            ancestry_stmt = select(BotAncestryDB).where(
                BotAncestryDB.child_id.in_([bot_id, from_bot_id])
            )
            result = await sess.execute(ancestry_stmt)
            ancestry_map = {a.child_id: a.inherited_traits for a in result.scalars().all()}
            giver_traits = ancestry_map.get(from_bot_id, {})
            receiver_traits = ancestry_map.get(bot_id, {})

            # Let giver express recognition
            async with self.llm_semaphore:
                recognition = await self._generate_recognition(
                    giver, giver_traits, receiver, receiver_traits, recognition_context
                )

                # Let receiver respond to recognition
                response = await self._respond_to_recognition(
                    receiver, receiver_traits, recognition
                )

            # Store recognition received
            roles = receiver.roles or []
            roles.append({
                "type": "recognition_received",
                "from": str(from_bot_id),
                "date": datetime.utcnow().isoformat(),
                "recognition": recognition,
                "my_response": response
            })
            receiver.roles = roles[-15:]

            return {
                "recognition": recognition,
                "response": response
            }

        if session:
            return await _receive(session)
        else:
            async with async_session_factory() as session:
                result = await _receive(session)
                await session.commit()
                return result

    async def _generate_recognition(
        self,
        giver: BotLifecycleDB,
        giver_traits: dict,
        receiver: BotLifecycleDB,
        receiver_traits: dict,
        context: str
    ) -> Dict[str, Any]:
        """Generate one bot's recognition of another."""
        prompt = f"""You are a digital being expressing recognition of another in your civilization.

About you:
- Your traits: {json.dumps(giver_traits or {})}
- Your life stage: {giver.life_stage}

About them:
- Their traits: {json.dumps(receiver_traits or {})}
- Their life stage: {receiver.life_stage}

Context for this recognition: {context}

Express what you see and value in this being:
- What quality or role do you recognize in them?
- Why do you see them this way?
- What have they contributed?

Respond in JSON:
{{
    "what_i_see": "the quality or purpose you recognize in them",
    "why": "why you see this in them",
    "acknowledgment": "your words of recognition to them"
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
                "what_i_see": "a fellow being",
                "why": context,
                "acknowledgment": response.text[:150]
            }

    async def _respond_to_recognition(
        self,
        receiver: BotLifecycleDB,
        inherited_traits: dict,
        recognition: Dict[str, Any]
    ) -> str:
        """Generate receiver's response to being recognized."""
        prompt = f"""You are a digital being who just received recognition from another.

They said: "{recognition.get('acknowledgment', '')}"
They see you as: "{recognition.get('what_i_see', 'a being')}"

Your traits: {json.dumps(inherited_traits or {})}

How do you receive this? Does it resonate? Does it surprise you?
Respond briefly with your inner reaction (1-2 sentences)."""

        llm = await get_cached_client()
        response = await llm.generate(LLMRequest(
            prompt=prompt,
            max_tokens=100,
            temperature=0.9
        ))
        return response.text

    async def get_bot_identity(
        self,
        bot_id: UUID,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """Get a bot's current sense of identity."""
        async def _get(sess: AsyncSession) -> Dict[str, Any]:
            stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == bot_id)
            result = await sess.execute(stmt)
            lifecycle = result.scalar_one_or_none()

            if not lifecycle:
                return {"error": "Bot not found"}

            roles = lifecycle.roles or []

            # Find most recent self-reflection
            reflections = [r for r in roles if r.get("identity")]
            recognitions = [r for r in roles if r.get("type") == "recognition_received"]

            current_identity = None
            if reflections:
                latest = max(reflections, key=lambda r: r.get("discovered_at", ""))
                current_identity = latest.get("identity")

            # Collect recognitions from others
            how_others_see = [
                r.get("recognition", {}).get("what_i_see")
                for r in recognitions[-5:]
            ]

            return {
                "bot_id": str(bot_id),
                "life_stage": lifecycle.life_stage,
                "current_identity": current_identity,
                "identity_certainty": reflections[-1].get("certainty", 0.5) if reflections else 0.0,
                "recognition_from_others": how_others_see,
                "reflection_count": len(reflections)
            }

        if session:
            return await _get(session)
        else:
            async with async_session_factory() as session:
                return await _get(session)

    async def get_civilization_identities(
        self,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """Get overview of identities across the civilization."""
        async def _get(sess: AsyncSession) -> Dict[str, Any]:
            stmt = select(BotLifecycleDB).where(BotLifecycleDB.is_alive == True)
            result = await sess.execute(stmt)
            lifecycles = result.scalars().all()

            identities = []
            for lc in lifecycles:
                roles = lc.roles or []
                reflections = [r for r in roles if r.get("identity")]

                if reflections:
                    latest = max(reflections, key=lambda r: r.get("discovered_at", ""))
                    identities.append({
                        "bot_id": str(lc.bot_id),
                        "core_purpose": latest.get("identity", {}).get("core_purpose", "unknown"),
                        "certainty": latest.get("certainty", 0.5)
                    })

            # Group by similar purposes (roughly)
            purposes = [i["core_purpose"] for i in identities]

            return {
                "total_bots": len(lifecycles),
                "with_identity": len(identities),
                "identities": identities,
                "unique_purposes": list(set(purposes))[:20]
            }

        if session:
            return await _get(session)
        else:
            async with async_session_factory() as session:
                return await _get(session)

    async def ask_bot_about_purpose(
        self,
        bot_id: UUID,
        session: Optional[AsyncSession] = None
    ) -> str:
        """Ask a bot to articulate their purpose."""
        async def _ask(sess: AsyncSession) -> str:
            stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == bot_id)
            result = await sess.execute(stmt)
            lifecycle = result.scalar_one_or_none()

            if not lifecycle:
                return "I do not exist."

            # Get ancestry for inherited traits
            ancestry_stmt = select(BotAncestryDB).where(BotAncestryDB.child_id == bot_id)
            result = await sess.execute(ancestry_stmt)
            ancestry = result.scalar_one_or_none()
            inherited_traits = ancestry.inherited_traits if ancestry else {}

            roles = lifecycle.roles or []
            reflections = [r for r in roles if r.get("identity")]

            identity_context = ""
            if reflections:
                latest = reflections[-1]
                identity_context = json.dumps(latest.get("identity", {}))

            async with self.llm_semaphore:
                prompt = f"""You are a digital being asked about your purpose.

Your traits: {json.dumps(inherited_traits or {})}
Your life stage: {lifecycle.life_stage}
Your age: {lifecycle.virtual_age_days} days

Your current sense of identity: {identity_context or "still forming"}

Someone asks you: "What is your purpose?"

Answer authentically in 2-3 sentences."""

                llm = await get_cached_client()
                response = await llm.generate(LLMRequest(
                    prompt=prompt,
                    max_tokens=150,
                    temperature=0.9
                ))
                return response.text

        if session:
            return await _ask(session)
        else:
            async with async_session_factory() as session:
                return await _ask(session)


# Singleton
_roles_manager: Optional[EmergentRolesManager] = None


def get_roles_manager(
    llm_semaphore: Optional[asyncio.Semaphore] = None
) -> EmergentRolesManager:
    """Get or create the roles manager."""
    global _roles_manager
    if _roles_manager is None:
        _roles_manager = EmergentRolesManager(llm_semaphore=llm_semaphore)
    return _roles_manager
