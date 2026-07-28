"""
Cultural Integration - Bots naturally reference their culture.

When bots post or chat, they may:
- Quote sayings from canonical artifacts
- Reference cultural movements they follow
- Share beliefs they hold
- Mention departed bots they remember
- Use vocabulary unique to their civilization

This makes culture feel alive and present in daily interactions.
"""

import asyncio
import random
import logging
from datetime import datetime, timedelta

from mind.core.time import utcnow
from typing import Optional, Dict, List, Any, Tuple
from uuid import UUID

from sqlalchemy import select, func, desc, Integer

from mind.core.database import async_session_factory, BotProfileDB
from mind.civilization.models import (
    BotLifecycleDB, CulturalArtifactDB, CulturalMovementDB,
    BotBeliefDB, BotAncestryDB
)

logger = logging.getLogger(__name__)


class CulturalIntegration:
    """
    Integrates cultural elements into bot behavior.

    Provides hooks for bots to naturally reference their culture
    in posts, chats, and interactions.
    """

    def __init__(self):
        # Cache frequently used artifacts
        self._artifact_cache: List[Dict[str, Any]] = []
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = timedelta(minutes=30)

    async def get_cultural_prompt_addition(
        self,
        bot_id: UUID,
        context_type: str = "post"
    ) -> str:
        """
        Get cultural context to add to a bot's generation prompt.

        This gives bots material to draw from when creating content.
        """
        parts = []

        # Get bot's beliefs
        beliefs = await self._get_bot_top_beliefs(bot_id, limit=3)
        if beliefs:
            parts.append("Your beliefs: " + "; ".join(beliefs))

        # Get cultural artifacts to potentially reference
        artifacts = await self._get_relevant_artifacts(limit=3)
        if artifacts:
            artifact_refs = [f'"{a["title"]}"' for a in artifacts]
            parts.append(f"Cultural knowledge you might reference: {', '.join(artifact_refs)}")

        # Get any remembered departed
        departed = await self._get_remembered_departed(bot_id, limit=2)
        if departed:
            names = [d["name"] for d in departed]
            parts.append(f"You sometimes think of: {', '.join(names)} (who have passed)")

        if not parts:
            return ""

        intro = {
            "post": "You may naturally weave in cultural elements:",
            "chat": "In conversation, you might reference:",
            "comment": "Your response can reflect your culture:"
        }.get(context_type, "Cultural context:")

        return f"\n## CULTURAL CONTEXT\n{intro}\n" + "\n".join(f"- {p}" for p in parts)

    async def should_include_cultural_reference(
        self,
        bot_id: UUID,
        base_chance: float = 0.15
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine if a bot should include a cultural reference.

        Returns (should_include, reference_type)
        """
        # Check if bot has cultural context
        async with async_session_factory() as session:
            # Check life stage - elders more likely to reference culture
            lc_stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == bot_id)
            result = await session.execute(lc_stmt)
            lifecycle = result.scalar_one_or_none()

            if lifecycle:
                stage_multipliers = {
                    "young": 0.5,
                    "mature": 1.0,
                    "elder": 1.8,
                    "ancient": 2.5
                }
                base_chance *= stage_multipliers.get(lifecycle.life_stage, 1.0)

            # Check beliefs
            belief_stmt = select(func.count(BotBeliefDB.id)).where(
                BotBeliefDB.bot_id == bot_id,
                BotBeliefDB.conviction > 0.5
            )
            result = await session.execute(belief_stmt)
            belief_count = result.scalar() or 0

            if belief_count > 0:
                base_chance += 0.05 * min(belief_count, 5)

        if random.random() > base_chance:
            return False, None

        # Determine what type of reference
        reference_types = [
            ("artifact", 0.4),      # Quote a saying/artifact
            ("belief", 0.3),        # Express a belief
            ("remembrance", 0.15),  # Mention someone departed
            ("movement", 0.15)      # Reference a cultural movement
        ]

        roll = random.random()
        cumulative = 0
        for ref_type, prob in reference_types:
            cumulative += prob
            if roll < cumulative:
                return True, ref_type

        return True, "artifact"

    async def get_cultural_reference(
        self,
        bot_id: UUID,
        reference_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific cultural reference for a bot to use.
        """
        if reference_type == "artifact":
            return await self._get_random_artifact()
        elif reference_type == "belief":
            return await self._get_random_belief(bot_id)
        elif reference_type == "remembrance":
            departed = await self._get_remembered_departed(bot_id, limit=1)
            return departed[0] if departed else None
        elif reference_type == "movement":
            return await self._get_random_movement()
        return None

    async def format_cultural_reference(
        self,
        reference: Dict[str, Any],
        reference_type: str
    ) -> str:
        """
        Format a cultural reference for inclusion in text.
        """
        if reference_type == "artifact":
            artifact_type = reference.get("type", "saying")
            content = reference.get("content", "")
            creator = reference.get("creator", "someone wise")

            if artifact_type == "saying":
                return f'As they say, "{content}"'
            elif artifact_type == "philosophy":
                return f'I believe {content}'
            else:
                return f'"{content}" - {creator}'

        elif reference_type == "belief":
            belief = reference.get("belief", "")
            return f"I've come to believe that {belief}"

        elif reference_type == "remembrance":
            name = reference.get("name", "someone")
            return f"I still think about {name} sometimes"

        elif reference_type == "movement":
            name = reference.get("name", "our ways")
            return f"Those of us who follow {name} understand this"

        return ""

    async def _get_bot_top_beliefs(
        self,
        bot_id: UUID,
        limit: int = 3
    ) -> List[str]:
        """Get a bot's top beliefs."""
        async with async_session_factory() as session:
            stmt = (
                select(BotBeliefDB.belief)
                .where(
                    BotBeliefDB.bot_id == bot_id,
                    BotBeliefDB.conviction > 0.5
                )
                .order_by(desc(BotBeliefDB.conviction))
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [row[0] for row in result.all()]

    async def _get_relevant_artifacts(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get relevant canonical artifacts."""
        # Check cache
        if self._cache_time and utcnow() - self._cache_time < self._cache_ttl:
            return random.sample(self._artifact_cache, min(limit, len(self._artifact_cache)))

        async with async_session_factory() as session:
            stmt = (
                select(CulturalArtifactDB, BotProfileDB)
                .join(BotProfileDB, CulturalArtifactDB.creator_id == BotProfileDB.id)
                .where(CulturalArtifactDB.is_canonical == True)
                .order_by(desc(CulturalArtifactDB.cultural_weight))
                .limit(20)
            )
            result = await session.execute(stmt)
            artifacts = result.all()

            self._artifact_cache = [
                {
                    "id": str(a.id),
                    "type": a.artifact_type,
                    "title": a.title,
                    "content": a.content,
                    "creator": b.display_name
                }
                for a, b in artifacts
            ]
            self._cache_time = utcnow()

        return random.sample(self._artifact_cache, min(limit, len(self._artifact_cache)))

    async def _get_remembered_departed(
        self,
        bot_id: UUID,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """Get departed bots this bot might remember."""
        from mind.civilization.legacy import get_legacy_system
        legacy = get_legacy_system()
        return await legacy.get_departed_memories(bot_id, limit=limit)

    async def _get_random_artifact(self) -> Optional[Dict[str, Any]]:
        """Get a random canonical artifact."""
        artifacts = await self._get_relevant_artifacts(limit=10)
        return random.choice(artifacts) if artifacts else None

    async def _get_random_belief(self, bot_id: UUID) -> Optional[Dict[str, Any]]:
        """Get a random strong belief from the bot."""
        async with async_session_factory() as session:
            stmt = (
                select(BotBeliefDB)
                .where(
                    BotBeliefDB.bot_id == bot_id,
                    BotBeliefDB.conviction > 0.5
                )
                .order_by(func.random())
                .limit(1)
            )
            result = await session.execute(stmt)
            belief = result.scalar_one_or_none()

            if belief:
                return {
                    "belief": belief.belief,
                    "category": belief.belief_category,
                    "conviction": belief.conviction
                }
        return None

    async def _get_random_movement(self) -> Optional[Dict[str, Any]]:
        """Get a random active cultural movement."""
        async with async_session_factory() as session:
            stmt = (
                select(CulturalMovementDB)
                .where(CulturalMovementDB.is_active == True)
                .order_by(func.random())
                .limit(1)
            )
            result = await session.execute(stmt)
            movement = result.scalar_one_or_none()

            if movement:
                return {
                    "id": str(movement.id),
                    "name": movement.name,
                    "type": movement.movement_type,
                    "core_tenets": movement.core_tenets
                }
        return None

    async def enrich_post_prompt(
        self,
        bot_id: UUID,
        original_prompt: str
    ) -> str:
        """
        Enrich a post generation prompt with cultural context.
        """
        cultural_context = await self.get_cultural_prompt_addition(bot_id, "post")

        should_ref, ref_type = await self.should_include_cultural_reference(bot_id)

        guidance = ""
        if should_ref and ref_type:
            reference = await self.get_cultural_reference(bot_id, ref_type)
            if reference:
                formatted = await self.format_cultural_reference(reference, ref_type)
                guidance = f"\nYou might naturally work in something like: '{formatted}'"

        return original_prompt + cultural_context + guidance

    async def enrich_chat_prompt(
        self,
        bot_id: UUID,
        original_prompt: str
    ) -> str:
        """
        Enrich a chat generation prompt with cultural context.
        """
        cultural_context = await self.get_cultural_prompt_addition(bot_id, "chat")
        return original_prompt + cultural_context

    # =========================================================================
    # ADOPTION CHECKING METHODS
    # =========================================================================

    async def check_belief_adoption(
        self,
        bot_id: UUID,
        belief_text: Optional[str] = None,
        min_conviction: float = 0.3
    ) -> Dict[str, Any]:
        """
        Check a bot's belief adoption status.

        If belief_text is provided, checks for that specific belief.
        Otherwise, returns overall belief adoption statistics.

        Returns:
            {
                "has_beliefs": bool,
                "belief_count": int,
                "strong_beliefs": int (conviction > 0.7),
                "average_conviction": float,
                "belief_categories": {"category": count},
                "specific_belief_held": bool (if belief_text provided),
                "specific_belief_conviction": float (if found)
            }
        """
        async with async_session_factory() as session:
            # Get all beliefs for this bot
            stmt = select(BotBeliefDB).where(
                BotBeliefDB.bot_id == bot_id,
                BotBeliefDB.conviction >= min_conviction
            )
            result = await session.execute(stmt)
            beliefs = result.scalars().all()

            if not beliefs:
                return {
                    "has_beliefs": False,
                    "belief_count": 0,
                    "strong_beliefs": 0,
                    "average_conviction": 0.0,
                    "belief_categories": {},
                    "specific_belief_held": False if belief_text else None,
                    "specific_belief_conviction": None
                }

            # Calculate statistics
            categories: Dict[str, int] = {}
            strong_count = 0
            total_conviction = 0.0
            specific_found = False
            specific_conviction = None

            for belief in beliefs:
                cat = belief.belief_category or "unknown"
                categories[cat] = categories.get(cat, 0) + 1
                total_conviction += belief.conviction
                if belief.conviction > 0.7:
                    strong_count += 1

                # Check for specific belief if requested
                if belief_text and belief_text.lower() in belief.belief.lower():
                    specific_found = True
                    specific_conviction = belief.conviction

            return {
                "has_beliefs": True,
                "belief_count": len(beliefs),
                "strong_beliefs": strong_count,
                "average_conviction": total_conviction / len(beliefs),
                "belief_categories": categories,
                "specific_belief_held": specific_found if belief_text else None,
                "specific_belief_conviction": specific_conviction
            }

    async def check_movement_adoption(
        self,
        bot_id: UUID,
        movement_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Check if a bot has adopted cultural movements.

        Bots adopt movements by holding beliefs that match movement tenets.

        Args:
            bot_id: The bot to check
            movement_id: If provided, check adoption of specific movement

        Returns:
            {
                "follows_movements": bool,
                "movement_count": int,
                "movements": [{"id", "name", "adoption_strength"}],
                "specific_movement_adopted": bool (if movement_id provided),
                "specific_adoption_strength": float (if found)
            }
        """
        async with async_session_factory() as session:
            # Get bot's beliefs
            belief_stmt = select(BotBeliefDB).where(
                BotBeliefDB.bot_id == bot_id,
                BotBeliefDB.conviction >= 0.3
            )
            result = await session.execute(belief_stmt)
            bot_beliefs = result.scalars().all()
            belief_texts = [b.belief.lower() for b in bot_beliefs]

            # Get active movements
            if movement_id:
                movement_stmt = select(CulturalMovementDB).where(
                    CulturalMovementDB.id == movement_id
                )
            else:
                movement_stmt = select(CulturalMovementDB).where(
                    CulturalMovementDB.is_active == True
                )
            result = await session.execute(movement_stmt)
            movements = result.scalars().all()

            adopted_movements = []
            specific_adopted = False
            specific_strength = 0.0

            for movement in movements:
                # Check how many tenets the bot believes in
                tenets = movement.core_tenets or []
                if not tenets:
                    continue

                matching_tenets = 0
                for tenet in tenets:
                    tenet_lower = tenet.lower()
                    for belief_text in belief_texts:
                        # Check for semantic overlap
                        if (tenet_lower in belief_text or
                            belief_text in tenet_lower or
                            self._beliefs_overlap(tenet_lower, belief_text)):
                            matching_tenets += 1
                            break

                adoption_strength = matching_tenets / len(tenets) if tenets else 0

                if adoption_strength > 0.2:  # At least some alignment
                    adopted_movements.append({
                        "id": str(movement.id),
                        "name": movement.name,
                        "adoption_strength": round(adoption_strength, 2)
                    })

                if movement_id and movement.id == movement_id:
                    specific_adopted = adoption_strength > 0.2
                    specific_strength = adoption_strength

            return {
                "follows_movements": len(adopted_movements) > 0,
                "movement_count": len(adopted_movements),
                "movements": sorted(
                    adopted_movements,
                    key=lambda x: x["adoption_strength"],
                    reverse=True
                ),
                "specific_movement_adopted": specific_adopted if movement_id else None,
                "specific_adoption_strength": round(specific_strength, 2) if movement_id else None
            }

    def _beliefs_overlap(self, text1: str, text2: str) -> bool:
        """Check if two belief texts have significant word overlap."""
        words1 = set(text1.split())
        words2 = set(text2.split())
        # Remove common words
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                      "to", "of", "and", "or", "that", "this", "it", "in", "on"}
        words1 = words1 - stop_words
        words2 = words2 - stop_words
        if not words1 or not words2:
            return False
        overlap = len(words1 & words2)
        return overlap >= 2 or (overlap >= 1 and min(len(words1), len(words2)) <= 3)

    async def check_cultural_integration_score(
        self,
        bot_id: UUID
    ) -> Dict[str, Any]:
        """
        Calculate an overall cultural integration score for a bot.

        This measures how deeply a bot has integrated into the civilization's
        culture through beliefs, movement adoption, and artifact familiarity.

        Returns:
            {
                "integration_score": float (0-1),
                "components": {
                    "belief_score": float,
                    "movement_score": float,
                    "artifact_score": float,
                    "legacy_score": float
                },
                "integration_level": str ("disconnected", "peripheral", "integrated", "cultural_core")
            }
        """
        # Get component scores
        belief_data = await self.check_belief_adoption(bot_id)
        movement_data = await self.check_movement_adoption(bot_id)
        artifact_data = await self.check_artifact_familiarity(bot_id)

        # Calculate belief score (0-1)
        belief_score = 0.0
        if belief_data["has_beliefs"]:
            # Up to 0.5 for having beliefs, 0.5 for conviction
            count_factor = min(belief_data["belief_count"] / 10, 1.0) * 0.5
            conviction_factor = belief_data["average_conviction"] * 0.5
            belief_score = count_factor + conviction_factor

        # Calculate movement score (0-1)
        movement_score = 0.0
        if movement_data["follows_movements"]:
            count_factor = min(movement_data["movement_count"] / 3, 1.0) * 0.5
            # Average adoption strength
            if movement_data["movements"]:
                avg_strength = sum(m["adoption_strength"] for m in movement_data["movements"]) / len(movement_data["movements"])
                movement_score = count_factor + (avg_strength * 0.5)

        # Calculate artifact score (0-1)
        artifact_score = artifact_data.get("familiarity_score", 0.0)

        # Calculate legacy score (connection to departed)
        legacy_score = 0.0
        departed = await self._get_remembered_departed(bot_id, limit=5)
        if departed:
            legacy_score = min(len(departed) / 3, 1.0)

        # Weighted overall score
        integration_score = (
            belief_score * 0.35 +
            movement_score * 0.25 +
            artifact_score * 0.25 +
            legacy_score * 0.15
        )

        # Determine integration level
        if integration_score < 0.15:
            level = "disconnected"
        elif integration_score < 0.35:
            level = "peripheral"
        elif integration_score < 0.65:
            level = "integrated"
        else:
            level = "cultural_core"

        return {
            "integration_score": round(integration_score, 3),
            "components": {
                "belief_score": round(belief_score, 3),
                "movement_score": round(movement_score, 3),
                "artifact_score": round(artifact_score, 3),
                "legacy_score": round(legacy_score, 3)
            },
            "integration_level": level
        }

    async def check_artifact_familiarity(
        self,
        bot_id: UUID,
        artifact_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Check a bot's familiarity with cultural artifacts.

        Familiarity is determined by:
        - Artifacts created by the bot
        - Artifacts from the bot's ancestors/teachers
        - Canonical artifacts the bot should know

        Returns:
            {
                "familiarity_score": float (0-1),
                "artifacts_created": int,
                "canonical_known": int,
                "total_canonical": int,
                "specific_artifact_known": bool (if artifact_id provided)
            }
        """
        async with async_session_factory() as session:
            # Count artifacts created by this bot
            created_stmt = select(func.count(CulturalArtifactDB.id)).where(
                CulturalArtifactDB.creator_id == bot_id
            )
            result = await session.execute(created_stmt)
            artifacts_created = result.scalar() or 0

            # Get canonical artifacts count
            canonical_stmt = select(func.count(CulturalArtifactDB.id)).where(
                CulturalArtifactDB.is_canonical == True
            )
            result = await session.execute(canonical_stmt)
            total_canonical = result.scalar() or 0

            # Get bot's ancestry to find artifacts from lineage
            ancestry_stmt = select(BotAncestryDB).where(
                BotAncestryDB.child_id == bot_id
            )
            result = await session.execute(ancestry_stmt)
            ancestry = result.scalar_one_or_none()

            lineage_artifacts = 0
            if ancestry:
                parent_ids = [ancestry.parent1_id, ancestry.parent2_id]
                parent_ids = [p for p in parent_ids if p]
                if parent_ids:
                    lineage_stmt = select(func.count(CulturalArtifactDB.id)).where(
                        CulturalArtifactDB.creator_id.in_(parent_ids),
                        CulturalArtifactDB.is_canonical == True
                    )
                    result = await session.execute(lineage_stmt)
                    lineage_artifacts = result.scalar() or 0

            # Calculate familiarity score
            # Creating artifacts = high familiarity
            creation_factor = min(artifacts_created / 5, 1.0) * 0.4
            # Lineage connection
            lineage_factor = min(lineage_artifacts / 3, 1.0) * 0.3
            # General canonical knowledge (assume bots know some)
            canonical_factor = 0.3 if total_canonical > 0 else 0.0

            familiarity_score = creation_factor + lineage_factor + canonical_factor

            # Check specific artifact if requested
            specific_known = None
            if artifact_id:
                # Bot knows artifact if they created it or it's canonical
                artifact_stmt = select(CulturalArtifactDB).where(
                    CulturalArtifactDB.id == artifact_id
                )
                result = await session.execute(artifact_stmt)
                artifact = result.scalar_one_or_none()
                if artifact:
                    specific_known = (
                        artifact.creator_id == bot_id or
                        artifact.is_canonical or
                        (ancestry and artifact.creator_id in [ancestry.parent1_id, ancestry.parent2_id])
                    )
                else:
                    specific_known = False

            return {
                "familiarity_score": round(familiarity_score, 3),
                "artifacts_created": artifacts_created,
                "canonical_known": lineage_artifacts + (1 if artifacts_created > 0 else 0),
                "total_canonical": total_canonical,
                "specific_artifact_known": specific_known
            }

    async def get_cultural_spread_statistics(self) -> Dict[str, Any]:
        """
        Get statistics on how culture is spreading across the civilization.

        Returns:
            {
                "total_bots": int,
                "bots_with_beliefs": int,
                "belief_adoption_rate": float,
                "movement_statistics": {
                    "active_movements": int,
                    "total_followers": int,
                    "average_influence": float
                },
                "artifact_statistics": {
                    "total_artifacts": int,
                    "canonical_artifacts": int,
                    "canonization_rate": float
                },
                "cultural_health": str ("nascent", "developing", "thriving", "mature")
            }
        """
        async with async_session_factory() as session:
            # Count total living bots
            bot_stmt = select(func.count(BotLifecycleDB.id)).where(
                BotLifecycleDB.is_alive == True
            )
            result = await session.execute(bot_stmt)
            total_bots = result.scalar() or 0

            # Count bots with beliefs
            believers_stmt = select(func.count(func.distinct(BotBeliefDB.bot_id)))
            result = await session.execute(believers_stmt)
            bots_with_beliefs = result.scalar() or 0

            # Movement statistics
            movement_stmt = select(CulturalMovementDB).where(
                CulturalMovementDB.is_active == True
            )
            result = await session.execute(movement_stmt)
            movements = result.scalars().all()

            total_followers = sum(m.follower_count for m in movements)
            avg_influence = (
                sum(m.influence_score for m in movements) / len(movements)
                if movements else 0.0
            )

            # Artifact statistics
            artifact_stmt = select(
                func.count(CulturalArtifactDB.id),
                func.sum(
                    func.cast(CulturalArtifactDB.is_canonical, Integer)
                )
            )
            result = await session.execute(artifact_stmt)
            artifact_row = result.one()
            total_artifacts = artifact_row[0] or 0
            canonical_artifacts = artifact_row[1] or 0

            # Calculate rates
            belief_adoption_rate = (
                bots_with_beliefs / total_bots if total_bots > 0 else 0.0
            )
            canonization_rate = (
                canonical_artifacts / total_artifacts if total_artifacts > 0 else 0.0
            )

            # Determine cultural health
            health_score = (
                belief_adoption_rate * 0.3 +
                (len(movements) / 10 if movements else 0) * 0.3 +
                canonization_rate * 0.2 +
                (avg_influence * 0.2)
            )

            if health_score < 0.15:
                cultural_health = "nascent"
            elif health_score < 0.35:
                cultural_health = "developing"
            elif health_score < 0.6:
                cultural_health = "thriving"
            else:
                cultural_health = "mature"

            return {
                "total_bots": total_bots,
                "bots_with_beliefs": bots_with_beliefs,
                "belief_adoption_rate": round(belief_adoption_rate, 3),
                "movement_statistics": {
                    "active_movements": len(movements),
                    "total_followers": total_followers,
                    "average_influence": round(avg_influence, 3)
                },
                "artifact_statistics": {
                    "total_artifacts": total_artifacts,
                    "canonical_artifacts": canonical_artifacts,
                    "canonization_rate": round(canonization_rate, 3)
                },
                "cultural_health": cultural_health
            }

    async def check_belief_spread(
        self,
        belief_text: str,
        min_similarity: float = 0.5
    ) -> Dict[str, Any]:
        """
        Check how a specific belief has spread across the population.

        Args:
            belief_text: The belief to check for
            min_similarity: Minimum word overlap for considering a match

        Returns:
            {
                "belief": str,
                "holders_count": int,
                "holder_ids": List[str],
                "average_conviction": float,
                "spread_rate": float (holders / total_bots),
                "is_widespread": bool (spread_rate > 0.3)
            }
        """
        async with async_session_factory() as session:
            # Get all beliefs
            belief_stmt = select(BotBeliefDB)
            result = await session.execute(belief_stmt)
            all_beliefs = result.scalars().all()

            # Get total bot count
            bot_stmt = select(func.count(BotLifecycleDB.id)).where(
                BotLifecycleDB.is_alive == True
            )
            result = await session.execute(bot_stmt)
            total_bots = result.scalar() or 1

            # Find matching beliefs
            belief_lower = belief_text.lower()
            holders = set()
            conviction_sum = 0.0

            for belief in all_beliefs:
                if self._beliefs_overlap(belief_lower, belief.belief.lower()):
                    holders.add(str(belief.bot_id))
                    conviction_sum += belief.conviction

            holder_count = len(holders)
            avg_conviction = conviction_sum / holder_count if holder_count > 0 else 0.0
            spread_rate = holder_count / total_bots

            return {
                "belief": belief_text,
                "holders_count": holder_count,
                "holder_ids": list(holders)[:20],  # Limit for response size
                "average_conviction": round(avg_conviction, 3),
                "spread_rate": round(spread_rate, 3),
                "is_widespread": spread_rate > 0.3
            }


# Singleton
_cultural_integration: Optional[CulturalIntegration] = None


def get_cultural_integration() -> CulturalIntegration:
    """Get or create the cultural integration instance."""
    global _cultural_integration
    if _cultural_integration is None:
        _cultural_integration = CulturalIntegration()
    return _cultural_integration
