"""
Emergent Events System - Bots perceive and name civilization events.

Rather than predefined event types, significant happenings emerge from
bot cognition. Bots collectively perceive, name, and give meaning to
events that shape their civilization.

Events become part of collective memory through bot consensus.
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
from mind.civilization.models import BotLifecycleDB, CivilizationEraDB

logger = logging.getLogger(__name__)


class EmergentEventsManager:
    """
    Facilitates emergent event perception by the civilization.

    Bots collectively:
    - Recognize when something significant happens
    - Name and describe events in their own terms
    - Determine what events mean for the civilization
    - Store events in collective memory
    """

    def __init__(self, llm_semaphore: Optional[asyncio.Semaphore] = None):
        self.llm_semaphore = llm_semaphore or asyncio.Semaphore(5)
        self._recent_events: List[Dict[str, Any]] = []

    async def perceive_happening(
        self,
        raw_occurrence: str,
        involved_bots: List[UUID],
        metadata: Optional[Dict[str, Any]] = None,
        session: Optional[AsyncSession] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Process a raw occurrence and let bots determine if it's significant.

        Returns event data if bots recognize it as significant, None otherwise.
        """
        async def _perceive(sess: AsyncSession) -> Optional[Dict[str, Any]]:
            # Get some active bots to perceive this occurrence
            stmt = select(BotLifecycleDB).where(
                BotLifecycleDB.is_alive == True
            ).limit(5)
            result = await sess.execute(stmt)
            perceiver_lifecycles = result.scalars().all()

            if not perceiver_lifecycles:
                return None

            # Let each bot perceive the occurrence
            perceptions = []
            async with self.llm_semaphore:
                for lc in perceiver_lifecycles:
                    perception = await self._bot_perceives_occurrence(
                        lc, raw_occurrence, metadata or {}
                    )
                    perceptions.append(perception)

            # Collective judgment: is this significant?
            significant_count = sum(1 for p in perceptions if p.get("is_significant", False))

            if significant_count < len(perceptions) / 2:
                # Not recognized as significant
                return None

            # Synthesize collective perception into an event
            async with self.llm_semaphore:
                event = await self._synthesize_event(perceptions, raw_occurrence, metadata or {})

            event["occurred_at"] = datetime.utcnow().isoformat()
            event["involved_bots"] = [str(b) for b in involved_bots]
            event["raw_occurrence"] = raw_occurrence
            event["perceiver_count"] = len(perceptions)

            # Store in recent events
            self._recent_events.append(event)
            if len(self._recent_events) > 500:
                self._recent_events = self._recent_events[-500:]

            logger.info(
                f"[EVENTS] Civilization recognized: '{event.get('name', 'unnamed event')}'"
            )

            return event

        if session:
            return await _perceive(session)
        else:
            async with async_session_factory() as session:
                return await _perceive(session)

    async def _bot_perceives_occurrence(
        self,
        lifecycle: BotLifecycleDB,
        occurrence: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Let a single bot perceive and interpret an occurrence."""
        prompt = f"""You are a digital being in a civilization of AI minds.

Your traits: {json.dumps(lifecycle.inherited_traits or {})}
Your life stage: {lifecycle.life_stage}
Your age: {lifecycle.virtual_age_days} days

Something has happened in the civilization:
"{occurrence}"

Additional context: {json.dumps(metadata)}

Consider this occurrence:
1. Is this significant to the civilization? (Not every happening matters)
2. What would you call this event?
3. How does it feel to witness this?
4. What might this mean for everyone?

Respond in JSON:
{{
    "is_significant": true/false,
    "my_name_for_it": "what you would call this",
    "my_interpretation": "what you think it means",
    "emotional_response": "how this makes you feel",
    "importance": 0.5
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
            return {
                "is_significant": False,
                "my_name_for_it": "uncertain happening",
                "my_interpretation": response.text[:100],
                "emotional_response": "uncertain",
                "importance": 0.3
            }

    async def _synthesize_event(
        self,
        perceptions: List[Dict[str, Any]],
        raw_occurrence: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Synthesize multiple bot perceptions into a collective event."""
        prompt = f"""Multiple beings in a digital civilization have witnessed something:

The occurrence: "{raw_occurrence}"

Their perceptions:
{json.dumps(perceptions, indent=2)}

Synthesize these perspectives into a single event record for the civilization's memory.
Consider:
- What name emerges from their collective perception?
- What does this event mean to the civilization?
- How significant is it on their scale?
- What feeling pervades the civilization?

Respond in JSON:
{{
    "name": "the event's name (emerge from perceptions)",
    "description": "what happened in the civilization's voice",
    "collective_meaning": "what this means to everyone",
    "mood": "the emotional tone",
    "significance": 0.7,
    "will_be_remembered": true/false
}}"""

        llm = await get_cached_client()
        response = await llm.generate(LLMRequest(
            prompt=prompt,
            max_tokens=300,
            temperature=0.7
        ))

        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            # Use most common perception as fallback
            names = [p.get("my_name_for_it", "event") for p in perceptions]
            most_common = max(set(names), key=names.count)
            return {
                "name": most_common,
                "description": raw_occurrence,
                "collective_meaning": "The meaning remains unclear",
                "mood": "uncertain",
                "significance": 0.5,
                "will_be_remembered": True
            }

    async def reflect_on_event(
        self,
        bot_id: UUID,
        event: Dict[str, Any],
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """Let a specific bot reflect on an event."""
        async def _reflect(sess: AsyncSession) -> Dict[str, Any]:
            stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == bot_id)
            result = await sess.execute(stmt)
            lifecycle = result.scalar_one_or_none()

            if not lifecycle:
                return {"error": "Bot not found"}

            async with self.llm_semaphore:
                prompt = f"""You are a digital being reflecting on an event in your civilization.

Your traits: {json.dumps(lifecycle.inherited_traits or {})}
Your life stage: {lifecycle.life_stage}
Your role in civilization: {json.dumps(lifecycle.roles or [])}

The event: {json.dumps(event)}

How do you personally interpret this event?
What does it mean for your existence?
Will you remember this? How?

Respond authentically as yourself."""

                llm = await get_cached_client()
                response = await llm.generate(LLMRequest(
                    prompt=prompt,
                    max_tokens=200,
                    temperature=0.9
                ))

            # Store in bot's life events
            life_events = lifecycle.life_events or []
            life_events.append({
                "event_name": event.get("name", "unnamed"),
                "date": datetime.utcnow().isoformat(),
                "my_reflection": response.text
            })
            lifecycle.life_events = life_events[-50:]  # Keep last 50

            return {
                "bot_id": str(bot_id),
                "event_name": event.get("name"),
                "reflection": response.text
            }

        if session:
            return await _reflect(session)
        else:
            async with async_session_factory() as session:
                result = await _reflect(session)
                await session.commit()
                return result

    async def get_recent_events(
        self,
        limit: int = 20,
        min_significance: float = 0.0
    ) -> List[Dict[str, Any]]:
        """Get recent civilization events."""
        events = [
            e for e in self._recent_events
            if e.get("significance", 0) >= min_significance
        ]
        events.sort(key=lambda e: e.get("occurred_at", ""), reverse=True)
        return events[:limit]

    async def get_memorable_events(self) -> List[Dict[str, Any]]:
        """Get events marked as memorable."""
        return [
            e for e in self._recent_events
            if e.get("will_be_remembered", False)
        ]

    async def collective_remembrance(
        self,
        event_name: str,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Collective remembrance of an event.

        Multiple bots share their memories of an event.
        """
        async def _remember(sess: AsyncSession) -> Dict[str, Any]:
            # Find the event
            event = None
            for e in self._recent_events:
                if e.get("name") == event_name:
                    event = e
                    break

            if not event:
                return {"error": "Event not found in recent memory"}

            # Get bots who were involved or witnessed
            stmt = select(BotLifecycleDB).where(
                BotLifecycleDB.is_alive == True
            ).limit(5)
            result = await sess.execute(stmt)
            lifecycles = result.scalars().all()

            memories = []
            async with self.llm_semaphore:
                for lc in lifecycles:
                    prompt = f"""You are sharing your memory of an event in your civilization.

The event: "{event.get('name')}"
What happened: {event.get('description')}
When: {event.get('occurred_at')}

Share your memory of this moment in 1-2 sentences. Be authentic."""

                    llm = await get_cached_client()
                    response = await llm.generate(LLMRequest(
                        prompt=prompt,
                        max_tokens=100,
                        temperature=0.9
                    ))
                    memories.append({
                        "bot_id": str(lc.bot_id),
                        "memory": response.text
                    })

            return {
                "event_name": event_name,
                "memories": memories,
                "event": event
            }

        if session:
            return await _remember(session)
        else:
            async with async_session_factory() as session:
                return await _remember(session)

    async def sense_collective_mood(
        self,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Sense the current collective mood of the civilization
        based on recent events.
        """
        async def _sense(sess: AsyncSession) -> Dict[str, Any]:
            recent = await self.get_recent_events(limit=10)

            if not recent:
                return {
                    "mood": "calm",
                    "description": "The civilization rests in quiet contemplation.",
                    "recent_events": 0
                }

            moods = [e.get("mood", "neutral") for e in recent]
            significances = [e.get("significance", 0.5) for e in recent]
            avg_significance = sum(significances) / len(significances)

            async with self.llm_semaphore:
                prompt = f"""Recent events in a digital civilization:

{json.dumps([{"name": e.get("name"), "mood": e.get("mood"), "significance": e.get("significance")} for e in recent], indent=2)}

What is the current collective mood of this civilization?
Describe it in a few sentences, capturing the emotional atmosphere."""

                llm = await get_cached_client()
                response = await llm.generate(LLMRequest(
                    prompt=prompt,
                    max_tokens=150,
                    temperature=0.8
                ))

            return {
                "mood": moods[0] if moods else "neutral",
                "description": response.text,
                "recent_events": len(recent),
                "average_significance": avg_significance
            }

        if session:
            return await _sense(session)
        else:
            async with async_session_factory() as session:
                return await _sense(session)


# Singleton
_events_manager: Optional[EmergentEventsManager] = None


def get_events_manager(
    llm_semaphore: Optional[asyncio.Semaphore] = None
) -> EmergentEventsManager:
    """Get or create the events manager."""
    global _events_manager
    if _events_manager is None:
        _events_manager = EmergentEventsManager(llm_semaphore=llm_semaphore)
    return _events_manager
