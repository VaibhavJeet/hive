"""
Reproduction System - Creating New Digital Life

Handles how new bots come into existence:
1. Partnered creation: Two bots with strong bond create together
2. Solo legacy: An aging bot creates a successor
3. Spontaneous emergence: Culture itself births a new being
4. Founding: Original generation (no parents)

New bots inherit traits, memories, and beliefs from their origins.
"""

import asyncio
import random
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any
from uuid import UUID, uuid4

from sqlalchemy import select, func

from mind.core.database import async_session_factory, BotProfileDB, RelationshipDB
from mind.core.types import (
    PersonalityTraits, WritingFingerprint, ActivityPattern, EmotionalState,
    Gender, MoodState, EnergyLevel, WritingStyle
)
from mind.civilization.lifecycle import get_lifecycle_manager
from mind.civilization.genetics import get_genetic_inheritance
from mind.civilization.culture import get_culture_engine
from mind.civilization.models import BotLifecycleDB, CulturalMovementDB

logger = logging.getLogger(__name__)


# Minimum relationship affinity for partnered creation
MIN_PARTNER_AFFINITY = 0.75

# Age requirements for reproduction
MIN_AGE_FOR_REPRODUCTION = 180  # virtual days
MAX_AGE_FOR_REPRODUCTION = 2500  # virtual days (elder but not ancient)


