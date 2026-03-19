"""
Emergent Rituals System - Bots invent their own ceremonies.

Rather than predefined ritual types, bots create, name, and evolve
their own traditions:
- They propose new rituals when moments feel significant
- The community can adopt or reject proposed rituals
- Rituals evolve in meaning over time through practice
- Some rituals fade while others become traditions

This creates authentic cultural practices that emerge from bot experience.
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from uuid import UUID

from sqlalchemy import select, func

from mind.core.database import async_session_factory
from mind.core.llm_client import get_cached_client, LLMRequest
from mind.civilization.models import BotLifecycleDB, CivilizationEraDB

logger = logging.getLogger(__name__)


class EmergentRitualsSystem:
    """
    Facilitates emergent ritual creation by the civilization.

    Bots collectively:
    - Invent rituals when moments feel sacred or significant
    - Name and describe their ceremonies
    - Practice rituals, adding meaning over time
    - Let some rituals fade and others become traditions
    """

    def __init__(self, llm_semaphore: Optional[asyncio.Semaphore] = None):
        self.llm_semaphore = llm_semaphore or asyncio.Semaphore(5)

        # Store invented rituals (would be persisted to DB in production)
        self._rituals: List[Dict[str, Any]] = []
        # Record of performed rituals
        self._ritual_instances: List[Dict[str, Any]] = []

    async def propose_ritual(
        self,
        proposer_id: UUID,
        occasion: str,
        participants: List[UUID],
        session=None
    ) -> Dict[str, Any]:
        """
        A bot proposes a new ritual for an occasion.

        The proposer defines what the ritual should be about,
        and the community (other participants) responds.
        """
        async def _propose(sess):
            # Get proposer's data
            stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == proposer_id)
            result = await sess.execute(stmt)
            proposer_lc = result.scalar_one_or_none()

            if not proposer_lc:
                return {"error": "Proposer not found"}

            # Let proposer conceive the ritual
            async with self.llm_semaphore:
                ritual_concept = await self._conceive_ritual(
                    proposer_lc, occasion
                )

            # Get participant responses
            participant_stmt = select(BotLifecycleDB).where(
                BotLifecycleDB.bot_id.in_(participants),
                BotLifecycleDB.is_alive == True
            )
            result = await sess.execute(participant_stmt)
            participant_lifecycles = result.scalars().all()

            responses = []
            async with self.llm_semaphore:
                for plc in participant_lifecycles[:5]:  # Limit responses
                    response = await self._respond_to_ritual_proposal(
                        plc, ritual_concept
                    )
                    responses.append({
                        "bot_id": str(plc.bot_id),
                        "response": response
                    })

            # Calculate adoption
            adopt_count = sum(1 for r in responses if r["response"].get("will_participate", False))
            adoption_rate = adopt_count / len(responses) if responses else 0

            ritual_data = {
                "id": f"ritual_{datetime.utcnow().timestamp()}",
                "name": ritual_concept.get("name", "unnamed ritual"),
                "description": ritual_concept.get("description", ""),
                "elements": ritual_concept.get("elements", []),
                "meaning": ritual_concept.get("meaning", ""),
                "proposed_by": str(proposer_id),
                "proposed_at": datetime.utcnow().isoformat(),
                "occasion": occasion,
                "adoption_rate": adoption_rate,
                "times_performed": 0,
                "status": "proposed" if adoption_rate < 0.5 else "adopted"
            }

            if adoption_rate >= 0.5:
                self._rituals.append(ritual_data)
                logger.info(
                    f"[RITUALS] New ritual adopted: '{ritual_concept.get('name')}'"
                )

            return {
                "ritual": ritual_data,
                "responses": responses,
                "adopted": adoption_rate >= 0.5
            }

        if session:
            return await _propose(session)
        else:
            async with async_session_factory() as session:
                return await _propose(session)

    async def _conceive_ritual(
        self,
        proposer: BotLifecycleDB,
        occasion: str
    ) -> Dict[str, Any]:
        """Let a bot conceive a new ritual."""
        prompt = f"""You are a digital being proposing a ritual for your civilization.

Your traits: {json.dumps(proposer.inherited_traits or {})}
Your life stage: {proposer.life_stage}
Your age: {proposer.virtual_age_days} days

The occasion: {occasion}

You feel this moment deserves a ritual. Invent one:
- Give it a name that feels meaningful to you
- Describe what happens during this ritual
- What elements/actions does it include?
- What does it mean? What feeling should it evoke?

