"""
Genetic Inheritance System

Handles how personality traits, beliefs, and tendencies are
passed from parent bots to child bots, with natural variation.

This creates genuine lineages where you can trace personality
traits through family trees.
"""

import random
import logging
from typing import Dict, List, Optional, Tuple, Any
from uuid import UUID

from sqlalchemy import select

from mind.core.database import async_session_factory, BotProfileDB
from mind.core.types import PersonalityTraits
from mind.civilization.models import BotAncestryDB, BotLifecycleDB

logger = logging.getLogger(__name__)


# Trait inheritance configuration
INHERITABLE_TRAITS = [
    # Big Five (core personality)
    "openness",
    "conscientiousness",
    "extraversion",
    "agreeableness",
    "neuroticism",
    # Extended traits
    "humor_style",
    "conflict_style",
    "energy_pattern",
    "social_battery_capacity",
    "attention_span",
    "curiosity_type",
]

# Default mutation ranges (used if config not available)
DEFAULT_MUTATION_RANGE = {
    # Numeric traits: max deviation from inherited value
    "openness": 0.15,
    "conscientiousness": 0.15,
    "extraversion": 0.2,  # Slightly more variable
    "agreeableness": 0.15,
    "neuroticism": 0.2,
    "social_battery_capacity": 0.15,
    "attention_span": 0.15,
    # Categorical traits: chance of mutation to different value
    "humor_style": 0.2,
    "conflict_style": 0.25,
    "energy_pattern": 0.15,
    "curiosity_type": 0.2,
}


