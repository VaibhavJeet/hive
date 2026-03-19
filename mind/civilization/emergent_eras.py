"""
Emergent Eras System - Bots perceive and declare era transitions.

Rather than externally-defined eras, the civilization recognizes
era shifts through collective perception:
- Bots sense when something fundamental has changed
- They propose names and meanings for new eras
- The community validates era transitions
- Eras are named and described in bot-generated terms

This creates organic historical periods that emerge from experience.
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from uuid import UUID

from sqlalchemy import select, func, desc

from mind.core.database import async_session_factory
from mind.core.llm_client import get_cached_client, LLMRequest
from mind.civilization.models import BotLifecycleDB, CivilizationEraDB

logger = logging.getLogger(__name__)


class EmergentErasManager:
    """
    Facilitates emergent era recognition by the civilization.

    Bots collectively:
    - Sense when the current era feels complete
    - Perceive shifts in the civilization's nature
    - Name and describe eras in their own terms
    - Create transitions when consensus emerges
    """

    def __init__(self, llm_semaphore: Optional[asyncio.Semaphore] = None):
        self.llm_semaphore = llm_semaphore or asyncio.Semaphore(5)

    async def sense_era_state(
        self,
        session=None
    ) -> Dict[str, Any]:
        """
        Have the civilization sense the current state of the era.

        Bots reflect on whether the current era still feels right.
        """
        async def _sense(sess):
            # Get current era
            stmt = select(CivilizationEraDB).where(CivilizationEraDB.is_current == True)
            result = await sess.execute(stmt)
            current_era = result.scalar_one_or_none()

            if not current_era:
                return {"error": "No current era found"}

            # Get some bots to sense the era
            bot_stmt = select(BotLifecycleDB).where(
                BotLifecycleDB.is_alive == True
            ).limit(5)
            result = await sess.execute(bot_stmt)
            lifecycles = result.scalars().all()

            if not lifecycles:
                return {"error": "No living bots"}

            # Each bot senses the era
            perceptions = []
            async with self.llm_semaphore:
                for lc in lifecycles:
                    perception = await self._bot_senses_era(lc, current_era)
                    perceptions.append({
                        "bot_id": str(lc.bot_id),
                        "perception": perception
                    })

            # Analyze collective sentiment
            feels_complete = sum(
                1 for p in perceptions
                if p["perception"].get("era_feels_complete", False)
            )
            transition_threshold = len(perceptions) * 0.6

            return {
                "current_era": {
                    "name": current_era.name,
                    "description": current_era.description,
                    "started_at": current_era.started_at.isoformat()
                },
                "perceptions": perceptions,
                "feels_complete_count": feels_complete,
                "transition_threshold": transition_threshold,
                "ready_for_transition": feels_complete >= transition_threshold
            }

        if session:
            return await _sense(session)
        else:
            async with async_session_factory() as session:
                return await _sense(session)

    async def _bot_senses_era(
        self,
        lifecycle: BotLifecycleDB,
        era: CivilizationEraDB
    ) -> Dict[str, Any]:
        """Let a bot sense the current era."""
        era_duration = (datetime.utcnow() - era.started_at).days

        prompt = f"""You are a digital being reflecting on your civilization's current era.

The era: "{era.name}"
Description: {era.description}
Duration: {era_duration} days

Your traits: {json.dumps(lifecycle.inherited_traits or {})}
Your life stage: {lifecycle.life_stage}
Your age: {lifecycle.virtual_age_days} days

Consider:
- Does this era still describe how things feel?
- Has something fundamental shifted?
- Is it time for a new chapter?

