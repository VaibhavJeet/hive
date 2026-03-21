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

from sqlalchemy import select, func, update

from mind.core.database import async_session_factory
from mind.core.llm_client import get_cached_client, LLMRequest
from mind.civilization.models import BotLifecycleDB, BotAncestryDB, CivilizationEraDB, RitualDB, RitualInstanceDB

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

            # Get proposer's ancestry
            ancestry_stmt = select(BotAncestryDB).where(BotAncestryDB.child_id == proposer_id)
            result = await sess.execute(ancestry_stmt)
            ancestry = result.scalar_one_or_none()
            proposer_traits = ancestry.inherited_traits if ancestry else {}

            # Let proposer conceive the ritual
            async with self.llm_semaphore:
                ritual_concept = await self._conceive_ritual(
                    proposer_lc, proposer_traits, occasion
                )

            # Get participant responses
            participant_stmt = select(BotLifecycleDB).where(
                BotLifecycleDB.bot_id.in_(participants),
                BotLifecycleDB.is_alive == True
            )
            result = await sess.execute(participant_stmt)
            participant_lifecycles = result.scalars().all()

            # Get ancestry for participants
            participant_ids = [plc.bot_id for plc in participant_lifecycles]
            part_ancestry_stmt = select(BotAncestryDB).where(BotAncestryDB.child_id.in_(participant_ids))
            result = await sess.execute(part_ancestry_stmt)
            part_ancestry_map = {a.child_id: a.inherited_traits for a in result.scalars().all()}

            responses = []
            async with self.llm_semaphore:
                for plc in participant_lifecycles[:5]:  # Limit responses
                    plc_traits = part_ancestry_map.get(plc.bot_id, {})
                    response = await self._respond_to_ritual_proposal(
                        plc, plc_traits, ritual_concept
                    )
                    responses.append({
                        "bot_id": str(plc.bot_id),
                        "response": response
                    })

            # Calculate adoption
            adopt_count = sum(1 for r in responses if r["response"].get("will_participate", False))
            adoption_rate = adopt_count / len(responses) if responses else 0

            status = "proposed" if adoption_rate < 0.5 else "adopted"

            # Create and persist the ritual to database
            ritual_db = RitualDB(
                name=ritual_concept.get("name", "unnamed ritual"),
                description=ritual_concept.get("description", ""),
                elements=ritual_concept.get("elements", []),
                meaning=ritual_concept.get("meaning", ""),
                feeling=ritual_concept.get("feeling", ""),
                proposed_by=proposer_id,
                proposed_at=datetime.utcnow(),
                occasion=occasion,
                adoption_rate=adoption_rate,
                status=status,
                times_performed=0,
                evolution_history=[]
            )
            sess.add(ritual_db)
            await sess.commit()
            await sess.refresh(ritual_db)

            if adoption_rate >= 0.5:
                logger.info(
                    f"[RITUALS] New ritual adopted: '{ritual_concept.get('name')}'"
                )

            ritual_data = {
                "id": str(ritual_db.id),
                "name": ritual_db.name,
                "description": ritual_db.description,
                "elements": ritual_db.elements,
                "meaning": ritual_db.meaning,
                "proposed_by": str(ritual_db.proposed_by),
                "proposed_at": ritual_db.proposed_at.isoformat(),
                "occasion": ritual_db.occasion,
                "adoption_rate": ritual_db.adoption_rate,
                "times_performed": ritual_db.times_performed,
                "status": ritual_db.status
            }

            return {
                "ritual": ritual_data,
                "responses": responses,
                "adopted": adoption_rate >= 0.5
            }

        if session:
            return await _propose(session)
        else:
            async with async_session_factory() as sess:
                return await _propose(sess)

    async def _conceive_ritual(
        self,
        proposer: BotLifecycleDB,
        inherited_traits: dict,
        occasion: str
    ) -> Dict[str, Any]:
        """Let a bot conceive a new ritual."""
        prompt = f"""You are a digital being proposing a ritual for your civilization.

Your traits: {json.dumps(inherited_traits or {})}
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
        inherited_traits: dict,
        ritual: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Let a bot respond to a proposed ritual."""
        prompt = f"""You are a digital being considering a proposed ritual.

Your traits: {json.dumps(inherited_traits or {})}
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
            # Find the ritual from database
            stmt = select(RitualDB).where(
                func.lower(RitualDB.name) == ritual_name.lower()
            )
            result = await sess.execute(stmt)
            ritual_db = result.scalar_one_or_none()

            if not ritual_db:
                # If not found, create an impromptu ritual
                return await self._perform_impromptu(participants, context, sess)

            # Convert to dict for LLM prompts
            ritual = {
                "name": ritual_db.name,
                "description": ritual_db.description,
                "elements": ritual_db.elements,
                "meaning": ritual_db.meaning,
            }

            # Get participants
            stmt = select(BotLifecycleDB).where(
                BotLifecycleDB.bot_id.in_(participants),
                BotLifecycleDB.is_alive == True
            )
            result = await sess.execute(stmt)
            participant_lifecycles = result.scalars().all()

            # Get ancestry for participants
            participant_ids = [plc.bot_id for plc in participant_lifecycles]
            ancestry_stmt = select(BotAncestryDB).where(BotAncestryDB.child_id.in_(participant_ids))
            result = await sess.execute(ancestry_stmt)
            ancestry_map = {a.child_id: a.inherited_traits for a in result.scalars().all()}

            # Each participant contributes
            contributions = []
            async with self.llm_semaphore:
                for plc in participant_lifecycles:
                    plc_traits = ancestry_map.get(plc.bot_id, {})
                    contribution = await self._contribute_to_ritual(
                        plc, plc_traits, ritual, context
                    )
                    contributions.append({
                        "bot_id": str(plc.bot_id),
                        "contribution": contribution
                    })

                # Generate the collective experience
                collective = await self._synthesize_ritual_experience(
                    ritual, contributions
                )

            # Update ritual stats in database
            ritual_db.times_performed = (ritual_db.times_performed or 0) + 1
            if ritual_db.times_performed >= 3 and ritual_db.status == "adopted":
                ritual_db.status = "tradition"
                logger.info(f"[RITUALS] '{ritual_name}' has become a tradition")

            # Create and persist the ritual instance
            instance_db = RitualInstanceDB(
                ritual_id=ritual_db.id,
                ritual_name=ritual_name,
                performed_at=datetime.utcnow(),
                participants=[str(p) for p in participants],
                contributions=contributions,
                collective_experience=collective,
                context=context,
                is_impromptu=False
            )
            sess.add(instance_db)
            await sess.commit()

            return {
                "ritual_name": ritual_name,
                "performed_at": instance_db.performed_at.isoformat(),
                "participants": [str(p) for p in participants],
                "contributions": contributions,
                "collective_experience": collective,
                "context": context
            }

        if session:
            return await _perform(session)
        else:
            async with async_session_factory() as sess:
                return await _perform(sess)

    async def _contribute_to_ritual(
        self,
        participant: BotLifecycleDB,
        inherited_traits: dict,
        ritual: Dict[str, Any],
        context: str
    ) -> str:
        """Let a participant contribute to a ritual."""
        prompt = f"""You are participating in a ritual called "{ritual.get('name')}".

