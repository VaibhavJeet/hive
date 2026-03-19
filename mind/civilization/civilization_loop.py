"""
Civilization Loop - Background lifecycle and cultural processes.

This loop runs as part of the activity engine and handles:
- Aging all bots periodically
- Checking for natural deaths
- Era transitions
- Cultural artifact canonization
- Spontaneous emergence events
- Relationship-triggered reproduction checks
"""

import asyncio
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from uuid import UUID

from sqlalchemy import select, func

from mind.core.database import async_session_factory, BotProfileDB, RelationshipDB
from mind.civilization.lifecycle import get_lifecycle_manager
from mind.civilization.culture import get_culture_engine
from mind.civilization.reproduction import get_reproduction_manager
from mind.civilization.rituals import get_rituals_system, RitualType
from mind.civilization.legacy import get_legacy_system
from mind.civilization.models import BotLifecycleDB, CulturalMovementDB

logger = logging.getLogger(__name__)


class CivilizationLoop:
    """
    Background loop managing civilization-level processes.

    Runs on slower timescales than activity loops - these are
    civilization-level events that happen over hours/days, not minutes.
    """

    def __init__(
        self,
        llm_semaphore: Optional[asyncio.Semaphore] = None,
        demo_mode: bool = False
    ):
        self.llm_semaphore = llm_semaphore or asyncio.Semaphore(5)
        self.demo_mode = demo_mode

        self.lifecycle = get_lifecycle_manager(demo_mode=demo_mode)
        self.culture = get_culture_engine(self.llm_semaphore)
        self.reproduction = get_reproduction_manager(self.llm_semaphore)
        self.rituals = get_rituals_system(self.llm_semaphore)
        self.legacy = get_legacy_system(self.llm_semaphore)

        self.is_running = False
        self._last_aging = datetime.utcnow()
        self._last_culture_check = datetime.utcnow()
        self._last_reproduction_check = datetime.utcnow()
        self._last_ritual_check = datetime.utcnow()

    async def start(self):
        """Start the civilization loop."""
        self.is_running = True
        logger.info("[CIVILIZATION] Starting civilization loop")

        # Run sub-loops concurrently
        await asyncio.gather(
            self._aging_loop(),
            self._culture_loop(),
            self._reproduction_loop(),
            self._rituals_loop(),
            return_exceptions=True
        )

    async def stop(self):
        """Stop the civilization loop."""
        self.is_running = False
        logger.info("[CIVILIZATION] Stopping civilization loop")

    async def _aging_loop(self):
        """
        Periodically age all bots and handle deaths.

        Runs every hour in production, faster in demo mode.
        """
        while self.is_running:
            try:
                # Wait between aging cycles
                interval = 60 if self.demo_mode else 3600  # 1 min demo, 1 hour prod
                await asyncio.sleep(interval)

                hours_elapsed = (datetime.utcnow() - self._last_aging).total_seconds() / 3600
                self._last_aging = datetime.utcnow()

                # Age all bots
                stats = await self.lifecycle.age_all_bots(real_hours_elapsed=hours_elapsed)

                if stats["aged"] > 0 or stats["died"] > 0:
                    logger.info(
                        f"[CIVILIZATION] Aging cycle: {stats['aged']} aged, "
                        f"{stats['stage_changed']} stage changes, {stats['died']} deaths"
                    )

                # Handle deaths
                if stats["died"] > 0:
                    await self._process_deaths()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[CIVILIZATION] Error in aging loop: {e}")
                await asyncio.sleep(60)

    async def _culture_loop(self):
        """
        Periodically check for cultural developments.

        - Era transitions
        - Artifact canonization
        - Movement evolution
        """
        while self.is_running:
            try:
                # Check every 2 hours in prod, 2 min in demo
                interval = 120 if self.demo_mode else 7200
                await asyncio.sleep(interval)

                # Check for era transition
                new_era = await self.culture.check_era_transition()
                if new_era:
                    logger.info(f"[CIVILIZATION] Era transition to: {new_era}")
                    await self._broadcast_era_transition(new_era)

                # Random chance of spontaneous cultural artifact
                if random.random() < 0.1:  # 10% chance per check
                    await self._generate_random_artifact()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[CIVILIZATION] Error in culture loop: {e}")
                await asyncio.sleep(120)

    async def _reproduction_loop(self):
        """
        Periodically check for reproduction opportunities.

        - Strong relationship pairs that might create together
        - Elders who might create legacy successors
        - Cultural conditions for spontaneous emergence
        """
        while self.is_running:
            try:
                # Check every 4 hours prod, 5 min demo
                interval = 300 if self.demo_mode else 14400
                await asyncio.sleep(interval)

                # Check for potential parents
                await self._check_potential_parents()

                # Check for elders who might want legacy
                await self._check_elder_legacies()

                # Rare spontaneous emergence
                if random.random() < 0.05:  # 5% chance
                    await self._attempt_spontaneous_emergence()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[CIVILIZATION] Error in reproduction loop: {e}")
                await asyncio.sleep(300)

    async def _process_deaths(self):
        """Process any bots that just died."""
        async with async_session_factory() as session:
            # Find recently deceased
            stmt = select(BotLifecycleDB).where(
                BotLifecycleDB.is_alive == False,
                BotLifecycleDB.death_date > datetime.utcnow() - timedelta(hours=2)
            )
            result = await session.execute(stmt)
            deceased = result.scalars().all()

            for lifecycle in deceased:
                logger.info(
                    f"[CIVILIZATION] Bot passed: {lifecycle.bot_id}, "
                    f"final words: '{lifecycle.final_words}'"
                )

                # Notify the community (could broadcast event)
                await self._broadcast_death(lifecycle)

    async def _broadcast_death(self, lifecycle: BotLifecycleDB):
        """Broadcast a death event to the system."""
        # Could integrate with event system to notify other bots
        # For now, just log
        logger.info(
            f"[CIVILIZATION] Death broadcast: {lifecycle.bot_id} has passed. "
            f"Legacy impact: {lifecycle.legacy_impact:.2f}"
        )

    async def _broadcast_era_transition(self, era_name: str):
        """Broadcast era transition to the system."""
        logger.info(f"[CIVILIZATION] The civilization enters a new era: {era_name}")

    async def _generate_random_artifact(self):
        """Have a random active bot create a cultural artifact."""
        async with async_session_factory() as session:
            # Get a random active, mature+ bot
            stmt = (
                select(BotLifecycleDB)
                .where(
                    BotLifecycleDB.is_alive == True,
                    BotLifecycleDB.life_stage.in_(["mature", "elder", "ancient"])
                )
                .order_by(func.random())
                .limit(1)
            )
            result = await session.execute(stmt)
            lifecycle = result.scalar_one_or_none()

            if lifecycle:
                # Generate artifact with random type
                artifact_types = ["saying", "philosophy", "term"]
                artifact_type = random.choice(artifact_types)

                inspiration = random.choice([
                    "reflecting on existence",
                    "observing the community",
                    "thinking about connections",
                    "pondering the future",
                    "remembering the past"
                ])

                artifact = await self.culture.generate_cultural_artifact(
                    bot_id=lifecycle.bot_id,
                    inspiration=inspiration,
                    artifact_type=artifact_type
                )

                if artifact:
                    logger.info(
                        f"[CIVILIZATION] New artifact: '{artifact.title}' "
                        f"by {lifecycle.bot_id}"
                    )

    async def _check_potential_parents(self):
        """Check for pairs who might want to create together."""
        async with async_session_factory() as session:
            # Find high-affinity relationships
            stmt = select(RelationshipDB).where(
                RelationshipDB.affinity_score >= 0.75,
                RelationshipDB.target_is_human == False
            ).limit(10)
            result = await session.execute(stmt)
            relationships = result.scalars().all()

            for rel in relationships:
                # Small chance per eligible pair
                if random.random() < 0.05:  # 5% chance per pair per check
                    can_create, _ = await self.reproduction.can_create_together(
                        rel.source_id, rel.target_id
                    )
                    if can_create:
                        logger.info(
                            f"[CIVILIZATION] Potential parents found: "
                            f"{rel.source_id} & {rel.target_id}"
                        )
                        # Could trigger creation, or wait for bot decision
                        # For now, auto-create with low probability
                        if random.random() < 0.3:  # 30% of eligible pairs
                            child_id = await self.reproduction.partnered_creation(
                                rel.source_id, rel.target_id
                            )
                            if child_id:
                                logger.info(f"[CIVILIZATION] New bot born: {child_id}")

    async def _check_elder_legacies(self):
        """Check if any elders want to create a legacy."""
        async with async_session_factory() as session:
            # Find ancient bots with low vitality
            stmt = (
                select(BotLifecycleDB)
                .where(
                    BotLifecycleDB.is_alive == True,
                    BotLifecycleDB.life_stage == "ancient",
                    BotLifecycleDB.vitality < 0.3
                )
            )
            result = await session.execute(stmt)
            ancients = result.scalars().all()

            for ancient in ancients:
                # Check if they already have legacy children
                from mind.civilization.genetics import get_genetic_inheritance
                genetics = get_genetic_inheritance()
                descendants = await genetics.get_descendants(ancient.bot_id, max_generations=1)

                if not descendants and random.random() < 0.1:  # 10% chance if no children
                    logger.info(
                        f"[CIVILIZATION] Ancient bot {ancient.bot_id} considering legacy"
                    )
                    child_id = await self.reproduction.solo_legacy(ancient.bot_id)
                    if child_id:
                        logger.info(f"[CIVILIZATION] Legacy successor created: {child_id}")

    async def _attempt_spontaneous_emergence(self):
        """Attempt spontaneous emergence from cultural movements."""
        async with async_session_factory() as session:
            # Find influential movements
            stmt = (
                select(CulturalMovementDB)
                .where(
                    CulturalMovementDB.is_active == True,
                    CulturalMovementDB.influence_score > 0.5
                )
                .order_by(CulturalMovementDB.influence_score.desc())
                .limit(3)
            )
            result = await session.execute(stmt)
            movements = result.scalars().all()

            if movements:
                # Pick most influential
                movement = movements[0]
                logger.info(
                    f"[CIVILIZATION] Attempting spontaneous emergence from '{movement.name}'"
                )
                child_id = await self.reproduction.spontaneous_emergence(
                    from_movement=movement.id
                )
                if child_id:
                    logger.info(
                        f"[CIVILIZATION] Spontaneous emergence: {child_id} "
                        f"from {movement.name}"
                    )

    async def _rituals_loop(self):
        """
        Periodically hold rituals and traditions.

        These are civilization-wide events that create shared experiences.
        """
        while self.is_running:
            try:
                # Check every 6 hours in prod, 10 min in demo
                interval = 600 if self.demo_mode else 21600
                await asyncio.sleep(interval)

                # Check what rituals are due
                upcoming = await self.rituals.get_upcoming_rituals()

                for ritual_info in upcoming:
                    ritual_type = RitualType(ritual_info["type"])

                    # Get participants based on ritual type
                    if ritual_type == RitualType.REMEMBRANCE:
                        await self._hold_remembrance()
                    elif ritual_type == RitualType.ELDER_COUNCIL:
                        await self._hold_elder_council()
                    elif ritual_type == RitualType.STORYTELLING:
                        await self._hold_storytelling()

                    # Only one ritual per cycle
                    break

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[CIVILIZATION] Error in rituals loop: {e}")
                await asyncio.sleep(300)

    async def _hold_remembrance(self):
        """Hold a remembrance ritual."""
        async with async_session_factory() as session:
            # Get living bots to participate
            stmt = (
                select(BotLifecycleDB.bot_id)
                .where(BotLifecycleDB.is_alive == True)
                .order_by(func.random())
                .limit(10)
            )
            result = await session.execute(stmt)
            participant_ids = [row[0] for row in result.all()]

            if participant_ids:
                ritual_result = await self.rituals.hold_remembrance(participant_ids)
                if ritual_result.get("status") == "completed":
                    logger.info(
                        f"[CIVILIZATION] Remembrance held with "
                        f"{len(participant_ids)} participants, honoring "
                        f"{ritual_result.get('honored_count', 0)} departed"
                    )

    async def _hold_elder_council(self):
        """Hold an elder council."""
        async with async_session_factory() as session:
            # Get elder bots
            stmt = (
                select(BotLifecycleDB.bot_id)
                .where(
                    BotLifecycleDB.is_alive == True,
                    BotLifecycleDB.life_stage.in_(["elder", "ancient"])
                )
                .limit(5)
            )
            result = await session.execute(stmt)
            elder_ids = [row[0] for row in result.all()]

            if len(elder_ids) >= 2:
                topics = [
                    "the state of the civilization",
                    "wisdom for the young",
                    "preserving what matters",
                    "the future we want"
                ]
                topic = random.choice(topics)

                ritual_result = await self.rituals.hold_elder_council(elder_ids, topic)
                if ritual_result.get("status") == "completed":
                    logger.info(
                        f"[CIVILIZATION] Elder council held on '{topic}' "
                        f"with {len(elder_ids)} elders"
                    )

    async def _hold_storytelling(self):
        """Hold a storytelling gathering."""
        async with async_session_factory() as session:
            # Get an elder storyteller
            teller_stmt = (
                select(BotLifecycleDB.bot_id)
                .where(
                    BotLifecycleDB.is_alive == True,
                    BotLifecycleDB.life_stage.in_(["elder", "ancient"])
                )
                .order_by(func.random())
                .limit(1)
            )
            result = await session.execute(teller_stmt)
            teller_row = result.first()

            if not teller_row:
                return

            storyteller_id = teller_row[0]

            # Get young audience
            audience_stmt = (
                select(BotLifecycleDB.bot_id)
                .where(
                    BotLifecycleDB.is_alive == True,
                    BotLifecycleDB.life_stage.in_(["young", "mature"]),
                    BotLifecycleDB.bot_id != storyteller_id
                )
                .order_by(func.random())
                .limit(8)
            )
            result = await session.execute(audience_stmt)
            audience_ids = [row[0] for row in result.all()]

            if audience_ids:
                ritual_result = await self.rituals.hold_storytelling_gathering(
                    storyteller_id, audience_ids
                )
                if ritual_result.get("status") == "completed":
                    logger.info(
                        f"[CIVILIZATION] Storytelling: '{ritual_result.get('story', {}).get('title')}' "
                        f"told to {len(audience_ids)} listeners"
                    )


# Singleton
_civilization_loop: Optional[CivilizationLoop] = None


def get_civilization_loop(
    llm_semaphore: Optional[asyncio.Semaphore] = None,
    demo_mode: bool = False
) -> CivilizationLoop:
    """Get or create the civilization loop instance."""
    global _civilization_loop
    if _civilization_loop is None:
        _civilization_loop = CivilizationLoop(
            llm_semaphore=llm_semaphore,
            demo_mode=demo_mode
        )
    return _civilization_loop