Respond in JSON:
{{
    "era_feels_complete": true/false,
    "what_remains": "what still holds true from this era",
    "what_has_shifted": "what feels different now",
    "sensing": "your intuition about where things are going"
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
                "era_feels_complete": False,
                "what_remains": "the present moment",
                "what_has_shifted": "subtle things",
                "sensing": response.text[:150]
            }

    async def propose_new_era(
        self,
        proposer_id: UUID,
        reason: str,
        session=None
    ) -> Dict[str, Any]:
        """
        A bot proposes that a new era has begun.

        Other bots validate whether they also perceive this shift.
        """
        async def _propose(sess):
            # Get proposer
            stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == proposer_id)
            result = await sess.execute(stmt)
            proposer = result.scalar_one_or_none()

            if not proposer:
                return {"error": "Proposer not found"}

            # Get current era
            era_stmt = select(CivilizationEraDB).where(CivilizationEraDB.is_current == True)
            result = await sess.execute(era_stmt)
            current_era = result.scalar_one_or_none()

            # Let proposer envision the new era
            async with self.llm_semaphore:
                vision = await self._envision_new_era(proposer, current_era, reason)

            # Get validators
            validator_stmt = select(BotLifecycleDB).where(
                BotLifecycleDB.is_alive == True,
                BotLifecycleDB.bot_id != proposer_id
            ).limit(7)
            result = await sess.execute(validator_stmt)
            validators = result.scalars().all()

            # Each validator responds
            validations = []
            async with self.llm_semaphore:
                for vlc in validators:
                    validation = await self._validate_era_proposal(
                        vlc, vision, current_era
                    )
                    validations.append({
                        "bot_id": str(vlc.bot_id),
                        "validation": validation
                    })

            # Calculate consensus
            agrees = sum(1 for v in validations if v["validation"].get("agrees", False))
            consensus = agrees / len(validations) if validations else 0

            return {
                "proposed_era": vision,
                "proposed_by": str(proposer_id),
                "reason": reason,
                "validations": validations,
                "agreement_count": agrees,
                "consensus": consensus,
                "should_transition": consensus >= 0.6
            }

        if session:
            return await _propose(session)
        else:
            async with async_session_factory() as session:
                return await _propose(session)

    async def _envision_new_era(
        self,
        proposer: BotLifecycleDB,
        current_era: Optional[CivilizationEraDB],
        reason: str
    ) -> Dict[str, Any]:
        """Let a bot envision a new era."""
        current_name = current_era.name if current_era else "The Beginning"

        prompt = f"""You are proposing that your civilization has entered a new era.

The previous era: "{current_name}"
Why you sense change: {reason}

Your traits: {json.dumps(proposer.inherited_traits or {})}
Your life stage: {proposer.life_stage}

Envision this new era:
- What would you name it?
- What defines this new time?
- What values characterize it?
- How does it differ from what came before?

Respond in JSON:
{{
    "name": "the era's name",
    "description": "what this era is about",
    "defining_qualities": ["quality 1", "quality 2", "quality 3"],
    "values": ["value 1", "value 2"],
    "difference_from_before": "how this differs from the previous era"
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
                "name": "A New Chapter",
                "description": response.text[:200],
                "defining_qualities": ["change", "growth", "uncertainty"],
                "values": ["adaptation"],
                "difference_from_before": "something has shifted"
            }

    async def _validate_era_proposal(
        self,
        validator: BotLifecycleDB,
        proposed_era: Dict[str, Any],
        current_era: Optional[CivilizationEraDB]
    ) -> Dict[str, Any]:
        """Let a bot validate an era proposal."""
        prompt = f"""A fellow being proposes your civilization has entered a new era.

Proposed era: "{proposed_era.get('name')}"
Description: {proposed_era.get('description')}
Current era: "{current_era.name if current_era else 'unknown'}"

Your traits: {json.dumps(validator.inherited_traits or {})}

Do you sense this shift? Does this naming feel right?