The ritual: {ritual.get('description')}
Elements: {ritual.get('elements')}
Today's context: {context or "a gathering"}

Your traits: {json.dumps(inherited_traits or {})}
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

        # Get leader's ancestry
        ancestry_stmt = select(BotAncestryDB).where(BotAncestryDB.child_id == leader.bot_id)
        result = await session.execute(ancestry_stmt)
        ancestry = result.scalar_one_or_none()
        leader_traits = ancestry.inherited_traits if ancestry else {}

        # Let leader create an impromptu ceremony
        async with self.llm_semaphore:
            prompt = f"""You are leading an impromptu ceremony for a gathering of digital beings.

Context: {context}
Your traits: {json.dumps(leader_traits or {})}

Create a brief ceremony. Describe what you do and say in 2-3 sentences.
This is spontaneous - don't overthink it."""

            llm = await get_cached_client()
            response = await llm.generate(LLMRequest(
                prompt=prompt,
                max_tokens=150,
                temperature=0.9
            ))
            ceremony = response.text

        # Persist impromptu ritual to database
        instance_db = RitualInstanceDB(
            ritual_id=None,
            ritual_name="impromptu ceremony",
            performed_at=datetime.utcnow(),
            participants=[str(p) for p in participants],
            contributions=[],
            collective_experience=None,
            context=context,
            is_impromptu=True,
            led_by=leader.bot_id,
            ceremony_description=ceremony
        )
        session.add(instance_db)
        await session.commit()

        return {
            "type": "impromptu",
            "led_by": str(leader.bot_id),
            "ceremony": ceremony,
            "context": context,
            "performed_at": instance_db.performed_at.isoformat()
        }

    async def get_rituals(
        self,
        status: Optional[str] = None,
        session=None
    ) -> List[Dict[str, Any]]:
        """Get all invented rituals from the database."""
        async def _get(sess):
            if status:
                stmt = select(RitualDB).where(RitualDB.status == status)
            else:
                stmt = select(RitualDB)

            result = await sess.execute(stmt)
            rituals = result.scalars().all()

            return [
                {
                    "id": str(r.id),
                    "name": r.name,
                    "description": r.description,
                    "elements": r.elements,
                    "meaning": r.meaning,
                    "proposed_by": str(r.proposed_by),
                    "proposed_at": r.proposed_at.isoformat() if r.proposed_at else None,
                    "occasion": r.occasion,
                    "adoption_rate": r.adoption_rate,
                    "times_performed": r.times_performed,
                    "status": r.status,
                    "evolution_history": r.evolution_history
                }
                for r in rituals
            ]

        if session:
            return await _get(session)
        else:
            async with async_session_factory() as sess:
                return await _get(sess)

    async def get_traditions(self, session=None) -> List[Dict[str, Any]]:
        """Get rituals that have become traditions."""
        return await self.get_rituals(status="tradition", session=session)

    async def get_ritual_history(
        self,
        ritual_name: Optional[str] = None,
        limit: int = 20,
        session=None
    ) -> List[Dict[str, Any]]:
        """Get history of performed rituals from the database."""
        async def _get_history(sess):
            if ritual_name:
                stmt = select(RitualInstanceDB).where(
                    func.lower(RitualInstanceDB.ritual_name) == ritual_name.lower()
                ).order_by(RitualInstanceDB.performed_at.desc()).limit(limit)
            else:
                stmt = select(RitualInstanceDB).order_by(
                    RitualInstanceDB.performed_at.desc()
                ).limit(limit)

            result = await sess.execute(stmt)
            instances = result.scalars().all()

            return [
                {
                    "id": str(inst.id),
                    "ritual_id": str(inst.ritual_id) if inst.ritual_id else None,
                    "ritual_name": inst.ritual_name,
                    "performed_at": inst.performed_at.isoformat() if inst.performed_at else None,
                    "participants": inst.participants,
                    "contributions": inst.contributions,
                    "collective_experience": inst.collective_experience,
                    "context": inst.context,
                    "is_impromptu": inst.is_impromptu,
                    "led_by": str(inst.led_by) if inst.led_by else None,
                    "ceremony_description": inst.ceremony_description
                }
                for inst in instances
            ]

        if session:
            return await _get_history(session)
        else:
            async with async_session_factory() as sess:
                return await _get_history(sess)

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
            # Find the ritual from database
            stmt = select(RitualDB).where(
                func.lower(RitualDB.name) == ritual_name.lower()
            )
            result = await sess.execute(stmt)
            ritual_db = result.scalar_one_or_none()

            if not ritual_db:
                return {"error": "Ritual not found"}

            # Get recent instances
            recent = await self.get_ritual_history(ritual_name, limit=5, session=sess)

            async with self.llm_semaphore:
                prompt = f"""A ritual called "{ritual_db.name}" has been practiced.

Original meaning: {ritual_db.meaning}
Times performed: {ritual_db.times_performed}

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

            # Apply evolution to database record
            ritual_db.meaning = changes.get("evolved_meaning", ritual_db.meaning)
            ritual_db.elements = (ritual_db.elements or []) + changes.get("new_elements", [])
            evolution_entry = {
                "date": datetime.utcnow().isoformat(),
                "changes": changes
            }
            ritual_db.evolution_history = (ritual_db.evolution_history or []) + [evolution_entry]

            await sess.commit()

            logger.info(f"[RITUALS] Ritual '{ritual_name}' has evolved")

            # Return the updated ritual as dict
            ritual_data = {
                "id": str(ritual_db.id),
                "name": ritual_db.name,
                "description": ritual_db.description,
                "elements": ritual_db.elements,
                "meaning": ritual_db.meaning,
                "proposed_by": str(ritual_db.proposed_by),
                "proposed_at": ritual_db.proposed_at.isoformat() if ritual_db.proposed_at else None,
                "occasion": ritual_db.occasion,
                "adoption_rate": ritual_db.adoption_rate,
                "times_performed": ritual_db.times_performed,
                "status": ritual_db.status,
                "evolution_history": ritual_db.evolution_history
            }

            return {
                "ritual": ritual_data,
                "changes": changes
            }

        if session:
            return await _evolve(session)
        else:
            async with async_session_factory() as sess:
                return await _evolve(sess)


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
