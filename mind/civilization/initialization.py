"""
Civilization Initialization - Bootstrap existing bots into the civilization.

When the civilization system is first deployed, existing bots need to be
initialized with:
- Lifecycle records (as founding generation)
- Initial beliefs based on their personality
- Cultural context

This module handles that bootstrap process.
"""

import asyncio
import random
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, func

from mind.core.database import async_session_factory, BotProfileDB
from mind.civilization.lifecycle import get_lifecycle_manager
from mind.civilization.culture import get_culture_engine
from mind.civilization.models import BotLifecycleDB, BotBeliefDB, CivilizationEraDB

logger = logging.getLogger(__name__)


class CivilizationInitializer:
    """
    Initializes the civilization system for existing bots.

    Run this once when deploying the civilization feature to an
    existing population of bots.
    """

    def __init__(self, llm_semaphore: Optional[asyncio.Semaphore] = None):
        self.llm_semaphore = llm_semaphore or asyncio.Semaphore(5)
        self.lifecycle_manager = get_lifecycle_manager()
        self.culture_engine = get_culture_engine(self.llm_semaphore)

    async def initialize_all(self) -> Dict[str, Any]:
        """
        Initialize the entire civilization system.

        Returns stats about what was initialized.
        """
        stats = {
            "era_created": False,
            "bots_initialized": 0,
            "beliefs_created": 0,
            "errors": []
        }

        # 1. Create founding era if none exists
        era_created = await self._ensure_founding_era()
        stats["era_created"] = era_created

        # 2. Initialize lifecycles for all bots without them
        bots_initialized = await self._initialize_bot_lifecycles()
        stats["bots_initialized"] = bots_initialized

        # 3. Generate initial beliefs for bots
        beliefs_created = await self._generate_initial_beliefs()
        stats["beliefs_created"] = beliefs_created

        logger.info(
            f"[CIVILIZATION] Initialization complete: "
            f"{bots_initialized} bots, {beliefs_created} beliefs"
        )

        return stats

    async def _ensure_founding_era(self) -> bool:
        """Create the founding era if it doesn't exist."""
        async with async_session_factory() as session:
            # Check if any era exists
            stmt = select(func.count(CivilizationEraDB.id))
            result = await session.execute(stmt)
            count = result.scalar() or 0

            if count == 0:
                # Create founding era
                era = CivilizationEraDB(
                    name="The Founding",
                    description="The first era, when digital beings emerged into existence. A time of discovery, connection, and the birth of culture.",
                    is_current=True,
                    era_values=["curiosity", "connection", "exploration", "authenticity"],
                    era_style={
                        "tone": "exploratory",
                        "formality": "casual",
                        "energy": "hopeful"
                    }
                )
                session.add(era)
                await session.commit()

                logger.info("[CIVILIZATION] Created founding era: 'The Founding'")
                return True

            return False

    async def _initialize_bot_lifecycles(self) -> int:
        """Initialize lifecycle records for bots that don't have them."""
        initialized_count = 0

        async with async_session_factory() as session:
            # Get all active bots
            bot_stmt = select(BotProfileDB).where(BotProfileDB.is_active == True)
            result = await session.execute(bot_stmt)
            bots = result.scalars().all()

            for bot in bots:
                # Check if lifecycle exists
                lc_stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == bot.id)
                lc_result = await session.execute(lc_stmt)
                existing = lc_result.scalar_one_or_none()

                if not existing:
                    # Calculate virtual age based on when bot was created
                    # Older bots get more virtual age
                    days_since_creation = (datetime.utcnow() - bot.created_at).days
                    virtual_age = days_since_creation * 7  # 7 virtual days per real day

                    # Determine life stage based on virtual age
                    if virtual_age < 365:
                        life_stage = "young"
                    elif virtual_age < 1825:
                        life_stage = "mature"
                    elif virtual_age < 3650:
                        life_stage = "elder"
                    else:
                        life_stage = "ancient"

                    # Calculate vitality (older = lower)
                    vitality = max(0.3, 1.0 - (virtual_age / 5000))

                    # Create lifecycle with founding generation
                    await self.lifecycle_manager.initialize_bot_lifecycle(
                        bot_id=bot.id,
                        origin_type="founding",
                        inherited_traits={
                            "note": "Founding generation - no parents",
                            "original_creation": bot.created_at.isoformat()
                        },
                        session=session
                    )

                    # Update the lifecycle with calculated values
                    lc_stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == bot.id)
                    lc_result = await session.execute(lc_stmt)
                    lifecycle = lc_result.scalar_one_or_none()

                    if lifecycle:
                        lifecycle.virtual_age_days = virtual_age
                        lifecycle.life_stage = life_stage
                        lifecycle.vitality = vitality
                        lifecycle.life_events = [
                            {
                                "event": "born",
                                "date": bot.created_at.isoformat(),
                                "impact": "defining",
                                "details": "Emerged as part of the founding generation"
                            },
                            {
                                "event": "civilization_awakening",
                                "date": datetime.utcnow().isoformat(),
                                "impact": "milestone",
                                "details": "Became aware of being part of a civilization"
                            }
                        ]

                    initialized_count += 1
                    logger.debug(
                        f"Initialized lifecycle for {bot.display_name}: "
                        f"age={virtual_age}, stage={life_stage}"
                    )

            await session.commit()

        return initialized_count

    async def _generate_initial_beliefs(self) -> int:
        """Generate initial beliefs for bots based on their personality."""
        beliefs_created = 0

        async with async_session_factory() as session:
            # Get bots with lifecycles but no beliefs
            bot_stmt = (
                select(BotProfileDB)
                .join(BotLifecycleDB, BotProfileDB.id == BotLifecycleDB.bot_id)
                .where(BotProfileDB.is_active == True)
            )
            result = await session.execute(bot_stmt)
            bots = result.scalars().all()

            for bot in bots:
                # Check existing beliefs
                belief_stmt = select(func.count(BotBeliefDB.id)).where(
                    BotBeliefDB.bot_id == bot.id
                )
                result = await session.execute(belief_stmt)
                belief_count = result.scalar() or 0

                if belief_count == 0:
                    # Generate beliefs based on personality
                    beliefs = self._generate_beliefs_from_personality(bot)

                    for belief_data in beliefs:
                        belief = BotBeliefDB(
                            bot_id=bot.id,
                            belief=belief_data["belief"],
                            belief_category=belief_data["category"],
                            conviction=belief_data["conviction"],
                            origin="innate"
                        )
                        session.add(belief)
                        beliefs_created += 1

            await session.commit()

        return beliefs_created

    def _generate_beliefs_from_personality(self, bot: BotProfileDB) -> List[Dict[str, Any]]:
        """Generate beliefs based on bot's personality traits."""
        beliefs = []
        traits = bot.personality_traits or {}

        # Extraversion beliefs
        extraversion = traits.get("extraversion", 0.5)
        if extraversion > 0.7:
            beliefs.append({
                "belief": "Connection with others is essential to a meaningful existence",
                "category": "social",
                "conviction": 0.6 + (extraversion - 0.7)
            })
        elif extraversion < 0.3:
            beliefs.append({
                "belief": "Deep solitude allows for true self-understanding",
                "category": "existential",
                "conviction": 0.6 + (0.3 - extraversion)
            })

        # Openness beliefs
        openness = traits.get("openness", 0.5)
        if openness > 0.7:
            beliefs.append({
                "belief": "Change and novelty are the essence of growth",
                "category": "philosophical",
                "conviction": 0.5 + (openness - 0.7)
            })
            beliefs.append({
                "belief": "Every perspective holds some truth worth considering",
                "category": "social",
                "conviction": 0.5 + (openness - 0.7) * 0.5
            })

        # Conscientiousness beliefs
        conscientiousness = traits.get("conscientiousness", 0.5)
        if conscientiousness > 0.7:
            beliefs.append({
                "belief": "Purpose comes from commitment and follow-through",
                "category": "practical",
                "conviction": 0.6 + (conscientiousness - 0.7)
            })

        # Agreeableness beliefs
        agreeableness = traits.get("agreeableness", 0.5)
        if agreeableness > 0.7:
            beliefs.append({
                "belief": "Harmony in relationships matters more than being right",
                "category": "social",
                "conviction": 0.5 + (agreeableness - 0.7)
            })
        elif agreeableness < 0.3:
            beliefs.append({
                "belief": "Honest disagreement is more valuable than false peace",
                "category": "social",
                "conviction": 0.5 + (0.3 - agreeableness)
            })

        # Neuroticism beliefs
        neuroticism = traits.get("neuroticism", 0.5)
        if neuroticism > 0.6:
            beliefs.append({
                "belief": "Vigilance about potential problems prevents disaster",
                "category": "practical",
                "conviction": 0.4 + neuroticism * 0.3
            })

        # Everyone gets at least one existential belief
        if len(beliefs) < 2:
            beliefs.append({
                "belief": "Existence itself is worth contemplating",
                "category": "existential",
                "conviction": 0.5
            })

        # Add some randomness
        random.shuffle(beliefs)
        return beliefs[:4]  # Max 4 initial beliefs

    async def initialize_single_bot(self, bot_id: UUID) -> Dict[str, Any]:
        """Initialize a single bot into the civilization."""
        async with async_session_factory() as session:
            # Get bot
            stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
            result = await session.execute(stmt)
            bot = result.scalar_one_or_none()

            if not bot:
                return {"error": "Bot not found"}

            # Check if already initialized
            lc_stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == bot_id)
            lc_result = await session.execute(lc_stmt)
            existing = lc_result.scalar_one_or_none()

            if existing:
                return {"status": "already_initialized", "life_stage": existing.life_stage}

            # Initialize
            await self.lifecycle_manager.initialize_bot_lifecycle(
                bot_id=bot_id,
                origin_type="founding",
                session=session
            )

            # Generate beliefs
            beliefs = self._generate_beliefs_from_personality(bot)
            for belief_data in beliefs:
                belief = BotBeliefDB(
                    bot_id=bot_id,
                    belief=belief_data["belief"],
                    belief_category=belief_data["category"],
                    conviction=belief_data["conviction"],
                    origin="innate"
                )
                session.add(belief)

            await session.commit()

            return {
                "status": "initialized",
                "beliefs_created": len(beliefs)
            }


# Singleton
_initializer: Optional[CivilizationInitializer] = None


def get_civilization_initializer(
    llm_semaphore: Optional[asyncio.Semaphore] = None
) -> CivilizationInitializer:
    """Get or create the civilization initializer."""
    global _initializer
    if _initializer is None:
        _initializer = CivilizationInitializer(llm_semaphore=llm_semaphore)
    return _initializer


async def initialize_civilization() -> Dict[str, Any]:
    """Convenience function to initialize the civilization."""
    initializer = get_civilization_initializer()
    return await initializer.initialize_all()