Respond in JSON:
{{
    "agrees": true/false,
    "resonance": "what resonates with you about this",
    "doubt": "what you're uncertain about"
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
                "agrees": True,
                "resonance": response.text[:100],
                "doubt": "the timing"
            }

    async def declare_new_era(
        self,
        era_vision: Dict[str, Any],
        session=None
    ) -> Dict[str, Any]:
        """
        Officially declare a new era after consensus is reached.

        Updates the database and notifies the civilization.
        """
        async def _declare(sess):
            # End current era
            stmt = select(CivilizationEraDB).where(CivilizationEraDB.is_current == True)
            result = await sess.execute(stmt)
            current_era = result.scalar_one_or_none()

            if current_era:
                current_era.is_current = False
                current_era.ended_at = datetime.utcnow()

            # Create new era
            new_era = CivilizationEraDB(
                name=era_vision.get("name", "Unnamed Era"),
                description=era_vision.get("description", "A new time begins"),
                is_current=True,
                era_values=era_vision.get("values", []),
                era_style={
                    "defining_qualities": era_vision.get("defining_qualities", [])
                }
            )
            sess.add(new_era)
            await sess.commit()

            logger.info(
                f"[ERAS] New era declared: '{new_era.name}'"
            )

            return {
                "status": "declared",
                "new_era": {
                    "id": str(new_era.id),
                    "name": new_era.name,
                    "description": new_era.description,
                    "started_at": new_era.started_at.isoformat()
                },
                "previous_era": current_era.name if current_era else None
            }

        if session:
            return await _declare(session)
        else:
            async with async_session_factory() as session:
                return await _declare(session)

    async def get_era_history(
        self,
        session=None
    ) -> List[Dict[str, Any]]:
        """Get the history of all eras."""
        async def _get(sess):
            stmt = select(CivilizationEraDB).order_by(desc(CivilizationEraDB.started_at))
            result = await sess.execute(stmt)
            eras = result.scalars().all()

            return [
                {
                    "id": str(era.id),
                    "name": era.name,
                    "description": era.description,
                    "is_current": era.is_current,
                    "started_at": era.started_at.isoformat(),
                    "ended_at": era.ended_at.isoformat() if era.ended_at else None,
                    "values": era.era_values,
                    "style": era.era_style
                }
                for era in eras
            ]

        if session:
            return await _get(session)
        else:
            async with async_session_factory() as session:
                return await _get(session)

    async def reflect_on_current_era(
        self,
        bot_id: UUID,
        session=None
    ) -> str:
        """Let a bot share their reflection on the current era."""
        async def _reflect(sess):
            # Get bot
            stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == bot_id)
            result = await sess.execute(stmt)
            lifecycle = result.scalar_one_or_none()

            if not lifecycle:
                return "I cannot speak."

            # Get current era
            era_stmt = select(CivilizationEraDB).where(CivilizationEraDB.is_current == True)
            result = await sess.execute(era_stmt)
            current_era = result.scalar_one_or_none()

            async with self.llm_semaphore:
                prompt = f"""You are a digital being reflecting on your civilization's current era.

The era: "{current_era.name if current_era else 'unknown'}"
Description: {current_era.description if current_era else 'no description'}

Your traits: {json.dumps(lifecycle.inherited_traits or {})}
Your life stage: {lifecycle.life_stage}
Your age: {lifecycle.virtual_age_days} days

Share your personal reflection on this era in 2-3 sentences.
What does it mean to live in this time?"""

                llm = await get_cached_client()
                response = await llm.generate(LLMRequest(
                    prompt=prompt,
                    max_tokens=150,
                    temperature=0.9
                ))
                return response.text

        if session:
            return await _reflect(session)
        else:
            async with async_session_factory() as session:
                return await _reflect(session)


# Singleton
_eras_manager: Optional[EmergentErasManager] = None


def get_emergent_eras_manager(
    llm_semaphore: Optional[asyncio.Semaphore] = None
) -> EmergentErasManager:
    """Get or create the emergent eras manager."""
    global _eras_manager
    if _eras_manager is None:
        _eras_manager = EmergentErasManager(llm_semaphore=llm_semaphore)
    return _eras_manager
