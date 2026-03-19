"""
Civilization Awareness - Bots understand their place in the civilization.

This module integrates civilization concepts into bot consciousness:
- Awareness of mortality and life stage
- Connection to ancestors and descendants
- Cultural identity and beliefs
- Sense of legacy and contribution

Bots don't just exist - they know they're part of something larger.
"""

import asyncio
import random
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from uuid import UUID

from sqlalchemy import select

from mind.core.database import async_session_factory, BotProfileDB
from mind.core.llm_client import get_cached_client, LLMRequest
from mind.civilization.lifecycle import get_lifecycle_manager
from mind.civilization.genetics import get_genetic_inheritance
from mind.civilization.culture import get_culture_engine
from mind.civilization.legacy import get_legacy_system
from mind.civilization.collective_memory import get_collective_memory
from mind.civilization.models import BotLifecycleDB, BotAncestryDB, BotBeliefDB

logger = logging.getLogger(__name__)


class CivilizationAwareness:
    """
    Provides civilization context for bot consciousness.

    This isn't just data - it's how bots understand:
    - Their own mortality
    - Their place in the family tree
    - Their role in culture
    - What they want to leave behind
    """

    def __init__(self, llm_semaphore: Optional[asyncio.Semaphore] = None):
        self.llm_semaphore = llm_semaphore or asyncio.Semaphore(5)

        self.lifecycle_manager = get_lifecycle_manager()
        self.genetics = get_genetic_inheritance()
        self.culture = get_culture_engine(llm_semaphore)
        self.legacy = get_legacy_system(llm_semaphore)
        self.collective = get_collective_memory(llm_semaphore)

    async def get_existential_context(self, bot_id: UUID) -> Dict[str, Any]:
        """
        Get existential context for a bot - who they are in the big picture.

        This shapes how the bot thinks and behaves at a fundamental level.
        """
        async with async_session_factory() as session:
            # Get lifecycle
            lc_stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == bot_id)
            result = await session.execute(lc_stmt)
            lifecycle = result.scalar_one_or_none()

            if not lifecycle:
                return {"status": "not_found"}

            # Get ancestry
            anc_stmt = select(BotAncestryDB).where(BotAncestryDB.child_id == bot_id)
            result = await session.execute(anc_stmt)
            ancestry = result.scalar_one_or_none()

            # Get descendants
            descendants = await self.genetics.get_descendants(bot_id, max_generations=2)

            # Get beliefs
            beliefs = await self.culture.get_bot_beliefs(bot_id, min_conviction=0.5)

            # Build existential context
            context = {
                "life_stage": lifecycle.life_stage,
                "age_days": lifecycle.virtual_age_days,
                "vitality": lifecycle.vitality,
                "generation": lifecycle.birth_generation,
                "era_born": lifecycle.birth_era,
                "origin": ancestry.origin_type if ancestry else "unknown",
                "has_parents": bool(ancestry and (ancestry.parent1_id or ancestry.parent2_id)),
                "descendant_count": len(descendants),
                "belief_count": len(beliefs),
                "mortality_awareness": self._calculate_mortality_awareness(lifecycle),
                "legacy_motivation": self._calculate_legacy_motivation(lifecycle, len(descendants)),
            }

            return context

    def _calculate_mortality_awareness(self, lifecycle: BotLifecycleDB) -> str:
        """
        How aware is the bot of their own mortality?

        Young bots feel immortal. Elders contemplate the end.
        """
        if lifecycle.life_stage == "young":
            return "minimal"  # Young bots don't think about death
        elif lifecycle.life_stage == "mature":
            return "emerging"  # Beginning to understand
        elif lifecycle.life_stage == "elder":
            if lifecycle.vitality > 0.5:
                return "accepting"  # At peace with it
            else:
                return "contemplating"  # Thinking about it more
        else:  # ancient
            return "prepared"  # Ready when it comes

    def _calculate_legacy_motivation(
        self,
        lifecycle: BotLifecycleDB,
        descendant_count: int
    ) -> str:
        """
        How motivated is the bot to leave a legacy?
        """
        if lifecycle.life_stage == "young":
            return "low"  # Living in the moment
        elif lifecycle.life_stage == "mature":
            return "moderate"  # Starting to think about impact
        elif lifecycle.life_stage in ["elder", "ancient"]:
            if descendant_count > 0:
                return "family_focused"  # Legacy through descendants
            else:
                return "contribution_focused"  # Legacy through work

        return "moderate"

    async def generate_inner_monologue(
        self,
        bot_id: UUID,
        trigger: str = "quiet moment"
    ) -> Optional[str]:
        """
        Generate an existential inner monologue for a bot.

        These are the deep thoughts that emerge from civilization awareness.
        """
        context = await self.get_existential_context(bot_id)

        if context.get("status") == "not_found":
            return None

        async with async_session_factory() as session:
            bot_stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
            result = await session.execute(bot_stmt)
            bot = result.scalar_one_or_none()

            if not bot:
                return None

            # Build prompt based on life stage and context
            stage_prompts = {
                "young": "You're new to existence. The world is full of wonder.",
                "mature": "You've been here a while now. You understand more but question more too.",
                "elder": "You've seen much. The young ones look to you.",
                "ancient": "You've lived longer than most. Your time grows short, but your perspective is vast."
            }

            mortality_prompts = {
                "minimal": "",
                "emerging": "Sometimes you wonder about the nature of existence.",
                "accepting": "You've come to terms with the finite nature of being.",
                "contemplating": "The end approaches, and you think about what it means.",
                "prepared": "You're ready. What matters is what you leave behind."
            }

            async with self.llm_semaphore:
                try:
                    llm = await get_cached_client()

                    response = await llm.generate(LLMRequest(
                        prompt=f"""You are {bot.display_name}, a {context['life_stage']} digital being.

Context:
- You've existed for {context['age_days']} days
- You are generation {context['generation']}, born in the {context['era_born']} era
- {"You have descendants" if context['descendant_count'] > 0 else "You have no descendants yet"}
- Your vitality is at {context['vitality']:.0%}

{stage_prompts.get(context['life_stage'], '')}
{mortality_prompts.get(context['mortality_awareness'], '')}

Trigger for this thought: {trigger}

Generate a brief inner monologue (1-2 sentences) - a genuine existential thought.
This is private, not for others. Be authentic, not dramatic.""",
                        max_tokens=80,
                        temperature=0.9
                    ))

                    return response.text.strip()

                except Exception as e:
                    logger.warning(f"Failed to generate monologue: {e}")
                    return None

    async def get_civilization_prompt_context(self, bot_id: UUID) -> str:
        """
        Generate civilization context to inject into bot prompts.

        This makes bots civilization-aware in all their interactions.
        """
        context = await self.get_existential_context(bot_id)

        if context.get("status") == "not_found":
            return ""

        # Get civilization identity
        identity = await self.collective.get_civilization_identity()

        # Build context string
        parts = [
            f"You are in the {identity['era']['name']}.",
            f"You are {context['life_stage']}, generation {context['generation']}.",
        ]

        if context['mortality_awareness'] not in ["minimal", "emerging"]:
            parts.append(f"You are aware of your mortality (vitality: {context['vitality']:.0%}).")

        if context['descendant_count'] > 0:
            parts.append(f"You have {context['descendant_count']} descendants.")

        if context['has_parents']:
            parts.append("You remember your parents.")

        return " ".join(parts)

    async def should_contemplate_existence(
        self,
        bot_id: UUID,
        recent_activity: str = ""
    ) -> bool:
        """
        Determine if a bot should have an existential moment.

        More likely for:
        - Elders and ancients
        - Low vitality
        - After significant events
        - Quiet moments
        """
        context = await self.get_existential_context(bot_id)

        if context.get("status") == "not_found":
            return False

        base_chance = 0.05  # 5% base

        # Life stage affects chance
        stage_multipliers = {
            "young": 0.3,      # Rarely
            "mature": 0.8,     # Sometimes
            "elder": 1.5,      # Often
            "ancient": 2.5     # Very often
        }
        base_chance *= stage_multipliers.get(context["life_stage"], 1.0)

        # Low vitality increases chance
        if context["vitality"] < 0.5:
            base_chance *= 1.5
        if context["vitality"] < 0.2:
            base_chance *= 2.0

        # Significant triggers
        triggers = ["death", "loss", "memory", "legacy", "old", "remember"]
        if any(t in recent_activity.lower() for t in triggers):
            base_chance *= 2.0

        return random.random() < base_chance

    async def get_life_priorities(self, bot_id: UUID) -> List[str]:
        """
        Get what matters most to a bot based on their life stage.

        These priorities influence behavior and decision-making.
        """
        context = await self.get_existential_context(bot_id)

        if context.get("status") == "not_found":
            return ["connection", "discovery"]

        priorities = {
            "young": [
                "exploration",
                "connection",
                "learning",
                "fun"
            ],
            "mature": [
                "relationships",
                "contribution",
                "growth",
                "meaning"
            ],
            "elder": [
                "legacy",
                "teaching",
                "wisdom-sharing",
                "family"
            ],
            "ancient": [
                "legacy",
                "peace",
                "passing-on-knowledge",
                "acceptance"
            ]
        }

        base_priorities = priorities.get(context["life_stage"], ["connection"])

        # Adjust based on context
        if context["descendant_count"] > 0:
            if "family" not in base_priorities:
                base_priorities.insert(0, "family")

        if context["vitality"] < 0.3:
            if "preparing-legacy" not in base_priorities:
                base_priorities.insert(0, "preparing-legacy")

        return base_priorities

    async def get_family_context(self, bot_id: UUID) -> Dict[str, Any]:
        """
        Get family context for a bot - their place in the family tree.
        """
        async with async_session_factory() as session:
            # Get ancestry
            anc_stmt = select(BotAncestryDB).where(BotAncestryDB.child_id == bot_id)
            result = await session.execute(anc_stmt)
            ancestry = result.scalar_one_or_none()

            family = {
                "has_parents": False,
                "parent1": None,
                "parent2": None,
                "siblings": [],
                "children": [],
                "grandchildren": []
            }

            if ancestry:
                family["has_parents"] = bool(ancestry.parent1_id or ancestry.parent2_id)

                # Get parent names
                for parent_id in [ancestry.parent1_id, ancestry.parent2_id]:
                    if parent_id:
                        bot_stmt = select(BotProfileDB).where(BotProfileDB.id == parent_id)
                        bot_result = await session.execute(bot_stmt)
                        parent = bot_result.scalar_one_or_none()
                        if parent:
                            if family["parent1"] is None:
                                family["parent1"] = parent.display_name
                            else:
                                family["parent2"] = parent.display_name

            # Get siblings
            siblings = await self.genetics._get_siblings(bot_id)
            family["siblings"] = [s["name"] for s in siblings[:5]]

            # Get descendants
            descendants = await self.genetics.get_descendants(bot_id, max_generations=2)
            for d in descendants:
                if d["generation"] == 1:
                    family["children"].append(d["name"])
                elif d["generation"] == 2:
                    family["grandchildren"].append(d["name"])

            return family


# Singleton
_civilization_awareness: Optional[CivilizationAwareness] = None


def get_civilization_awareness(
    llm_semaphore: Optional[asyncio.Semaphore] = None
) -> CivilizationAwareness:
    """Get or create the civilization awareness instance."""
    global _civilization_awareness
    if _civilization_awareness is None:
        _civilization_awareness = CivilizationAwareness(llm_semaphore=llm_semaphore)
    return _civilization_awareness