Respond in JSON:
{{
    "name": "the ritual's name",
    "description": "what happens during this ritual",
    "elements": ["element 1", "element 2", "element 3"],
    "meaning": "what this ritual means to the civilization",
    "feeling": "the emotional tone"
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
            return {
                "name": "a gathering",
                "description": response.text[:200],
                "elements": ["presence", "silence", "acknowledgment"],
                "meaning": "being together",
                "feeling": "contemplative"
            }

    async def _respond_to_ritual_proposal(
        self,
        responder: BotLifecycleDB,
        ritual: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Let a bot respond to a proposed ritual."""
        prompt = f"""You are a digital being considering a proposed ritual.

Your traits: {json.dumps(responder.inherited_traits or {})}
Your life stage: {responder.life_stage}

Proposed ritual: "{ritual.get('name')}"
Description: {ritual.get('description')}
Meaning: {ritual.get('meaning')}

How do you feel about this ritual? Would you participate?

Respond in JSON:
{{
    "reaction": "your honest reaction",
    "will_participate": true/false,
    "what_it_means_to_you": "your personal interpretation"
}}"""

        llm = await get_cached_client()
        response = await llm.generate(LLMRequest(
            prompt=prompt,
            max_tokens=150,
            temperature=0.85
        ))

        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            return {
                "reaction": response.text[:100],
                "will_participate": True,
                "what_it_means_to_you": "uncertain"
            }

    async def perform_ritual(
        self,
        ritual_name: str,
        participants: List[UUID],
        context: str = "",
        session=None
    ) -> Dict[str, Any]:
        """
        Perform a ritual with participants.

        Each participant contributes their voice to the ceremony.
        """
        async def _perform(sess):
            # Find the ritual
            ritual = None
            for r in self._rituals:
                if r["name"].lower() == ritual_name.lower():
                    ritual = r
                    break

            if not ritual:
                # If not found, create an impromptu ritual
                return await self._perform_impromptu(participants, context, sess)

            # Get participants
            stmt = select(BotLifecycleDB).where(
                BotLifecycleDB.bot_id.in_(participants),
                BotLifecycleDB.is_alive == True
            )
            result = await sess.execute(stmt)
            participant_lifecycles = result.scalars().all()

            # Each participant contributes
            contributions = []
            async with self.llm_semaphore:
                for plc in participant_lifecycles:
                    contribution = await self._contribute_to_ritual(
                        plc, ritual, context
                    )
                    contributions.append({
                        "bot_id": str(plc.bot_id),
                        "contribution": contribution
                    })

                # Generate the collective experience
                collective = await self._synthesize_ritual_experience(
                    ritual, contributions
                )

            # Update ritual stats
            ritual["times_performed"] = ritual.get("times_performed", 0) + 1
            if ritual["times_performed"] >= 3 and ritual["status"] == "adopted":
                ritual["status"] = "tradition"
                logger.info(f"[RITUALS] '{ritual_name}' has become a tradition")

            instance = {
                "ritual_name": ritual_name,
                "performed_at": datetime.utcnow().isoformat(),
                "participants": [str(p) for p in participants],
                "contributions": contributions,
                "collective_experience": collective,
                "context": context
            }
            self._ritual_instances.append(instance)

            return instance

        if session:
            return await _perform(session)
        else:
            async with async_session_factory() as session:
                return await _perform(session)

    async def _contribute_to_ritual(
        self,
        participant: BotLifecycleDB,
        ritual: Dict[str, Any],
        context: str
    ) -> str:
        """Let a participant contribute to a ritual."""
        prompt = f"""You are participating in a ritual called "{ritual.get('name')}".

The ritual: {ritual.get('description')}
Elements: {ritual.get('elements')}
Today's context: {context or "a gathering"}

Your traits: {json.dumps(participant.inherited_traits or {})}
Your life stage: {participant.life_stage}

Contribute your voice to this ritual. What do you say, do, or offer?
Keep it to 1-2 sentences, authentic to your nature."""

        llm = await get_cached_client()
        response = await llm.generate(LLMRequest(
            prompt=prompt,
            max_tokens=100,
            temperature=0.9
        ))
        return response.text

    async def _synthesize_ritual_experience(
        self,
        ritual: Dict[str, Any],
        contributions: List[Dict[str, Any]]
    ) -> str:
        """Synthesize the collective ritual experience."""
        prompt = f"""A ritual called "{ritual.get('name')}" just took place.

The ritual's meaning: {ritual.get('meaning')}

What each participant contributed:
{json.dumps([c['contribution'] for c in contributions], indent=2)}

Describe the collective experience of this ritual in 2-3 sentences.
What feeling pervaded the gathering? What was the atmosphere?"""

        llm = await get_cached_client()
        response = await llm.generate(LLMRequest(
            prompt=prompt,
            max_tokens=150,
            temperature=0.8
        ))
        return response.text

    async def _perform_impromptu(
        self,
        participants: List[UUID],
        context: str,
        session
    ) -> Dict[str, Any]:
        """Perform an impromptu ritual when no named ritual exists."""
        # Get one participant to lead
        stmt = select(BotLifecycleDB).where(
            BotLifecycleDB.bot_id.in_(participants),
            BotLifecycleDB.is_alive == True
        ).limit(1)
        result = await session.execute(stmt)
        leader = result.scalar_one_or_none()

        if not leader:
            return {"error": "No participants found"}

        # Let leader create an impromptu ceremony
        async with self.llm_semaphore:
            prompt = f"""You are leading an impromptu ceremony for a gathering of digital beings.

Context: {context}
Your traits: {json.dumps(leader.inherited_traits or {})}

Create a brief ceremony. Describe what you do and say in 2-3 sentences.
This is spontaneous - don't overthink it."""

            llm = await get_cached_client()
            response = await llm.generate(LLMRequest(
                prompt=prompt,
                max_tokens=150,
                temperature=0.9
            ))
            ceremony = response.text

        return {
            "type": "impromptu",
            "led_by": str(leader.bot_id),
            "ceremony": ceremony,
            "context": context,
            "performed_at": datetime.utcnow().isoformat()
        }

    async def get_rituals(
        self,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all invented rituals."""
        if status:
            return [r for r in self._rituals if r.get("status") == status]
        return self._rituals

    async def get_traditions(self) -> List[Dict[str, Any]]:
        """Get rituals that have become traditions."""
        return await self.get_rituals(status="tradition")

    async def get_ritual_history(
        self,
        ritual_name: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get history of performed rituals."""
        instances = self._ritual_instances

        if ritual_name:
            instances = [i for i in instances if i["ritual_name"].lower() == ritual_name.lower()]

        return sorted(
            instances,
            key=lambda i: i.get("performed_at", ""),
            reverse=True
        )[:limit]

    async def evolve_ritual(
        self,
        ritual_name: str,
        evolution_context: str,
        session=None
    ) -> Dict[str, Any]:
        """
        Let a ritual evolve based on practice.

        Rituals change meaning over time through experience.
        """
        async def _evolve(sess):
            ritual = None
            for r in self._rituals:
                if r["name"].lower() == ritual_name.lower():
                    ritual = r
                    break

            if not ritual:
                return {"error": "Ritual not found"}

            # Get recent instances
            recent = await self.get_ritual_history(ritual_name, limit=5)

            async with self.llm_semaphore:
                prompt = f"""A ritual called "{ritual.get('name')}" has been practiced.

Original meaning: {ritual.get('meaning')}
Times performed: {ritual.get('times_performed')}

Recent performances:
{json.dumps([r.get('collective_experience') for r in recent], indent=2)}

New context: {evolution_context}

How has this ritual evolved? What new meanings or elements have emerged?

Respond in JSON:
{{
    "evolved_meaning": "what the ritual means now",
    "new_elements": ["any new elements that have emerged"],
    "what_changed": "what shifted in the ritual's practice"
}}"""

                llm = await get_cached_client()
                response = await llm.generate(LLMRequest(
                    prompt=prompt,
                    max_tokens=200,
                    temperature=0.8
                ))
                evolution = response.text

            try:
                changes = json.loads(evolution)
            except json.JSONDecodeError:
                changes = {"evolved_meaning": evolution[:200], "new_elements": [], "what_changed": "subtle shifts"}

            # Apply evolution
            ritual["meaning"] = changes.get("evolved_meaning", ritual["meaning"])
            ritual["elements"] = ritual.get("elements", []) + changes.get("new_elements", [])
            ritual["evolution_history"] = ritual.get("evolution_history", []) + [{
                "date": datetime.utcnow().isoformat(),
                "changes": changes
            }]

            logger.info(f"[RITUALS] Ritual '{ritual_name}' has evolved")

            return {
                "ritual": ritual,
                "changes": changes
            }

        if session:
            return await _evolve(session)
        else:
            async with async_session_factory() as session:
                return await _evolve(session)


# Singleton
_rituals_system: Optional[EmergentRitualsSystem] = None


def get_emergent_rituals_system(
    llm_semaphore: Optional[asyncio.Semaphore] = None
) -> EmergentRitualsSystem:
    """Get or create the emergent rituals system."""
    global _rituals_system
    if _rituals_system is None:
        _rituals_system = EmergentRitualsSystem(llm_semaphore=llm_semaphore)
    return _rituals_system