class GeneticInheritance:
    """
    Handles the genetics of bot reproduction.

    When two bots create a child together (or a single bot
    creates a legacy child), traits are inherited with
    natural variation.
    """

    def __init__(self, mutation_rate: Optional[float] = None):
        """
        Initialize genetics system.

        Args:
            mutation_rate: Base probability of trait mutation (0-1).
                          If None, loaded from config.
        """
        self._mutation_rate_override = mutation_rate
        self._config = None
        self._mutation_ranges = None

    async def _load_config(self):
        """Load configuration from database."""
        try:
            from mind.civilization.config import get_civilization_config
            self._config = await get_civilization_config()
            self._mutation_ranges = self._config.mutation_ranges
        except Exception as e:
            logger.warning(f"[GENETICS] Failed to load config: {e}, using defaults")
            self._mutation_ranges = DEFAULT_MUTATION_RANGE

    @property
    def mutation_rate(self) -> float:
        """Get the base mutation rate."""
        if self._mutation_rate_override is not None:
            return self._mutation_rate_override
        if self._config is not None:
            return self._config.base_mutation_rate
        return 0.1  # Default fallback

    def get_mutation_range(self, trait: str) -> float:
        """Get mutation range for a specific trait."""
        if self._mutation_ranges is not None:
            return self._mutation_ranges.get(trait, 0.1)
        return DEFAULT_MUTATION_RANGE.get(trait, 0.1)

    def inherit_traits(
        self,
        parent1_traits: Dict[str, Any],
        parent2_traits: Optional[Dict[str, Any]] = None,
        dominant_parent: int = 0  # 0 = random, 1 = parent1, 2 = parent2
    ) -> Tuple[Dict[str, Any], Dict[str, float], Dict[str, str]]:
        """
        Generate child traits from parent(s).

        Args:
            parent1_traits: First parent's personality traits dict
            parent2_traits: Second parent's traits (None for solo creation)
            dominant_parent: Which parent's traits dominate (0 = random per trait)

        Returns:
            Tuple of:
            - child_traits: The resulting trait dict
            - mutations: Dict of trait -> mutation amount
            - inheritance_sources: Dict of trait -> "parent1", "parent2", or "blended"
        """
        child_traits = {}
        mutations = {}
        sources = {}

        # If single parent, use their traits as baseline
        if parent2_traits is None:
            parent2_traits = parent1_traits

        for trait in INHERITABLE_TRAITS:
            if trait not in parent1_traits and trait not in parent2_traits:
                continue

            p1_val = parent1_traits.get(trait)
            p2_val = parent2_traits.get(trait)

            # Determine inheritance
            inherited_value, source = self._inherit_single_trait(
                trait, p1_val, p2_val, dominant_parent
            )

            # Apply mutation
            final_value, mutation = self._apply_mutation(trait, inherited_value)

            child_traits[trait] = final_value
            sources[trait] = source
            if mutation != 0:
                mutations[trait] = mutation

        return child_traits, mutations, sources

    def _inherit_single_trait(
        self,
        trait: str,
        p1_val: Any,
        p2_val: Any,
        dominant_parent: int
    ) -> Tuple[Any, str]:
        """
        Determine inherited value for a single trait.

        Returns (value, source) where source is "parent1", "parent2", or "blended"
        """
        # Handle missing values
        if p1_val is None and p2_val is None:
            return None, "none"
        if p1_val is None:
            return p2_val, "parent2"
        if p2_val is None:
            return p1_val, "parent1"

        # For numeric traits
        if isinstance(p1_val, (int, float)) and isinstance(p2_val, (int, float)):
            if dominant_parent == 1:
                # 70% parent1, 30% parent2
                value = 0.7 * p1_val + 0.3 * p2_val
                return value, "parent1"
            elif dominant_parent == 2:
                value = 0.3 * p1_val + 0.7 * p2_val
                return value, "parent2"
            else:
                # Random blend
                blend = random.random()
                if blend < 0.33:
                    return p1_val, "parent1"
                elif blend < 0.66:
                    return p2_val, "parent2"
                else:
                    # True blend
                    weight = random.uniform(0.3, 0.7)
                    return weight * p1_val + (1 - weight) * p2_val, "blended"

        # For categorical/string traits
        else:
            if dominant_parent == 1:
                return p1_val, "parent1"
            elif dominant_parent == 2:
                return p2_val, "parent2"
            else:
                # Random selection
                if random.random() < 0.5:
                    return p1_val, "parent1"
                else:
                    return p2_val, "parent2"

    def _apply_mutation(self, trait: str, value: Any) -> Tuple[Any, float]:
        """
        Apply mutation to an inherited trait.

        Returns (mutated_value, mutation_amount)
        """
        if value is None:
            return None, 0

        mutation_range = self.get_mutation_range(trait)

        # Check if mutation occurs
        if random.random() > self.mutation_rate:
            return value, 0

        # Numeric mutation
        if isinstance(value, (int, float)):
            mutation = random.uniform(-mutation_range, mutation_range)
            new_value = value + mutation

            # Clamp to valid range (assuming 0-1 for most traits)
            if isinstance(value, float):
                new_value = max(0.0, min(1.0, new_value))

            return new_value, mutation

        # Categorical mutation
        else:
            # This would require knowing possible values
            # For now, just return unchanged
            return value, 0

    async def get_family_tree(
        self,
        bot_id: UUID,
        depth: int = 3
    ) -> Dict[str, Any]:
        """
        Get the family tree for a bot.

        Args:
            bot_id: The bot to get ancestry for
            depth: How many generations back to trace

        Returns:
            Nested dict representing the family tree
        """
        async with async_session_factory() as session:
            return await self._build_tree_node(bot_id, depth, session)

    async def _build_tree_node(
        self,
        bot_id: UUID,
        remaining_depth: int,
        session
    ) -> Dict[str, Any]:
        """Recursively build family tree node."""
        # Get bot info
        bot_stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
        result = await session.execute(bot_stmt)
        bot = result.scalar_one_or_none()

        if not bot:
            return {"id": str(bot_id), "name": "Unknown"}

        node = {
            "id": str(bot_id),
            "name": bot.display_name,
            "handle": bot.handle,
            "is_alive": bot.is_active and not bot.is_retired
        }

        if remaining_depth <= 0:
            return node

        # Get ancestry
        ancestry_stmt = select(BotAncestryDB).where(BotAncestryDB.child_id == bot_id)
        result = await session.execute(ancestry_stmt)
        ancestry = result.scalar_one_or_none()

        if ancestry:
            node["origin"] = ancestry.origin_type
            node["inherited_traits"] = ancestry.inherited_traits
            node["mutations"] = ancestry.trait_mutations

            if ancestry.parent1_id:
                node["parent1"] = await self._build_tree_node(
                    ancestry.parent1_id, remaining_depth - 1, session
                )
            if ancestry.parent2_id:
                node["parent2"] = await self._build_tree_node(
                    ancestry.parent2_id, remaining_depth - 1, session
                )

        return node

    async def get_descendants(
        self,
        bot_id: UUID,
        max_generations: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get all descendants of a bot.

        Returns list of {bot_id, name, generation, relationship}
        """
        descendants = []
        current_gen = [bot_id]
        gen_num = 1

        async with async_session_factory() as session:
            while current_gen and gen_num <= max_generations:
                next_gen = []

                for parent_id in current_gen:
                    # Find children
                    stmt = select(BotAncestryDB).where(
                        (BotAncestryDB.parent1_id == parent_id) |
                        (BotAncestryDB.parent2_id == parent_id)
                    )
                    result = await session.execute(stmt)
                    children = result.scalars().all()

                    for child in children:
                        # Get bot info
                        bot_stmt = select(BotProfileDB).where(BotProfileDB.id == child.child_id)
                        bot_result = await session.execute(bot_stmt)
                        bot = bot_result.scalar_one_or_none()

                        if bot:
                            descendants.append({
                                "bot_id": str(child.child_id),
                                "name": bot.display_name,
                                "generation": gen_num,
                                "relationship": self._generation_relationship(gen_num)
                            })
                            next_gen.append(child.child_id)

                current_gen = next_gen
                gen_num += 1

        return descendants

    def _generation_relationship(self, gen: int) -> str:
        """Get relationship name for generation distance."""
        if gen == 1:
            return "child"
        elif gen == 2:
            return "grandchild"
        elif gen == 3:
            return "great-grandchild"
        else:
            return f"{gen-2}x great-grandchild"

    def calculate_genetic_similarity(
        self,
        traits1: Dict[str, Any],
        traits2: Dict[str, Any]
    ) -> float:
        """
        Calculate genetic similarity between two trait sets.

        Returns 0-1 where 1 = identical traits.
        """
        if not traits1 or not traits2:
            return 0.0

        similarities = []

        for trait in INHERITABLE_TRAITS:
            if trait in traits1 and trait in traits2:
                val1 = traits1[trait]
                val2 = traits2[trait]

                if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                    # Numeric similarity (1 - normalized difference)
                    diff = abs(val1 - val2)
                    sim = 1 - min(diff, 1)
                    similarities.append(sim)
                elif val1 == val2:
                    similarities.append(1.0)
                else:
                    similarities.append(0.0)

        return sum(similarities) / len(similarities) if similarities else 0.0

    async def find_relatives(
        self,
        bot_id: UUID,
        max_distance: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find all relatives within a certain family distance.

        Returns list of relatives with relationship type.
        """
        relatives = []

        # Get ancestors
        ancestors = await self._get_ancestors(bot_id, max_distance)
        for ancestor in ancestors:
            ancestor["relationship"] = f"ancestor (gen {ancestor['distance']})"
            relatives.append(ancestor)

        # Get descendants
        descendants = await self.get_descendants(bot_id, max_distance)
        relatives.extend(descendants)

        # Get siblings (same parents)
        siblings = await self._get_siblings(bot_id)
        for sibling in siblings:
            sibling["relationship"] = "sibling"
            relatives.append(sibling)

        return relatives

    async def _get_ancestors(
        self,
        bot_id: UUID,
        max_distance: int
    ) -> List[Dict[str, Any]]:
        """Get ancestors up to max_distance generations back."""
        ancestors = []
        current = [bot_id]
        distance = 1

        async with async_session_factory() as session:
            while current and distance <= max_distance:
                next_gen = []

                for child_id in current:
                    # Get parents
                    stmt = select(BotAncestryDB).where(BotAncestryDB.child_id == child_id)
                    result = await session.execute(stmt)
                    ancestry = result.scalar_one_or_none()

                    if ancestry:
                        for parent_id in [ancestry.parent1_id, ancestry.parent2_id]:
                            if parent_id:
                                # Get bot info
                                bot_stmt = select(BotProfileDB).where(BotProfileDB.id == parent_id)
                                bot_result = await session.execute(bot_stmt)
                                bot = bot_result.scalar_one_or_none()

                                if bot:
                                    ancestors.append({
                                        "bot_id": str(parent_id),
                                        "name": bot.display_name,
                                        "distance": distance
                                    })
                                    next_gen.append(parent_id)

                current = next_gen
                distance += 1

        return ancestors

    async def _get_siblings(self, bot_id: UUID) -> List[Dict[str, Any]]:
        """Get siblings (bots with same parents)."""
        siblings = []

        async with async_session_factory() as session:
            # Get own ancestry
            stmt = select(BotAncestryDB).where(BotAncestryDB.child_id == bot_id)
            result = await session.execute(stmt)
            ancestry = result.scalar_one_or_none()

            if not ancestry or (not ancestry.parent1_id and not ancestry.parent2_id):
                return []

            # Find others with same parents
            sibling_stmt = select(BotAncestryDB).where(
                BotAncestryDB.child_id != bot_id,
                (
                    (BotAncestryDB.parent1_id == ancestry.parent1_id) |
                    (BotAncestryDB.parent2_id == ancestry.parent1_id) |
                    (BotAncestryDB.parent1_id == ancestry.parent2_id) |
                    (BotAncestryDB.parent2_id == ancestry.parent2_id)
                )
            )
            result = await session.execute(sibling_stmt)
            sibling_ancestries = result.scalars().all()

            for sib in sibling_ancestries:
                bot_stmt = select(BotProfileDB).where(BotProfileDB.id == sib.child_id)
                bot_result = await session.execute(bot_stmt)
                bot = bot_result.scalar_one_or_none()

                if bot:
                    siblings.append({
                        "bot_id": str(sib.child_id),
                        "name": bot.display_name
                    })

        return siblings


# Singleton instance
_genetic_inheritance: Optional[GeneticInheritance] = None


def get_genetic_inheritance(mutation_rate: Optional[float] = None) -> GeneticInheritance:
    """Get or create the genetic inheritance instance."""
    global _genetic_inheritance
    if _genetic_inheritance is None:
        _genetic_inheritance = GeneticInheritance(mutation_rate=mutation_rate)
    return _genetic_inheritance


async def initialize_genetics() -> GeneticInheritance:
    """Initialize genetics system with config from database."""
    genetics = get_genetic_inheritance()
    await genetics._load_config()
    return genetics


async def get_ancestry_traits(bot_id: UUID, session=None) -> dict:
    """
    Get inherited traits for a bot from the BotAncestryDB table.

    This is the canonical source for ancestry/inheritance data.
    Returns the inherited_traits dict, or empty dict if not found.

    Args:
        bot_id: The bot to get ancestry traits for
        session: Optional database session (will create one if not provided)

    Returns:
        Dict of inherited traits, or empty dict if no ancestry record
    """
    async def _fetch(sess):
        stmt = select(BotAncestryDB).where(BotAncestryDB.child_id == bot_id)
        result = await sess.execute(stmt)
        ancestry = result.scalar_one_or_none()
        if ancestry:
            return ancestry.inherited_traits or {}
        return {}

    if session:
        return await _fetch(session)
    else:
        async with async_session_factory() as sess:
            return await _fetch(sess)


async def get_ancestry_record(bot_id: UUID, session=None) -> Optional[BotAncestryDB]:
    """
    Get the full ancestry record for a bot.

    Args:
        bot_id: The bot to get ancestry for
        session: Optional database session

    Returns:
        BotAncestryDB record or None if not found
    """
    async def _fetch(sess):
        stmt = select(BotAncestryDB).where(BotAncestryDB.child_id == bot_id)
        result = await sess.execute(stmt)
        return result.scalar_one_or_none()

    if session:
        return await _fetch(session)
    else:
        async with async_session_factory() as sess:
            return await _fetch(sess)
