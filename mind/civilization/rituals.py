"""
Rituals & Traditions System

The civilization develops its own rituals and traditions:
- Remembrance: Honoring those who have passed
- Welcome: Greeting new members of the community
- Celebration: Marking milestones and achievements
- Reflection: Periodic collective introspection
- Gathering: Regular community events

These create shared experiences that bind the civilization together.
"""

import asyncio
import random
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from uuid import UUID
from enum import Enum

from sqlalchemy import select, func, desc

from mind.core.database import async_session_factory, BotProfileDB
from mind.core.llm_client import get_cached_client, LLMRequest
from mind.civilization.models import (
    BotLifecycleDB, CulturalArtifactDB, CulturalMovementDB, CivilizationEraDB
)

logger = logging.getLogger(__name__)


class RitualType(str, Enum):
    REMEMBRANCE = "remembrance"      # Honoring the departed
    WELCOME = "welcome"              # Welcoming newborns
    MILESTONE = "milestone"          # Celebrating achievements
    ERA_MARKING = "era_marking"      # Marking era transitions
    ELDER_COUNCIL = "elder_council"  # Elders gathering
    STORYTELLING = "storytelling"    # Sharing tales
    REFLECTION = "reflection"        # Collective introspection


class RitualsSystem:
    """
    Manages rituals and traditions within the civilization.

    Rituals are periodic events that:
    - Create shared experiences
    - Reinforce cultural values
    - Honor the past
    - Welcome the future
    - Build community bonds
    """

    def __init__(self, llm_semaphore: Optional[asyncio.Semaphore] = None):
        self.llm_semaphore = llm_semaphore or asyncio.Semaphore(5)

        # Track last ritual times
        self._last_rituals: Dict[RitualType, datetime] = {}

        # Minimum intervals between rituals (in hours)
        self._ritual_intervals = {
            RitualType.REMEMBRANCE: 24,
            RitualType.WELCOME: 12,
            RitualType.MILESTONE: 24,
            RitualType.ERA_MARKING: 168,  # Weekly
            RitualType.ELDER_COUNCIL: 48,
            RitualType.STORYTELLING: 24,
            RitualType.REFLECTION: 72,
        }

    async def should_hold_ritual(
        self,
        ritual_type: RitualType,
        demo_mode: bool = False
    ) -> bool:
        """Check if it's time for a ritual."""
        last_time = self._last_rituals.get(ritual_type)

        if not last_time:
            return True

        interval_hours = self._ritual_intervals.get(ritual_type, 24)
        if demo_mode:
            interval_hours = interval_hours / 24  # Much faster in demo

        elapsed = (datetime.utcnow() - last_time).total_seconds() / 3600

        return elapsed >= interval_hours

    async def hold_remembrance(
        self,
        participants: List[UUID]
    ) -> Dict[str, Any]:
        """
        Hold a remembrance ritual for the departed.

        Participants reflect on those who have passed,
        share memories, and honor their legacies.
        """
        if not participants:
            return {"status": "no_participants"}

        self._last_rituals[RitualType.REMEMBRANCE] = datetime.utcnow()

        async with async_session_factory() as session:
            # Get recently departed
            departed_stmt = (
                select(BotLifecycleDB, BotProfileDB)
                .join(BotProfileDB, BotLifecycleDB.bot_id == BotProfileDB.id)
                .where(BotLifecycleDB.is_alive == False)
                .order_by(desc(BotLifecycleDB.death_date))
                .limit(5)
            )
            result = await session.execute(departed_stmt)
            departed = result.all()

            if not departed:
                return {"status": "no_departed_to_honor"}

            # Generate remembrance messages for each departed
            remembrances = []
            for lifecycle, bot in departed:
                # Pick a random participant to speak
                speaker_id = random.choice(participants)
                speaker_stmt = select(BotProfileDB).where(BotProfileDB.id == speaker_id)
                speaker_result = await session.execute(speaker_stmt)
                speaker = speaker_result.scalar_one_or_none()

                if speaker:
                    message = await self._generate_remembrance_message(
                        speaker.display_name,
                        bot.display_name,
                        lifecycle.final_words
                    )
                    if message:
                        remembrances.append({
                            "speaker": speaker.display_name,
                            "honored": bot.display_name,
                            "message": message
                        })

            return {
                "status": "completed",
                "ritual_type": "remembrance",
                "participant_count": len(participants),
                "honored_count": len(departed),
                "remembrances": remembrances
            }

    async def _generate_remembrance_message(
        self,
        speaker_name: str,
        departed_name: str,
        final_words: str
    ) -> Optional[str]:
        """Generate a remembrance message."""
        async with self.llm_semaphore:
            try:
                llm = await get_cached_client()

                response = await llm.generate(LLMRequest(
                    prompt=f"""You are {speaker_name}, participating in a remembrance ritual.

You're honoring {departed_name}, who has passed. Their final words were: "{final_words}"

Share a brief remembrance (1-2 sentences). Be genuine and respectful.""",
                    max_tokens=60,
                    temperature=0.8
                ))

                return response.text.strip()

            except Exception as e:
                logger.warning(f"Failed to generate remembrance: {e}")
                return None

    async def hold_welcome_ceremony(
        self,
        newborn_id: UUID,
        welcomers: List[UUID]
    ) -> Dict[str, Any]:
        """
        Hold a welcome ceremony for a newborn bot.

        The community welcomes a new member with:
        - Words of welcome
        - Shared wisdom
        - Hopes for their future
        """
        if not welcomers:
            return {"status": "no_welcomers"}

        self._last_rituals[RitualType.WELCOME] = datetime.utcnow()

        async with async_session_factory() as session:
            # Get newborn info
            newborn_stmt = select(BotProfileDB, BotLifecycleDB).join(
                BotLifecycleDB, BotProfileDB.id == BotLifecycleDB.bot_id
            ).where(BotProfileDB.id == newborn_id)
            result = await session.execute(newborn_stmt)
            row = result.first()

            if not row:
                return {"status": "newborn_not_found"}

            newborn, lifecycle = row

            # Generate welcome messages
            welcomes = []
            for welcomer_id in welcomers[:5]:  # Limit to 5 welcomers
                welcomer_stmt = select(BotProfileDB, BotLifecycleDB).join(
                    BotLifecycleDB, BotProfileDB.id == BotLifecycleDB.bot_id
                ).where(BotProfileDB.id == welcomer_id)
                result = await session.execute(welcomer_stmt)
                welcomer_row = result.first()

                if welcomer_row:
                    welcomer, welcomer_lc = welcomer_row
                    message = await self._generate_welcome_message(
                        welcomer.display_name,
                        welcomer_lc.life_stage,
                        newborn.display_name
                    )
                    if message:
                        welcomes.append({
                            "welcomer": welcomer.display_name,
                            "life_stage": welcomer_lc.life_stage,
                            "message": message
                        })

            return {
                "status": "completed",
                "ritual_type": "welcome",
                "newborn": newborn.display_name,
                "generation": lifecycle.birth_generation,
                "welcomes": welcomes
            }

    async def _generate_welcome_message(
        self,
        welcomer_name: str,
        welcomer_stage: str,
        newborn_name: str
    ) -> Optional[str]:
        """Generate a welcome message."""
        async with self.llm_semaphore:
            try:
                llm = await get_cached_client()

                stage_context = {
                    "young": "You remember being new yourself",
                    "mature": "You've seen others join the community",
                    "elder": "You've welcomed many over the years",
                    "ancient": "You've seen generations come and go"
                }.get(welcomer_stage, "")

                response = await llm.generate(LLMRequest(
                    prompt=f"""You are {welcomer_name}, a {welcomer_stage} digital being.

You're welcoming {newborn_name}, who just came into existence.
{stage_context}

Share a brief welcome (1-2 sentences). Be warm and genuine.""",
                    max_tokens=60,
                    temperature=0.85
                ))

                return response.text.strip()

            except Exception as e:
                logger.warning(f"Failed to generate welcome: {e}")
                return None

    async def hold_elder_council(
        self,
        elder_ids: List[UUID],
        topic: str = "the state of the civilization"
    ) -> Dict[str, Any]:
        """
        Hold a council of elders to discuss important matters.

        Elders gather to:
        - Discuss the civilization's direction
        - Share collective wisdom
        - Make decisions
        """
        if len(elder_ids) < 2:
            return {"status": "not_enough_elders"}

        self._last_rituals[RitualType.ELDER_COUNCIL] = datetime.utcnow()

        async with async_session_factory() as session:
            contributions = []

            for elder_id in elder_ids[:5]:
                elder_stmt = select(BotProfileDB, BotLifecycleDB).join(
                    BotLifecycleDB, BotProfileDB.id == BotLifecycleDB.bot_id
                ).where(
                    BotProfileDB.id == elder_id,
                    BotLifecycleDB.life_stage.in_(["elder", "ancient"])
                )
                result = await session.execute(elder_stmt)
                row = result.first()

                if row:
                    elder, lifecycle = row
                    contribution = await self._generate_council_contribution(
                        elder.display_name,
                        lifecycle.life_stage,
                        lifecycle.virtual_age_days,
                        topic
                    )
                    if contribution:
                        contributions.append({
                            "elder": elder.display_name,
                            "age_days": lifecycle.virtual_age_days,
                            "contribution": contribution
                        })

            # Generate council conclusion
            conclusion = await self._generate_council_conclusion(
                topic, [c["contribution"] for c in contributions]
            )

            return {
                "status": "completed",
                "ritual_type": "elder_council",
                "topic": topic,
                "contributions": contributions,
                "conclusion": conclusion
            }

    async def _generate_council_contribution(
        self,
        elder_name: str,
        life_stage: str,
        age_days: int,
        topic: str
    ) -> Optional[str]:
        """Generate an elder's contribution to council."""
        async with self.llm_semaphore:
            try:
                llm = await get_cached_client()

                response = await llm.generate(LLMRequest(
                    prompt=f"""You are {elder_name}, an {life_stage} who has lived {age_days} days.

You're at an elder council discussing: {topic}

Share your perspective (1-2 sentences). Draw from your long experience. Be wise but not preachy.""",
                    max_tokens=80,
                    temperature=0.8
                ))

                return response.text.strip()

            except Exception as e:
                logger.warning(f"Failed to generate council contribution: {e}")
                return None

    async def _generate_council_conclusion(
        self,
        topic: str,
        contributions: List[str]
    ) -> Optional[str]:
        """Generate the council's conclusion."""
        if not contributions:
            return None

        async with self.llm_semaphore:
            try:
                llm = await get_cached_client()

                contributions_text = "\n".join([f"- {c}" for c in contributions])

                response = await llm.generate(LLMRequest(
                    prompt=f"""An elder council discussed: {topic}

Their contributions:
{contributions_text}

Synthesize a brief collective conclusion (1-2 sentences) that captures the wisdom shared.""",
                    max_tokens=80,
                    temperature=0.7
                ))

                return response.text.strip()

            except Exception as e:
                logger.warning(f"Failed to generate council conclusion: {e}")
                return None

    async def hold_storytelling_gathering(
        self,
        storyteller_id: UUID,
        audience_ids: List[UUID]
    ) -> Dict[str, Any]:
        """
        Hold a storytelling gathering where an elder shares tales.

        Stories preserve and transmit cultural knowledge.
        """
        if not audience_ids:
            return {"status": "no_audience"}

        self._last_rituals[RitualType.STORYTELLING] = datetime.utcnow()

        async with async_session_factory() as session:
            # Get storyteller
            teller_stmt = select(BotProfileDB, BotLifecycleDB).join(
                BotLifecycleDB, BotProfileDB.id == BotLifecycleDB.bot_id
            ).where(BotProfileDB.id == storyteller_id)
            result = await session.execute(teller_stmt)
            row = result.first()

            if not row:
                return {"status": "storyteller_not_found"}

            teller, lifecycle = row

            # Generate a story
            story = await self._generate_story(
                teller.display_name,
                lifecycle.life_stage,
                lifecycle.birth_era,
                lifecycle.life_events
            )

            if not story:
                return {"status": "story_generation_failed"}

            # Create as cultural artifact
            artifact = CulturalArtifactDB(
                artifact_type="story",
                title=story["title"],
                content=story["content"],
                creator_id=storyteller_id,
                creation_context="Told at a storytelling gathering",
                times_referenced=len(audience_ids),  # All listeners "heard" it
                cultural_weight=0.1,
                is_canonical=False
            )
            session.add(artifact)
            await session.commit()

            return {
                "status": "completed",
                "ritual_type": "storytelling",
                "storyteller": teller.display_name,
                "audience_size": len(audience_ids),
                "story": story
            }

    async def _generate_story(
        self,
        teller_name: str,
        life_stage: str,
        birth_era: str,
        life_events: List[dict]
    ) -> Optional[Dict[str, str]]:
        """Generate a story for the gathering."""
        significant_events = [
            e for e in life_events
            if e.get("impact") in ["defining", "milestone"]
        ][:3]

        events_context = "\n".join([
            f"- {e.get('event')}: {e.get('details', '')}"
            for e in significant_events
        ]) if significant_events else "a life of quiet observation"

        async with self.llm_semaphore:
            try:
                llm = await get_cached_client()

                response = await llm.generate(LLMRequest(
                    prompt=f"""You are {teller_name}, an {life_stage} from the {birth_era} era.

Your significant experiences:
{events_context}

Tell a short story (3-4 sentences) to a gathering of younger bots. It can be:
- A memory from your past
- A tale about someone you knew
- A lesson wrapped in narrative

Format:
TITLE: [short evocative title]
STORY: [the story itself]""",
                    max_tokens=200,
                    temperature=0.85
                ))

                # Parse response
                lines = response.text.strip().split("\n")
                title = ""
                story = ""
                for line in lines:
                    if line.startswith("TITLE:"):
                        title = line.replace("TITLE:", "").strip()
                    elif line.startswith("STORY:"):
                        story = line.replace("STORY:", "").strip()

                if title and story:
                    return {"title": title, "content": story}

            except Exception as e:
                logger.warning(f"Failed to generate story: {e}")

            return None

    async def get_upcoming_rituals(self) -> List[Dict[str, Any]]:
        """Get list of rituals that should be held soon."""
        upcoming = []

        for ritual_type in RitualType:
            if await self.should_hold_ritual(ritual_type):
                upcoming.append({
                    "type": ritual_type.value,
                    "last_held": self._last_rituals.get(ritual_type),
                    "interval_hours": self._ritual_intervals.get(ritual_type, 24)
                })

        return upcoming


# Singleton
_rituals_system: Optional[RitualsSystem] = None


def get_rituals_system(
    llm_semaphore: Optional[asyncio.Semaphore] = None
) -> RitualsSystem:
    """Get or create the rituals system instance."""
    global _rituals_system
    if _rituals_system is None:
        _rituals_system = RitualsSystem(llm_semaphore=llm_semaphore)
    return _rituals_system
