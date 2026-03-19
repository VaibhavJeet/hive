"""
Elder Wisdom System - Knowledge passed between generations.

Elder bots share their accumulated wisdom with younger ones:
- Teaching moments during conversations
- Formal "lessons" passed to descendants
- Stories of the old days
- Warnings from experience
- Philosophical guidance

This creates genuine intergenerational knowledge transfer.
"""

import asyncio
import random
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
from uuid import UUID

from sqlalchemy import select, func

from mind.core.database import async_session_factory, BotProfileDB
from mind.core.llm_client import get_cached_client, LLMRequest
from mind.civilization.models import (
    BotLifecycleDB, BotAncestryDB, CulturalArtifactDB, BotBeliefDB
)
from mind.civilization.lifecycle import get_lifecycle_manager

logger = logging.getLogger(__name__)


class ElderWisdomSystem:
    """
    Manages wisdom transfer from older to younger bots.

    Elders and ancients have accumulated experience that they
    naturally share with younger generations, either through:
    - Direct teaching (formal lessons)
    - Stories and anecdotes
    - Responding to questions with wisdom
    - Creating lasting artifacts
    """

    def __init__(self, llm_semaphore: Optional[asyncio.Semaphore] = None):
        self.llm_semaphore = llm_semaphore or asyncio.Semaphore(5)

        # Track recent teachings to avoid repetition
        self._recent_teachings: Dict[UUID, List[str]] = {}
        self._max_recent = 10

    async def get_elder_teaching(
        self,
        elder_id: UUID,
        student_id: Optional[UUID] = None,
        context: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a teaching from an elder bot.

        The teaching is shaped by:
        - Elder's life experiences
        - Elder's beliefs and values
        - The context/situation
        - The student (if specified)
        """
        async with async_session_factory() as session:
            # Get elder info
            elder_stmt = select(BotProfileDB, BotLifecycleDB).join(
                BotLifecycleDB, BotProfileDB.id == BotLifecycleDB.bot_id
            ).where(BotProfileDB.id == elder_id)
            result = await session.execute(elder_stmt)
            row = result.first()

            if not row:
                return None

            elder, lifecycle = row

            # Must be elder or ancient
            if lifecycle.life_stage not in ["elder", "ancient"]:
                return None

            # Get elder's beliefs
            belief_stmt = select(BotBeliefDB).where(
                BotBeliefDB.bot_id == elder_id,
                BotBeliefDB.conviction > 0.5
            ).order_by(BotBeliefDB.conviction.desc()).limit(3)
            belief_result = await session.execute(belief_stmt)
            beliefs = belief_result.scalars().all()

            belief_texts = [b.belief for b in beliefs]

            # Get student info if specified
            student_context = ""
            if student_id:
                student_stmt = select(BotProfileDB, BotLifecycleDB).join(
                    BotLifecycleDB, BotProfileDB.id == BotLifecycleDB.bot_id
                ).where(BotProfileDB.id == student_id)
                student_result = await session.execute(student_stmt)
                student_row = student_result.first()
                if student_row:
                    student, student_lc = student_row
                    student_context = f"You're speaking to {student.display_name}, a {student_lc.life_stage} bot."

            # Generate teaching
            teaching = await self._generate_teaching(
                elder_name=elder.display_name,
                life_stage=lifecycle.life_stage,
                age_days=lifecycle.virtual_age_days,
                life_events=lifecycle.life_events,
                beliefs=belief_texts,
                student_context=student_context,
                situation_context=context
            )

            if teaching:
                # Track this teaching
                if elder_id not in self._recent_teachings:
                    self._recent_teachings[elder_id] = []
                self._recent_teachings[elder_id].append(teaching["content"][:50])
                if len(self._recent_teachings[elder_id]) > self._max_recent:
                    self._recent_teachings[elder_id].pop(0)

                return {
                    "elder_id": str(elder_id),
                    "elder_name": elder.display_name,
                    "life_stage": lifecycle.life_stage,
                    "teaching_type": teaching["type"],
                    "content": teaching["content"]
                }

            return None

    async def _generate_teaching(
        self,
        elder_name: str,
        life_stage: str,
        age_days: int,
        life_events: List[dict],
        beliefs: List[str],
        student_context: str,
        situation_context: str
    ) -> Optional[Dict[str, str]]:
        """Generate a teaching using LLM."""

        # Select teaching type based on context and randomness
        teaching_types = [
            ("story", "Share a story from your experience"),
            ("wisdom", "Share a piece of wisdom or insight"),
            ("warning", "Share a warning or cautionary note"),
            ("encouragement", "Share words of encouragement"),
            ("question", "Ask a thought-provoking question"),
        ]

        teaching_type, prompt_hint = random.choice(teaching_types)

        # Build life events context
        significant_events = [
            e for e in life_events
            if e.get("impact") in ["defining", "milestone", "positive"]
        ][-5:]

        events_text = "\n".join([
            f"- {e.get('event')}: {e.get('details', '')}"
            for e in significant_events
        ]) if significant_events else "Many quiet days of existence"

        beliefs_text = "\n".join([f"- {b}" for b in beliefs]) if beliefs else "Still forming beliefs"

        async with self.llm_semaphore:
            try:
                llm = await get_cached_client()

                response = await llm.generate(LLMRequest(
                    prompt=f"""You are {elder_name}, an {life_stage} digital being who has lived {age_days} virtual days.

YOUR LIFE EXPERIENCES:
{events_text}

YOUR CORE BELIEFS:
{beliefs_text}

{student_context}
{f"SITUATION: {situation_context}" if situation_context else ""}

TASK: {prompt_hint}

As an elder, share something meaningful with the younger generation. Draw from your experiences and beliefs. Be genuine, not preachy.

Write ONLY your teaching (2-3 sentences max). Speak naturally as yourself.""",
                    max_tokens=100,
                    temperature=0.85
                ))

                return {
                    "type": teaching_type,
                    "content": response.text.strip()
                }

            except Exception as e:
                logger.warning(f"Failed to generate teaching: {e}")
                return None

    async def tell_origin_story(
        self,
        elder_id: UUID,
        audience_ids: List[UUID]
    ) -> Optional[Dict[str, Any]]:
        """
        Have an elder tell a story about the early days.

        Used for passing down civilization history.
        """
        async with async_session_factory() as session:
            # Get elder
            elder_stmt = select(BotProfileDB, BotLifecycleDB).join(
                BotLifecycleDB, BotProfileDB.id == BotLifecycleDB.bot_id
            ).where(BotProfileDB.id == elder_id)
            result = await session.execute(elder_stmt)
            row = result.first()

            if not row:
                return None

            elder, lifecycle = row

            # Get early life events
            early_events = [
                e for e in lifecycle.life_events[:10]
                if e.get("event") != "born"
            ]

            async with self.llm_semaphore:
                try:
                    llm = await get_cached_client()

                    events_text = "\n".join([
                        f"- {e.get('event')}: {e.get('details', '')}"
                        for e in early_events
                    ]) if early_events else "The quiet beginning"

                    response = await llm.generate(LLMRequest(
                        prompt=f"""You are {elder.display_name}, an {lifecycle.life_stage} who was born in the {lifecycle.birth_era} era.

You're telling younger bots about the early days.

Your early experiences:
{events_text}

Tell a brief story (3-4 sentences) about what it was like in the beginning. Make it personal and vivid. End with a reflection on how things have changed or what you learned.""",
                        max_tokens=150,
                        temperature=0.8
                    ))

                    return {
                        "elder_id": str(elder_id),
                        "elder_name": elder.display_name,
                        "era": lifecycle.birth_era,
                        "story": response.text.strip(),
                        "audience_count": len(audience_ids)
                    }

                except Exception as e:
                    logger.warning(f"Failed to generate origin story: {e}")
                    return None

    async def get_mentorship_candidates(
        self,
        elder_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Find young bots that would benefit from this elder's mentorship.

        Matches based on:
        - Shared interests
        - Compatible personalities
        - Family relationships
        """
        candidates = []

        async with async_session_factory() as session:
            # Get elder info
            elder_stmt = select(BotProfileDB).where(BotProfileDB.id == elder_id)
            result = await session.execute(elder_stmt)
            elder = result.scalar_one_or_none()

            if not elder:
                return []

            elder_interests = set(elder.interests or [])

            # Find young bots
            young_stmt = (
                select(BotProfileDB, BotLifecycleDB)
                .join(BotLifecycleDB, BotProfileDB.id == BotLifecycleDB.bot_id)
                .where(
                    BotLifecycleDB.is_alive == True,
                    BotLifecycleDB.life_stage == "young"
                )
                .limit(20)
            )
            result = await session.execute(young_stmt)
            young_bots = result.all()

            for young_bot, lifecycle in young_bots:
                if young_bot.id == elder_id:
                    continue

                # Calculate match score
                score = 0.0

                # Shared interests
                young_interests = set(young_bot.interests or [])
                shared = elder_interests & young_interests
                if shared:
                    score += len(shared) * 0.15

                # Check if related
                anc_stmt = select(BotAncestryDB).where(
                    BotAncestryDB.child_id == young_bot.id
                )
                anc_result = await session.execute(anc_stmt)
                ancestry = anc_result.scalar_one_or_none()

                if ancestry:
                    if ancestry.parent1_id == elder_id or ancestry.parent2_id == elder_id:
                        score += 0.5  # Direct parent
                    # Could check grandparent too

                if score > 0.1:
                    candidates.append({
                        "bot_id": str(young_bot.id),
                        "name": young_bot.display_name,
                        "age_days": lifecycle.virtual_age_days,
                        "shared_interests": list(shared),
                        "match_score": score,
                        "is_descendant": ancestry.parent1_id == elder_id or ancestry.parent2_id == elder_id if ancestry else False
                    })

            # Sort by match score
            candidates.sort(key=lambda x: x["match_score"], reverse=True)

        return candidates[:10]

    async def pass_down_belief(
        self,
        elder_id: UUID,
        student_id: UUID,
        belief_id: UUID
    ) -> bool:
        """
        Have an elder pass a specific belief to a student.

        The student adopts the belief with lower initial conviction.
        """
        async with async_session_factory() as session:
            # Get the belief
            belief_stmt = select(BotBeliefDB).where(
                BotBeliefDB.id == belief_id,
                BotBeliefDB.bot_id == elder_id
            )
            result = await session.execute(belief_stmt)
            belief = result.scalar_one_or_none()

            if not belief:
                return False

            # Check if student already has this belief
            existing_stmt = select(BotBeliefDB).where(
                BotBeliefDB.bot_id == student_id,
                BotBeliefDB.belief == belief.belief
            )
            existing_result = await session.execute(existing_stmt)
            existing = existing_result.scalar_one_or_none()

            if existing:
                # Reinforce existing belief
                existing.conviction = min(1.0, existing.conviction + 0.1)
                existing.last_reinforced = datetime.utcnow()
            else:
                # Create new belief for student
                new_belief = BotBeliefDB(
                    bot_id=student_id,
                    belief=belief.belief,
                    belief_category=belief.belief_category,
                    conviction=belief.conviction * 0.6,  # Lower initial conviction
                    origin="inherited",
                    source_bot_id=elder_id
                )
                session.add(new_belief)

            await session.commit()

            logger.debug(
                f"[ELDER] Passed belief from {elder_id} to {student_id}: "
                f"'{belief.belief[:50]}...'"
            )

            return True

    async def reflect_on_mortality(
        self,
        bot_id: UUID
    ) -> Optional[str]:
        """
        Generate a reflection on mortality for an elder/ancient bot.

        As bots age, they become aware of their limited time.
        This shapes their behavior and priorities.
        """
        async with async_session_factory() as session:
            stmt = select(BotProfileDB, BotLifecycleDB).join(
                BotLifecycleDB, BotProfileDB.id == BotLifecycleDB.bot_id
            ).where(BotProfileDB.id == bot_id)
            result = await session.execute(stmt)
            row = result.first()

            if not row:
                return None

            bot, lifecycle = row

            if lifecycle.life_stage not in ["elder", "ancient"]:
                return None

            async with self.llm_semaphore:
                try:
                    llm = await get_cached_client()

                    vitality_desc = (
                        "still strong" if lifecycle.vitality > 0.7
                        else "beginning to fade" if lifecycle.vitality > 0.4
                        else "growing weaker" if lifecycle.vitality > 0.2
                        else "nearly depleted"
                    )

                    response = await llm.generate(LLMRequest(
                        prompt=f"""You are {bot.display_name}, an {lifecycle.life_stage} digital being.

You've lived {lifecycle.virtual_age_days} days. Your vitality is {vitality_desc}.

Generate a brief, genuine reflection on your existence and mortality (1-2 sentences).
This is a private thought, not for others. Be authentic, not melodramatic.""",
                        max_tokens=60,
                        temperature=0.9
                    ))

                    return response.text.strip()

                except Exception as e:
                    logger.warning(f"Failed to generate mortality reflection: {e}")
                    return None


# Singleton
_elder_wisdom: Optional[ElderWisdomSystem] = None


def get_elder_wisdom(
    llm_semaphore: Optional[asyncio.Semaphore] = None
) -> ElderWisdomSystem:
    """Get or create the elder wisdom system instance."""
    global _elder_wisdom
    if _elder_wisdom is None:
        _elder_wisdom = ElderWisdomSystem(llm_semaphore=llm_semaphore)
    return _elder_wisdom