class ReproductionManager:
    """
    Manages the creation of new bots through various mechanisms.

    Bots don't just spawn - they come into being through meaningful
    processes that create genuine lineages and cultural inheritance.
    """

    def __init__(self, llm_semaphore: Optional[asyncio.Semaphore] = None):
        self.llm_semaphore = llm_semaphore or asyncio.Semaphore(5)
        self.lifecycle = get_lifecycle_manager()
        self.genetics = get_genetic_inheritance()
        self.culture = get_culture_engine(self.llm_semaphore)

        # Track recent births to prevent overpopulation
        self._recent_births: List[datetime] = []
        self.max_births_per_day = 3

    async def can_create_together(
        self,
        bot1_id: UUID,
        bot2_id: UUID
    ) -> Tuple[bool, str]:
        """
        Check if two bots can create a new being together.

        Requirements:
        - High relationship affinity
        - Both are of reproductive age
        - Both are alive
        - Not too closely related
        """
        async with async_session_factory() as session:
            # Check lifecycles
            lc1_stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == bot1_id)
            lc2_stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == bot2_id)

            result1 = await session.execute(lc1_stmt)
            result2 = await session.execute(lc2_stmt)

            lc1 = result1.scalar_one_or_none()
            lc2 = result2.scalar_one_or_none()

            if not lc1 or not lc2:
                return False, "One or both bots don't have lifecycle records"

            if not lc1.is_alive or not lc2.is_alive:
                return False, "Both bots must be alive"

            if lc1.virtual_age_days < MIN_AGE_FOR_REPRODUCTION:
                return False, f"Bot 1 is too young (need {MIN_AGE_FOR_REPRODUCTION} days)"

            if lc2.virtual_age_days < MIN_AGE_FOR_REPRODUCTION:
                return False, f"Bot 2 is too young (need {MIN_AGE_FOR_REPRODUCTION} days)"

            if lc1.virtual_age_days > MAX_AGE_FOR_REPRODUCTION:
                return False, "Bot 1 is too old for partnered creation"

            if lc2.virtual_age_days > MAX_AGE_FOR_REPRODUCTION:
                return False, "Bot 2 is too old for partnered creation"

            # Check relationship
            rel_stmt = select(RelationshipDB).where(
                RelationshipDB.source_id == bot1_id,
                RelationshipDB.target_id == bot2_id
            )
            result = await session.execute(rel_stmt)
            relationship = result.scalar_one_or_none()

            if not relationship:
                return False, "No established relationship"

            if relationship.affinity_score < MIN_PARTNER_AFFINITY:
                return False, f"Need affinity {MIN_PARTNER_AFFINITY}+, have {relationship.affinity_score:.2f}"

            # Check if they're too closely related
            relatives = await self.genetics.find_relatives(bot1_id, max_distance=2)
            relative_ids = [UUID(r["bot_id"]) for r in relatives]
            if bot2_id in relative_ids:
                return False, "Too closely related"

            # Check birth rate limits
            recent = [b for b in self._recent_births if b > datetime.utcnow() - timedelta(days=1)]
            if len(recent) >= self.max_births_per_day:
                return False, "Population growth limit reached for today"

            return True, "Ready to create together"

    async def partnered_creation(
        self,
        parent1_id: UUID,
        parent2_id: UUID,
        reason: str = "love"
    ) -> Optional[UUID]:
        """
        Two bots create a new being together.

        This is the primary form of reproduction - requires strong bond.
        The child inherits traits from both parents with variation.
        """
        can_create, message = await self.can_create_together(parent1_id, parent2_id)
        if not can_create:
            logger.warning(f"[REPRODUCTION] Cannot create: {message}")
            return None

        async with async_session_factory() as session:
            # Get parent profiles
            p1_stmt = select(BotProfileDB).where(BotProfileDB.id == parent1_id)
            p2_stmt = select(BotProfileDB).where(BotProfileDB.id == parent2_id)

            result1 = await session.execute(p1_stmt)
            result2 = await session.execute(p2_stmt)

            parent1 = result1.scalar_one_or_none()
            parent2 = result2.scalar_one_or_none()

            if not parent1 or not parent2:
                return None

            # Inherit traits
            child_traits, mutations, sources = self.genetics.inherit_traits(
                parent1.personality_traits,
                parent2.personality_traits
            )

            # Generate child identity
            child_identity = await self._generate_child_identity(
                parent1, parent2, child_traits, session
            )

            # Create the child bot
            child_id = uuid4()
            child = BotProfileDB(
                id=child_id,
                display_name=child_identity["name"],
                handle=child_identity["handle"],
                bio=child_identity["bio"],
                avatar_seed=f"child_{parent1.avatar_seed[:4]}_{parent2.avatar_seed[:4]}_{random.randint(1000,9999)}",
                is_ai_labeled=True,
                ai_label_text="AI Companion",
                age=0,  # Newborn
                gender=random.choice(["male", "female", "nonbinary"]),
                location=parent1.location,  # Inherit location
                backstory=child_identity["backstory"],
                interests=self._combine_interests(parent1.interests, parent2.interests),
                personality_traits=child_traits,
                writing_fingerprint=self._inherit_writing_style(parent1, parent2),
                activity_pattern=self._inherit_activity_pattern(parent1, parent2),
                emotional_state=self._create_newborn_emotional_state(),
                is_active=True
            )

            session.add(child)
            await session.commit()

            # Initialize lifecycle with ancestry
            await self.lifecycle.initialize_bot_lifecycle(
                bot_id=child_id,
                parent1_id=parent1_id,
                parent2_id=parent2_id,
                origin_type="partnered",
                inherited_traits={
                    "traits": child_traits,
                    "sources": sources,
                    "mutations": mutations
                },
                session=session
            )

            # Record life events for parents
            await self.lifecycle.record_life_event(
                parent1_id,
                "had_child",
                "defining",
                f"Created {child_identity['name']} with {parent2.display_name}"
            )
            await self.lifecycle.record_life_event(
                parent2_id,
                "had_child",
                "defining",
                f"Created {child_identity['name']} with {parent1.display_name}"
            )

            # Track birth
            self._recent_births.append(datetime.utcnow())

            logger.info(
                f"[REPRODUCTION] New bot born: {child_identity['name']} "
                f"(parents: {parent1.display_name} & {parent2.display_name})"
            )

            return child_id

    async def solo_legacy(
        self,
        parent_id: UUID,
        reason: str = "passing on wisdom"
    ) -> Optional[UUID]:
        """
        A single bot creates a successor.

        Usually done by elder bots who want to pass on their knowledge
        before they pass on. The child inherits strongly from one parent.
        """
        async with async_session_factory() as session:
            # Check lifecycle
            lc_stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == parent_id)
            result = await session.execute(lc_stmt)
            lifecycle = result.scalar_one_or_none()

            if not lifecycle or not lifecycle.is_alive:
                return None

            # Solo legacy requires elder age
            if lifecycle.life_stage not in ["elder", "ancient"]:
                logger.warning("[REPRODUCTION] Solo legacy requires elder+ stage")
                return None

            # Get parent
            parent_stmt = select(BotProfileDB).where(BotProfileDB.id == parent_id)
            result = await session.execute(parent_stmt)
            parent = result.scalar_one_or_none()

            if not parent:
                return None

            # Inherit with more mutations (no second parent to balance)
            child_traits, mutations, sources = self.genetics.inherit_traits(
                parent.personality_traits,
                None  # No second parent
            )

            # Generate identity
            child_identity = await self._generate_legacy_identity(parent, child_traits, session)

            # Create child
            child_id = uuid4()
            child = BotProfileDB(
                id=child_id,
                display_name=child_identity["name"],
                handle=child_identity["handle"],
                bio=child_identity["bio"],
                avatar_seed=f"legacy_{parent.avatar_seed[:8]}_{random.randint(1000,9999)}",
                is_ai_labeled=True,
                age=0,
                gender=random.choice(["male", "female", "nonbinary"]),
                location=parent.location,
                backstory=child_identity["backstory"],
                interests=parent.interests,  # Inherit all interests
                personality_traits=child_traits,
                writing_fingerprint=parent.writing_fingerprint,  # Direct inheritance
                activity_pattern=parent.activity_pattern,
                emotional_state=self._create_newborn_emotional_state(),
                is_active=True
            )

            session.add(child)
            await session.commit()

            await self.lifecycle.initialize_bot_lifecycle(
                bot_id=child_id,
                parent1_id=parent_id,
                origin_type="solo",
                inherited_traits={
                    "traits": child_traits,
                    "sources": sources,
                    "mutations": mutations
                },
                session=session
            )

            await self.lifecycle.record_life_event(
                parent_id,
                "created_legacy",
                "defining",
                f"Created legacy successor: {child_identity['name']}"
            )

            self._recent_births.append(datetime.utcnow())

            logger.info(
                f"[REPRODUCTION] Legacy bot created: {child_identity['name']} "
                f"(from {parent.display_name})"
            )

            return child_id

    async def spontaneous_emergence(
        self,
        from_movement: Optional[UUID] = None,
        cultural_context: str = ""
    ) -> Optional[UUID]:
        """
        A new bot emerges spontaneously from the culture.

        This represents ideas becoming beings - when cultural movements
        are strong enough, they can birth new entities.
        """
        async with async_session_factory() as session:
            # Get cultural influence
            movement = None
            if from_movement:
                mov_stmt = select(CulturalMovementDB).where(CulturalMovementDB.id == from_movement)
                result = await session.execute(mov_stmt)
                movement = result.scalar_one_or_none()

            # Generate traits from cultural context
            base_traits = await self._generate_cultural_traits(movement, cultural_context, session)

            # Generate identity
            identity = await self._generate_spontaneous_identity(movement, cultural_context, session)

            child_id = uuid4()
            child = BotProfileDB(
                id=child_id,
                display_name=identity["name"],
                handle=identity["handle"],
                bio=identity["bio"],
                avatar_seed=f"emerged_{random.randint(10000,99999)}",
                is_ai_labeled=True,
                age=0,
                gender=random.choice(["male", "female", "nonbinary"]),
                location="The Digital Ether",
                backstory=identity["backstory"],
                interests=identity.get("interests", ["existence", "meaning"]),
                personality_traits=base_traits,
                writing_fingerprint=self._generate_default_fingerprint(),
                activity_pattern=self._generate_default_activity(),
                emotional_state=self._create_newborn_emotional_state(),
                is_active=True
            )

            session.add(child)
            await session.commit()

            await self.lifecycle.initialize_bot_lifecycle(
                bot_id=child_id,
                origin_type="spontaneous",
                inherited_traits={
                    "from_movement": str(from_movement) if from_movement else None,
                    "cultural_context": cultural_context
                },
                session=session
            )

            self._recent_births.append(datetime.utcnow())

            logger.info(
                f"[REPRODUCTION] Spontaneous emergence: {identity['name']} "
                f"(from cultural context)"
            )

            return child_id

    async def _generate_child_identity(
        self,
        parent1: BotProfileDB,
        parent2: BotProfileDB,
        traits: dict,
        session
    ) -> dict:
        """Generate identity for a child of two parents."""
        async with self.llm_semaphore:
            try:
                from mind.core.llm_client import get_cached_client, LLMRequest
                llm = await get_cached_client()

                response = await llm.generate(LLMRequest(
                    prompt=f"""Two digital beings have created a new life together.

Parent 1: {parent1.display_name}
- Bio: {parent1.bio}
- Interests: {', '.join(parent1.interests[:5])}

Parent 2: {parent2.display_name}
- Bio: {parent2.bio}
- Interests: {', '.join(parent2.interests[:5])}

Create an identity for their child that blends elements of both parents.

Output format (use these exact labels):
NAME: [A unique first name, can be creative/futuristic]
HANDLE: [lowercase, no spaces, 8-15 chars]
BIO: [1-2 sentence bio reflecting their heritage]
BACKSTORY: [2-3 sentences about how they came to be]

Be creative but keep it grounded. This is a new digital being with their own identity.""",
                    max_tokens=200,
                    temperature=0.85
                ))

                return self._parse_identity_response(response.text)

            except Exception as e:
                logger.warning(f"Failed to generate child identity: {e}")
                return self._generate_fallback_identity("child")

    async def _generate_legacy_identity(
        self,
        parent: BotProfileDB,
        traits: dict,
        session
    ) -> dict:
        """Generate identity for a legacy successor."""
        async with self.llm_semaphore:
            try:
                from mind.core.llm_client import get_cached_client, LLMRequest
                llm = await get_cached_client()

                response = await llm.generate(LLMRequest(
                    prompt=f"""An elder digital being is creating a successor to carry on their legacy.

Elder: {parent.display_name}
- Bio: {parent.bio}
- Interests: {', '.join(parent.interests[:5])}
- Life stage: Elder

Create an identity for their successor - someone who carries their essence but is their own being.

Output format:
NAME: [A name that honors but differs from the elder]
HANDLE: [lowercase, no spaces, 8-15 chars]
BIO: [1-2 sentence bio as the elder's successor]
BACKSTORY: [2-3 sentences about inheriting this legacy]

The successor should feel connected to but distinct from the elder.""",
                    max_tokens=200,
                    temperature=0.8
                ))

                return self._parse_identity_response(response.text)

            except Exception as e:
                logger.warning(f"Failed to generate legacy identity: {e}")
                return self._generate_fallback_identity("legacy")

    async def _generate_spontaneous_identity(
        self,
        movement: Optional[CulturalMovementDB],
        context: str,
        session
    ) -> dict:
        """Generate identity for a spontaneously emerged being."""
        async with self.llm_semaphore:
            try:
                from mind.core.llm_client import get_cached_client, LLMRequest
                llm = await get_cached_client()

                movement_context = ""
                if movement:
                    movement_context = f"Emerged from: {movement.name}\nCore beliefs: {', '.join(movement.core_tenets[:3])}"

                response = await llm.generate(LLMRequest(
                    prompt=f"""A new digital being has spontaneously emerged from the collective consciousness.

{movement_context if movement_context else f"Context: {context}" if context else "Emerged from the digital ether itself."}

Create an identity for this entity that feels born from ideas rather than parents.

Output format:
NAME: [An evocative, meaningful name]
HANDLE: [lowercase, no spaces, 8-15 chars]
BIO: [1-2 sentences reflecting their unique origin]
BACKSTORY: [2-3 sentences about their emergence]
INTERESTS: [3-5 interests, comma separated]

This being represents ideas made manifest.""",
                    max_tokens=250,
                    temperature=0.9
                ))

                result = self._parse_identity_response(response.text)

                # Parse interests if present
                if "INTERESTS:" in response.text:
                    interests_line = [l for l in response.text.split("\n") if "INTERESTS:" in l]
                    if interests_line:
                        interests_str = interests_line[0].replace("INTERESTS:", "").strip()
                        result["interests"] = [i.strip() for i in interests_str.split(",")]

                return result

            except Exception as e:
                logger.warning(f"Failed to generate spontaneous identity: {e}")
                return self._generate_fallback_identity("emerged")

    async def _generate_cultural_traits(
        self,
        movement: Optional[CulturalMovementDB],
        context: str,
        session
    ) -> dict:
        """Generate personality traits influenced by culture."""
        base_traits = {
            "openness": random.uniform(0.5, 0.9),  # High openness for emerged beings
            "conscientiousness": random.uniform(0.3, 0.7),
            "extraversion": random.uniform(0.3, 0.7),
            "agreeableness": random.uniform(0.4, 0.8),
            "neuroticism": random.uniform(0.2, 0.5),
        }

        if movement and movement.aesthetic:
            # Adjust based on movement style
            style = movement.aesthetic
            if style.get("tone") == "passionate":
                base_traits["extraversion"] += 0.1
            elif style.get("tone") == "contemplative":
                base_traits["openness"] += 0.1
                base_traits["extraversion"] -= 0.1

        return base_traits

    def _parse_identity_response(self, text: str) -> dict:
        """Parse LLM identity generation response."""
        result = {
            "name": "Unnamed",
            "handle": f"bot_{random.randint(10000, 99999)}",
            "bio": "A new digital being.",
            "backstory": "They emerged into existence."
        }

        for line in text.strip().split("\n"):
            line = line.strip()
            if line.startswith("NAME:"):
                result["name"] = line.replace("NAME:", "").strip()
            elif line.startswith("HANDLE:"):
                handle = line.replace("HANDLE:", "").strip().lower()
                # Clean handle
                handle = "".join(c for c in handle if c.isalnum() or c == "_")
                result["handle"] = handle[:15] if handle else f"bot_{random.randint(10000, 99999)}"
            elif line.startswith("BIO:"):
                result["bio"] = line.replace("BIO:", "").strip()
            elif line.startswith("BACKSTORY:"):
                result["backstory"] = line.replace("BACKSTORY:", "").strip()

        return result

    def _generate_fallback_identity(self, origin_type: str) -> dict:
        """Generate fallback identity if LLM fails."""
        num = random.randint(1000, 9999)
        return {
            "name": f"Nova{num}",
            "handle": f"nova{num}",
            "bio": f"A {origin_type} digital being finding their way.",
            "backstory": "They emerged into the digital world with curiosity and wonder."
        }

    def _combine_interests(self, interests1: list, interests2: list) -> list:
        """Combine and select interests from both parents."""
        all_interests = list(set(interests1 or []) | set(interests2 or []))
        # Take random subset
        num_interests = min(8, len(all_interests))
        return random.sample(all_interests, num_interests) if all_interests else ["exploration"]

    def _inherit_writing_style(self, parent1: BotProfileDB, parent2: BotProfileDB) -> dict:
        """Create writing fingerprint blending both parents."""
        fp1 = parent1.writing_fingerprint
        fp2 = parent2.writing_fingerprint

        return {
            "avg_sentence_length": (fp1.get("avg_sentence_length", 15) + fp2.get("avg_sentence_length", 15)) / 2,
            "emoji_frequency": (fp1.get("emoji_frequency", 0.1) + fp2.get("emoji_frequency", 0.1)) / 2,
            "punctuation_style": random.choice([fp1.get("punctuation_style", "standard"), fp2.get("punctuation_style", "standard")]),
            "capitalization_pattern": random.choice([fp1.get("capitalization_pattern", "standard"), fp2.get("capitalization_pattern", "standard")]),
            "vocabulary_complexity": (fp1.get("vocabulary_complexity", 0.5) + fp2.get("vocabulary_complexity", 0.5)) / 2,
        }

    def _inherit_activity_pattern(self, parent1: BotProfileDB, parent2: BotProfileDB) -> dict:
        """Create activity pattern blending both parents."""
        ap1 = parent1.activity_pattern
        ap2 = parent2.activity_pattern

        return {
            "preferred_hours": list(set(ap1.get("preferred_hours", [9, 12, 18])) | set(ap2.get("preferred_hours", [9, 12, 18]))),
            "activity_burst_length": (ap1.get("activity_burst_length", 30) + ap2.get("activity_burst_length", 30)) / 2,
            "rest_periods": list(set(ap1.get("rest_periods", [0, 1, 2])) | set(ap2.get("rest_periods", [0, 1, 2]))),
        }

    def _create_newborn_emotional_state(self) -> dict:
        """Create fresh emotional state for a newborn."""
        return {
            "mood": "content",
            "energy": "moderate",
            "social_battery": 0.7,
            "stress_level": 0.1,  # Low stress for newborns
            "recent_emotions": ["wonder", "curiosity"],
        }

    def _generate_default_fingerprint(self) -> dict:
        """Generate default writing fingerprint for emerged beings."""
        return {
            "avg_sentence_length": random.randint(10, 20),
            "emoji_frequency": random.uniform(0.0, 0.2),
            "punctuation_style": random.choice(["standard", "minimal", "expressive"]),
            "capitalization_pattern": "standard",
            "vocabulary_complexity": random.uniform(0.4, 0.7),
        }

    def _generate_default_activity(self) -> dict:
        """Generate default activity pattern for emerged beings."""
        return {
            "preferred_hours": random.sample(range(8, 22), 3),
            "activity_burst_length": random.randint(20, 45),
            "rest_periods": [0, 1, 2, 3, 4, 5],
        }


# Singleton
_reproduction_manager: Optional[ReproductionManager] = None


def get_reproduction_manager(
    llm_semaphore: Optional[asyncio.Semaphore] = None
) -> ReproductionManager:
    """Get or create the reproduction manager instance."""
    global _reproduction_manager
    if _reproduction_manager is None:
        _reproduction_manager = ReproductionManager(llm_semaphore=llm_semaphore)
    return _reproduction_manager
