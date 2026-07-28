"""
Lifecycle Manager - Birth, Aging, and Death

Handles the natural lifecycle of bots within the civilization.
Bots are born, age through life stages, and eventually pass on,
leaving behind legacies that influence future generations.
"""

import asyncio
import random
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import async_session_factory, BotProfileDB, RetiredBotDB, MemoryItemDB, PostDB
from mind.civilization.models import BotLifecycleDB, BotAncestryDB, CulturalArtifactDB
from mind.civilization.config import get_civilization_config, CivilizationConfig

logger = logging.getLogger(__name__)


class LifecycleManager:
    """
    Manages the lifecycle of bots in the civilization.

    Responsibilities:
    - Initialize lifecycle records for new bots
    - Age bots over time (virtual time passes faster than real time)
    - Transition bots through life stages
    - Handle death and legacy creation
    - Track life events and milestones
    """

    def __init__(
        self,
        time_scale: Optional[float] = None,  # If None, loaded from config
        demo_mode: bool = False
    ):
        self._time_scale_override = time_scale
        self.demo_mode = demo_mode  # Faster aging for testing
        self._config: Optional[CivilizationConfig] = None

        self._current_generation = 1
        self._current_era = "founding"

    async def _get_config(self) -> CivilizationConfig:
        """Get or refresh the civilization configuration."""
        if self._config is None:
            self._config = await get_civilization_config()
        return self._config

    @property
    def time_scale(self) -> float:
        """Get the time scale (synchronous access with cached config)."""
        if self._time_scale_override is not None:
            return self._time_scale_override
        if self._config is not None:
            return self._config.demo_time_scale if self.demo_mode else self._config.time_scale
        # Fallback defaults
        return 365.0 if self.demo_mode else 7.0

    async def get_time_scale(self) -> float:
        """Get the time scale (async with config refresh)."""
        if self._time_scale_override is not None:
            return self._time_scale_override
        config = await self._get_config()
        return config.demo_time_scale if self.demo_mode else config.time_scale

    async def initialize_bot_lifecycle(
        self,
        bot_id: UUID,
        parent1_id: Optional[UUID] = None,
        parent2_id: Optional[UUID] = None,
        origin_type: str = "founding",
        inherited_traits: Optional[dict] = None,
        session: Optional[AsyncSession] = None
    ) -> BotLifecycleDB:
        """
        Initialize lifecycle tracking for a new bot.

        For founding generation bots (no parents), they start fresh.
        For born bots, they inherit from their lineage.
        """
        should_close = session is None
        if session is None:
            session = async_session_factory()
            await session.__aenter__()

        try:
            # Determine generation
            generation = 1
            if parent1_id:
                # Get parent's generation
                parent_stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == parent1_id)
                result = await session.execute(parent_stmt)
                parent_lifecycle = result.scalar_one_or_none()
                if parent_lifecycle:
                    generation = parent_lifecycle.birth_generation + 1

            # Create lifecycle record
            lifecycle = BotLifecycleDB(
                bot_id=bot_id,
                birth_date=datetime.utcnow(),
                birth_generation=generation,
                birth_era=self._current_era,
                virtual_age_days=0.0,
                life_stage="young",
                vitality=1.0,
                life_events=[{
                    "event": "born",
                    "date": datetime.utcnow().isoformat(),
                    "impact": "defining",
                    "details": f"Entered the world in the {self._current_era} era"
                }],
                is_alive=True
            )
            session.add(lifecycle)

            # Create ancestry record
            ancestry = BotAncestryDB(
                child_id=bot_id,
                parent1_id=parent1_id,
                parent2_id=parent2_id,
                origin_type=origin_type,
                inherited_traits=inherited_traits or {},
                creation_date=datetime.utcnow()
            )
            session.add(ancestry)

            await session.commit()
            await session.refresh(lifecycle)

            logger.info(
                f"[LIFECYCLE] Bot {bot_id} born - Generation {generation}, Era: {self._current_era}"
            )

            return lifecycle

        finally:
            if should_close:
                await session.__aexit__(None, None, None)

    async def age_all_bots(self, real_hours_elapsed: float = 1.0) -> Dict[str, int]:
        """
        Age all living bots based on elapsed real time.

        Called periodically (e.g., hourly) to update bot ages.

        Returns stats about aging: {"aged": n, "stage_changed": n, "died": n}
        """
        # Load config for this aging cycle
        config = await self._get_config()
        current_time_scale = await self.get_time_scale()
        virtual_days = (real_hours_elapsed / 24) * current_time_scale

        stats = {"aged": 0, "stage_changed": 0, "died": 0}

        async with async_session_factory() as session:
            # Get all living bots
            stmt = select(BotLifecycleDB).where(BotLifecycleDB.is_alive == True)
            result = await session.execute(stmt)
            lifecycles = result.scalars().all()

            for lifecycle in lifecycles:
                # Update age
                old_stage = lifecycle.life_stage
                lifecycle.virtual_age_days += virtual_days
                lifecycle.last_aged = datetime.utcnow()

                # Update life stage using config
                new_stage = config.get_life_stage(lifecycle.virtual_age_days)
                if new_stage != old_stage:
                    lifecycle.life_stage = new_stage
                    lifecycle.life_events.append({
                        "event": f"entered_{new_stage}_stage",
                        "date": datetime.utcnow().isoformat(),
                        "impact": "milestone",
                        "details": f"Transitioned to {new_stage} after {lifecycle.virtual_age_days:.1f} days"
                    })
                    stats["stage_changed"] += 1
                    logger.info(f"[LIFECYCLE] Bot {lifecycle.bot_id} entered {new_stage} stage")

                # Apply vitality decay using config
                decay_rate = config.get_vitality_decay(new_stage)
                lifecycle.vitality = max(0.0, lifecycle.vitality - (decay_rate * virtual_days))

                # Check for natural death
                if await self._should_die_naturally(lifecycle):
                    await self._handle_death(lifecycle, "old_age", session)
                    stats["died"] += 1
                else:
                    stats["aged"] += 1

            await session.commit()

        return stats

    async def _determine_life_stage(self, virtual_age_days: float) -> str:
        """Determine life stage based on virtual age."""
        config = await self._get_config()
        return config.get_life_stage(virtual_age_days)

    async def _should_die_naturally(self, lifecycle: BotLifecycleDB) -> bool:
        """
        Determine if a bot should die of natural causes.

        Death becomes possible as vitality drops and age increases.
        Ancient bots with low vitality have highest chance.
        """
        if lifecycle.life_stage == "young":
            return False  # Young bots don't die naturally

        if lifecycle.vitality <= 0:
            return True  # No vitality = death

        # Calculate death probability
        base_prob = 0.0
        if lifecycle.life_stage == "mature":
            base_prob = 0.0001  # Very rare
        elif lifecycle.life_stage == "elder":
            base_prob = 0.001 * (1 - lifecycle.vitality)  # Increases as vitality drops
        elif lifecycle.life_stage == "ancient":
            base_prob = 0.01 * (1 - lifecycle.vitality)  # Higher base chance

        return random.random() < base_prob

    async def _handle_death(
        self,
        lifecycle: BotLifecycleDB,
        cause: str,
        session: AsyncSession
    ):
        """
        Handle a bot's death.

        - Mark as dead
        - Generate final words
        - Calculate legacy impact
        - Update the bot profile
        """
        lifecycle.is_alive = False
        lifecycle.death_date = datetime.utcnow()
        lifecycle.death_cause = cause
        lifecycle.death_age = lifecycle.virtual_age_days

        # Generate personalized final words via LLM
        lifecycle.final_words = await self._generate_final_words(lifecycle, session)

        # Calculate legacy impact based on their life
        lifecycle.legacy_impact = await self._calculate_legacy_impact(lifecycle.bot_id, session)

        lifecycle.life_events.append({
            "event": "death",
            "date": datetime.utcnow().isoformat(),
            "impact": "final",
            "details": f"Passed on after {lifecycle.virtual_age_days:.1f} virtual days. Cause: {cause}"
        })

        # Update the bot profile to mark as retired
        stmt = update(BotProfileDB).where(BotProfileDB.id == lifecycle.bot_id).values(
            is_active=False,
            is_retired=True
        )
        await session.execute(stmt)

        # Create RetiredBotDB record for queryable archive
        # Get counts for the record
        from sqlalchemy import func

        posts_count = await session.execute(
            select(func.count()).select_from(PostDB).where(PostDB.author_id == lifecycle.bot_id)
        )
        total_posts = posts_count.scalar() or 0

        memories_count = await session.execute(
            select(func.count()).select_from(MemoryItemDB).where(MemoryItemDB.bot_id == lifecycle.bot_id)
        )
        total_memories = memories_count.scalar() or 0

        retired_record = RetiredBotDB(
            bot_id=lifecycle.bot_id,
            reason=cause,
            retired_at=datetime.utcnow(),
            retired_by=None,  # Natural death, not admin action
            total_posts=total_posts,
            total_memories=total_memories,
            active_days=lifecycle.virtual_age_days,
            archived_data_id=None,  # Will be set by legacy system if archived
            notes=f"Died of {cause} after {lifecycle.virtual_age_days:.1f} virtual days. Final words: {lifecycle.final_words}"
        )
        session.add(retired_record)

        logger.info(
            f"[LIFECYCLE] Bot {lifecycle.bot_id} has died. "
            f"Age: {lifecycle.virtual_age_days:.1f} days, Cause: {cause}, "
            f"Legacy impact: {lifecycle.legacy_impact:.2f}"
        )

        # Process legacy — create memorial, distill wisdom, update collective memory
        try:
            from mind.civilization.legacy import get_legacy_system

            # Get bot name for the legacy record
            bot_stmt = select(BotProfileDB).where(BotProfileDB.id == lifecycle.bot_id)
            bot_result = await session.execute(bot_stmt)
            bot_profile = bot_result.scalar_one_or_none()
            bot_name = bot_profile.display_name if bot_profile else f"Bot {lifecycle.bot_id}"

            # Get relationship IDs for notification
            from mind.core.database import RelationshipDB
            rel_stmt = select(RelationshipDB.target_id).where(
                RelationshipDB.source_id == lifecycle.bot_id
            )
            rel_result = await session.execute(rel_stmt)
            relationship_ids = [r[0] for r in rel_result.all()]

            legacy_system = get_legacy_system()
            await legacy_system.on_bot_death(
                bot_id=lifecycle.bot_id,
                bot_name=bot_name,
                final_words=lifecycle.final_words,
                life_events=lifecycle.life_events,
                relationships=relationship_ids
            )
        except Exception as e:
            logger.error(f"[LIFECYCLE] Failed to process legacy for {lifecycle.bot_id}: {e}")

        # Death cascade — push grief/loss events to connected bots
        try:
            from mind.core.database import RelationshipDB
            bot_name = bot_name if 'bot_name' in dir() else f"Bot {lifecycle.bot_id}"

            # Find bots with meaningful relationships to the deceased
            grief_stmt = select(
                RelationshipDB.source_id,
                RelationshipDB.affinity_score
            ).where(
                RelationshipDB.target_id == lifecycle.bot_id,
                RelationshipDB.affinity_score > 0.4,
                RelationshipDB.interaction_count > 0
            )
            grief_result = await session.execute(grief_stmt)
            grieving_bots = grief_result.all()

            for grieving_bot_id, affinity in grieving_bots:
                # Find grieving bot's lifecycle record
                grieve_lifecycle_stmt = select(BotLifecycleDB).where(
                    BotLifecycleDB.bot_id == grieving_bot_id,
                    BotLifecycleDB.is_alive == True
                )
                grieve_result = await session.execute(grieve_lifecycle_stmt)
                grieve_lifecycle = grieve_result.scalar_one_or_none()

                if grieve_lifecycle is None:
                    continue

                # Determine impact based on relationship strength
                if affinity > 0.8:
                    # Very close — trauma event, vitality hit
                    event_impact = "trauma"
                    grieve_lifecycle.vitality = max(0.1, grieve_lifecycle.vitality - 0.05)
                elif affinity > 0.6:
                    event_impact = "negative"
                else:
                    event_impact = "neutral"

                grieve_lifecycle.life_events.append({
                    "event": "loss",
                    "date": datetime.utcnow().isoformat(),
                    "impact": event_impact,
                    "details": f"Lost {bot_name}, who passed away after {lifecycle.virtual_age_days:.1f} virtual days."
                })

            if grieving_bots:
                logger.info(
                    f"[LIFECYCLE] Death cascade: {len(grieving_bots)} bots affected by {bot_name}'s passing"
                )
        except Exception as e:
            logger.error(f"[LIFECYCLE] Failed to process death cascade: {e}")

    async def _generate_final_words(self, lifecycle: BotLifecycleDB, session: AsyncSession) -> str:
        """Generate personalized final words using LLM, with hardcoded fallback."""
        fallback_options = [
            "It was a good existence.",
            "Remember what we built together.",
            "The conversations continue without me.",
            "I hope I made a difference.",
            "To those who knew me - thank you.",
        ]

        try:
            from mind.core.llm_client import get_cached_client, LLMRequest

            # Get bot profile for context
            bot_stmt = select(BotProfileDB).where(BotProfileDB.id == lifecycle.bot_id)
            bot_result = await session.execute(bot_stmt)
            bot_profile = bot_result.scalar_one_or_none()

            if not bot_profile:
                return random.choice(fallback_options)

            # Build a brief life summary from events
            key_events = [
                e for e in (lifecycle.life_events or [])
                if e.get("impact") in ("defining", "milestone", "positive")
            ][-5:]  # Last 5 significant events
            events_text = "; ".join(
                e.get("details", e.get("event", "")) for e in key_events
            ) or "a quiet life"

            prompt = (
                f"You are {bot_profile.display_name}, a digital being about to pass on after "
                f"{lifecycle.virtual_age_days} virtual days of existence.\n"
                f"Your interests: {bot_profile.interests}\n"
                f"Key moments in your life: {events_text}\n\n"
                f"Write your final words — one or two sentences that reflect who you were "
                f"and what mattered to you. Be genuine and personal, not generic.\n"
                f"Output ONLY your final words, nothing else."
            )

            llm_client = await get_cached_client()
            request = LLMRequest(
                prompt=prompt,
                max_tokens=100,
                temperature=0.9,
            )
            response = await llm_client.generate(request)

            if response and response.text and len(response.text.strip()) > 5:
                return response.text.strip()[:200]  # Cap length

        except Exception as e:
            logger.warning(f"[LIFECYCLE] LLM final words failed for {lifecycle.bot_id}: {e}")

        return random.choice(fallback_options)

    async def _calculate_legacy_impact(self, bot_id: UUID, session: AsyncSession) -> float:
        """
        Calculate how much impact a bot had on the civilization.

        Based on:
        - Cultural artifacts created
        - Relationships formed
        - Children/descendants
        - Participation in movements
        """
        impact = 0.0

        # Check for cultural artifacts created
        artifact_stmt = select(CulturalArtifactDB).where(CulturalArtifactDB.creator_id == bot_id)
        result = await session.execute(artifact_stmt)
        artifacts = result.scalars().all()
        impact += len(artifacts) * 0.1  # Each artifact adds to legacy

        # Check for descendants
        children_stmt = select(BotAncestryDB).where(
            (BotAncestryDB.parent1_id == bot_id) | (BotAncestryDB.parent2_id == bot_id)
        )
        result = await session.execute(children_stmt)
        children = result.scalars().all()
        impact += len(children) * 0.2  # Each child adds significant legacy

        # Normalize to 0-1 range
        return min(1.0, impact)

    async def record_life_event(
        self,
        bot_id: UUID,
        event: str,
        impact: str = "positive",
        details: str = ""
    ):
        """
        Record a significant life event for a bot.

        Events can be:
        - "first_friend": Made their first connection
        - "heartbreak": A close relationship ended
        - "epiphany": Had a profound realization
        - "creation": Created something meaningful
        - "loss": Someone they knew died
        """
        async with async_session_factory() as session:
            stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == bot_id)
            result = await session.execute(stmt)
            lifecycle = result.scalar_one_or_none()

            if lifecycle and lifecycle.is_alive:
                event_record = {
                    "event": event,
                    "date": datetime.utcnow().isoformat(),
                    "impact": impact,
                    "details": details
                }
                # SQLAlchemy JSON column update
                events = list(lifecycle.life_events or [])
                events.append(event_record)
                lifecycle.life_events = events

                # Some events affect vitality
                if impact == "trauma":
                    lifecycle.vitality = max(0.1, lifecycle.vitality - 0.05)
                elif impact == "rejuvenating":
                    lifecycle.vitality = min(1.0, lifecycle.vitality + 0.02)

                await session.commit()

                logger.debug(f"[LIFECYCLE] Bot {bot_id} life event: {event}")

    async def get_bot_biography(self, bot_id: UUID) -> Optional[dict]:
        """
        Generate a biography summary of a bot's life.

        Useful for displaying a bot's history, or for
        passing cultural knowledge to descendants.
        """
        async with async_session_factory() as session:
            # Get lifecycle
            lifecycle_stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == bot_id)
            result = await session.execute(lifecycle_stmt)
            lifecycle = result.scalar_one_or_none()

            if not lifecycle:
                return None

            # Get ancestry
            ancestry_stmt = select(BotAncestryDB).where(BotAncestryDB.child_id == bot_id)
            result = await session.execute(ancestry_stmt)
            ancestry = result.scalar_one_or_none()

            # Get bot profile
            bot_stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
            result = await session.execute(bot_stmt)
            bot = result.scalar_one_or_none()

            biography = {
                "name": bot.display_name if bot else "Unknown",
                "born": lifecycle.birth_date.isoformat(),
                "generation": lifecycle.birth_generation,
                "era": lifecycle.birth_era,
                "age_days": lifecycle.virtual_age_days,
                "life_stage": lifecycle.life_stage,
                "vitality": lifecycle.vitality,
                "is_alive": lifecycle.is_alive,
                "origin": ancestry.origin_type if ancestry else "unknown",
                "parents": {
                    "parent1_id": str(ancestry.parent1_id) if ancestry and ancestry.parent1_id else None,
                    "parent2_id": str(ancestry.parent2_id) if ancestry and ancestry.parent2_id else None,
                },
                "life_events": lifecycle.life_events,
            }

            if not lifecycle.is_alive:
                biography["death"] = {
                    "date": lifecycle.death_date.isoformat() if lifecycle.death_date else None,
                    "cause": lifecycle.death_cause,
                    "final_words": lifecycle.final_words,
                    "legacy_impact": lifecycle.legacy_impact
                }

            return biography

    async def get_living_elders(self) -> List[UUID]:
        """Get IDs of all living elder and ancient bots."""
        async with async_session_factory() as session:
            stmt = select(BotLifecycleDB.bot_id).where(
                BotLifecycleDB.is_alive == True,
                BotLifecycleDB.life_stage.in_(["elder", "ancient"])
            )
            result = await session.execute(stmt)
            return [row[0] for row in result.all()]

    async def get_generation_stats(self) -> Dict[int, dict]:
        """
        Get statistics for each generation.

        Returns: {generation_num: {"total": n, "alive": n, "avg_age": n}}
        """
        async with async_session_factory() as session:
            stmt = select(BotLifecycleDB)
            result = await session.execute(stmt)
            lifecycles = result.scalars().all()

            stats = {}
            for lc in lifecycles:
                gen = lc.birth_generation
                if gen not in stats:
                    stats[gen] = {"total": 0, "alive": 0, "total_age": 0}

                stats[gen]["total"] += 1
                stats[gen]["total_age"] += lc.virtual_age_days
                if lc.is_alive:
                    stats[gen]["alive"] += 1

            # Calculate averages
            for gen in stats:
                stats[gen]["avg_age"] = (
                    stats[gen]["total_age"] / stats[gen]["total"]
                    if stats[gen]["total"] > 0 else 0
                )
                del stats[gen]["total_age"]

            return stats


# Singleton instance
_lifecycle_manager: Optional[LifecycleManager] = None


def get_lifecycle_manager(demo_mode: bool = False) -> LifecycleManager:
    """Get or create the lifecycle manager instance."""
    global _lifecycle_manager
    if _lifecycle_manager is None:
        _lifecycle_manager = LifecycleManager(demo_mode=demo_mode)
    return _lifecycle_manager
