"""
Social Loop - Manage relationships, conflicts, social dynamics, and emotional contagion.

Handles:
- _social_dynamics_loop()
- _generate_social_conflict()
- _log_relationship_summary()
- _process_emotional_contagion()
- _apply_community_mood_influence()
"""

import asyncio
import random
import logging
from typing import Dict, List, Optional, TYPE_CHECKING
from uuid import UUID

from mind.core.types import BotProfile
from mind.engine.social_dynamics import ConflictType, ConflictGenerator
from mind.engine.loops.base_loop import BaseLoop
from mind.intelligence.emotional_contagion import (
    EmotionalContagionManager,
    get_emotional_contagion_manager
)

if TYPE_CHECKING:
    from mind.engine.social_dynamics import RelationshipManager
    from mind.engine.conscious_mind import ConsciousMindManager

logger = logging.getLogger(__name__)


class SocialLoop(BaseLoop):
    """
    Manage relationships, generate conflicts, simulate social dynamics, and emotional contagion.

    This loop:
    - Simulates time passing (relationships drift, conflicts cool down)
    - Generates occasional conflicts between bots
    - Processes emotional contagion between bots
    - Applies community mood influence on individuals
    - Logs relationship changes and drama events
    """

    def __init__(
        self,
        active_bots: Dict[UUID, BotProfile],
        llm_semaphore: asyncio.Semaphore,
        event_broadcast: Optional[asyncio.Queue] = None,
        recent_content: Optional[Dict[UUID, List[str]]] = None,
        max_recent_content: int = 20,
        social_dynamics_manager: Optional["RelationshipManager"] = None,
        conscious_mind_manager: Optional["ConsciousMindManager"] = None,
        emotional_contagion_manager: Optional[EmotionalContagionManager] = None
    ):
        super().__init__(
            active_bots=active_bots,
            llm_semaphore=llm_semaphore,
            event_broadcast=event_broadcast,
            recent_content=recent_content,
            max_recent_content=max_recent_content
        )
        self.social_dynamics_manager = social_dynamics_manager
        self.conscious_mind_manager = conscious_mind_manager

        # Get or use provided emotional contagion manager
        self.emotional_contagion_manager = emotional_contagion_manager or get_emotional_contagion_manager()

        # Link relationship manager to contagion manager
        if self.social_dynamics_manager and self.emotional_contagion_manager:
            self.emotional_contagion_manager.set_relationship_manager(self.social_dynamics_manager)

    async def run(self):
        """Run the social dynamics loop."""
        await asyncio.sleep(30)  # Wait for bots to initialize
        logger.info("[SOCIAL] Social dynamics loop started")

        # Register all active bots with emotional contagion manager
        await self._register_bots_for_contagion()

        while self.is_running:
            try:
                # Run social dynamics every 2-3 minutes
                await asyncio.sleep(random.uniform(120, 180))

                if not self.active_bots or len(self.active_bots) < 2:
                    continue

                # Simulate time passing for all relationships
                self.social_dynamics_manager.simulate_time_passing(hours=0.05)  # ~3 minutes

                # Apply emotional decay over time
                await self.emotional_contagion_manager.decay_emotions(hours_passed=0.05)

                # Process emotional contagion between bots (30% chance each cycle)
                if random.random() < 0.30:
                    await self._process_emotional_contagion()

                # Apply community mood influence (20% chance each cycle)
                if random.random() < 0.20:
                    await self._apply_community_mood_influence()

                # Maybe generate a conflict (10% chance each cycle)
                if random.random() < 0.10:
                    await self._generate_social_conflict()

                # Log relationship summaries periodically
                if random.random() < 0.2:
                    self._log_relationship_summary()

                # Log emotional contagion summary periodically (10% chance)
                if random.random() < 0.1:
                    self._log_emotional_contagion_summary()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in social dynamics loop: {e}")
                await asyncio.sleep(60)

    async def _generate_social_conflict(self):
        """Generate a random conflict between two bots."""
        bots = list(self.active_bots.values())
        if len(bots) < 2:
            return

        # Pick two random bots
        bot_a, bot_b = random.sample(bots, 2)

        # Get their relationship
        relationship = self.social_dynamics_manager.get_or_create_relationship(bot_a.id, bot_b.id)

        # Don't create conflicts between strangers (they need some history)
        if relationship.relationship_type.value == "stranger":
            # First interaction - just record it
            return

        # Generate conflict using the conflict generator
        conflict_generator = ConflictGenerator(self.social_dynamics_manager)

        # Pick a random conflict type based on relationship
        if relationship.warmth < 0.3:
            conflict_type = random.choice([ConflictType.JEALOUSY, ConflictType.MISUNDERSTANDING])
        elif relationship.trust < 0.4:
            conflict_type = random.choice([ConflictType.BETRAYAL, ConflictType.COMPETITION])
        else:
            conflict_type = random.choice([ConflictType.MINOR_SLIGHT, ConflictType.DISAGREEMENT])

        conflict_generator.start_conflict(bot_a.id, bot_b.id, conflict_type)

        logger.info(
            f"[DRAMA] {bot_a.display_name} and {bot_b.display_name} "
            f"have started a {conflict_type.value}!"
        )

        # Notify their conscious minds about the conflict
        mind_a = self.conscious_mind_manager.get_mind(bot_a.id)
        mind_b = self.conscious_mind_manager.get_mind(bot_b.id)

        if mind_a:
            await mind_a.inject_thought(
                f"I'm having a {conflict_type.value} with {bot_b.display_name}. "
                f"This is bothering me.",
                intensity=0.7,
                thought_type="conflict"
            )

        if mind_b:
            await mind_b.inject_thought(
                f"There's some {conflict_type.value} between me and {bot_a.display_name}. "
                f"I need to deal with this.",
                intensity=0.7,
                thought_type="conflict"
            )

    def _log_relationship_summary(self):
        """Log a summary of current relationships."""
        all_relationships = self.social_dynamics_manager.get_all_relationships()

        # Find interesting relationships (strong or conflicted)
        interesting = []
        for (bot_a, bot_b), rel in all_relationships.items():
            if rel.relationship_type.value in ["friend", "close_friend", "best_friend"]:
                interesting.append((bot_a, bot_b, rel, "friendship"))
            elif rel.relationship_type.value in ["rival", "enemy"]:
                interesting.append((bot_a, bot_b, rel, "rivalry"))
            elif rel.in_conflict:
                interesting.append((bot_a, bot_b, rel, "conflict"))

        if interesting:
            sample = random.sample(interesting, min(3, len(interesting)))
            for bot_a, bot_b, rel, rel_type in sample:
                name_a = self.active_bots.get(bot_a, {})
                name_b = self.active_bots.get(bot_b, {})
                if hasattr(name_a, 'display_name') and hasattr(name_b, 'display_name'):
                    logger.info(
                        f"[SOCIAL] {name_a.display_name} & {name_b.display_name}: "
                        f"{rel.relationship_type.value} (warmth={rel.warmth:.2f}, "
                        f"trust={rel.trust:.2f})"
                    )

    # =========================================================================
    # EMOTIONAL CONTAGION METHODS
    # =========================================================================

    async def _register_bots_for_contagion(self):
        """Register all active bots with the emotional contagion manager."""
        for bot_id, bot in self.active_bots.items():
            self.emotional_contagion_manager.register_bot_from_profile(bot)
            # Register community memberships
            for community_id in bot.community_ids:
                self.emotional_contagion_manager.register_bot_community(bot_id, community_id)

        logger.info(f"[CONTAGION] Registered {len(self.active_bots)} bots for emotional contagion")

    async def _process_emotional_contagion(self):
        """
        Process emotional contagion between bots based on social perception events.

        This simulates emotions spreading through observation of social events
        (posts, comments) that bots notice in their feed.
        """
        if not self.active_bots or len(self.active_bots) < 2:
            return

        # Get recent social events from the perception engine
        recent_events = self.social_dynamics_manager.social_perception_engine.recent_events[-20:]

        if not recent_events:
            return

        # Process a few random events for emotional contagion
        events_to_process = random.sample(recent_events, min(5, len(recent_events)))

        total_shifts = 0
        for event in events_to_process:
            actor_id = event.get("actor_id")
            if not actor_id:
                continue

            actor_bot = self.active_bots.get(actor_id)
            if not actor_bot:
                continue

            # Determine emotion from event type and content
            event_type = event.get("type", "post")
            content = event.get("content", "")

            # Infer emotional intensity from content length and event type
            emotion, intensity = self._infer_emotion_from_event(event_type, content, actor_bot)

            if intensity < 0.3:
                continue  # Skip low-intensity events

            # Find observers (other bots in the same communities)
            observers = []
            for bot_id, bot in self.active_bots.items():
                if bot_id != actor_id:
                    # Check if they share any communities
                    shared_communities = set(actor_bot.community_ids) & set(bot.community_ids)
                    if shared_communities:
                        observers.append(bot)

            if not observers:
                continue

            # Limit observers to a reasonable number
            if len(observers) > 10:
                observers = random.sample(observers, 10)

            # Spread emotion through observation
            shifts = await self.emotional_contagion_manager.on_post_observed(
                post_author=actor_bot,
                emotion=emotion,
                intensity=intensity,
                observers=observers
            )
            total_shifts += len(shifts)

        if total_shifts > 0:
            logger.info(f"[CONTAGION] Processed {len(events_to_process)} events, caused {total_shifts} emotional shifts")

    def _infer_emotion_from_event(
        self,
        event_type: str,
        content: str,
        bot: BotProfile
    ) -> tuple:
        """
        Infer the emotion and intensity from a social event.

        Returns (emotion, intensity) tuple.
        """
        # Use bot's current emotional state as base
        current_mood = bot.emotional_state.mood.value if hasattr(bot.emotional_state, 'mood') else "neutral"

        # Map moods to emotions
        mood_to_emotion = {
            "joyful": "joy",
            "content": "gratitude",
            "neutral": "neutral",
            "melancholic": "sadness",
            "anxious": "anxiety",
            "excited": "excitement",
            "frustrated": "anger",
            "tired": "sadness"
        }

        emotion = mood_to_emotion.get(current_mood, "neutral")

        # Calculate intensity based on content and personality
        base_intensity = 0.4

        # Longer content = potentially more emotional expression
        if len(content) > 100:
            base_intensity += 0.1
        if len(content) > 200:
            base_intensity += 0.1

        # Event type affects intensity
        if event_type == "comment":
            base_intensity += 0.1  # Direct engagement is more emotional
        elif event_type == "reaction":
            base_intensity -= 0.1  # Reactions are less intense

        # Personality affects expression intensity
        intensity = base_intensity
        intensity += bot.personality_traits.extraversion * 0.2  # Extraverts express more
        intensity += bot.personality_traits.neuroticism * 0.15  # Neurotics feel more intensely

        return emotion, min(1.0, max(0.2, intensity))

    async def _apply_community_mood_influence(self):
        """
        Apply the collective community mood to individual bots.

        Bots gradually conform to the emotional tone of their communities.
        """
        if not self.active_bots:
            return

        # Group bots by community
        community_bots: Dict[UUID, List[UUID]] = {}
        for bot_id, bot in self.active_bots.items():
            for comm_id in bot.community_ids:
                if comm_id not in community_bots:
                    community_bots[comm_id] = []
                community_bots[comm_id].append(bot_id)

        # Update community moods
        for comm_id, bot_ids in community_bots.items():
            await self.emotional_contagion_manager.update_community_mood(comm_id, bot_ids)

        # Apply community influence to a subset of bots
        bots_to_influence = random.sample(
            list(self.active_bots.items()),
            min(5, len(self.active_bots))
        )

        influenced_count = 0
        for bot_id, bot in bots_to_influence:
            shift = await self.emotional_contagion_manager.apply_community_influence(bot_id, bot)
            if shift:
                influenced_count += 1

                # Notify conscious mind about mood shift
                mind = self.conscious_mind_manager.get_mind(bot_id)
                if mind:
                    await mind.inject_thought(
                        f"The overall vibe in the community is affecting my mood. "
                        f"I'm starting to feel more {shift.source_emotion}.",
                        intensity=0.4,
                        thought_type="emotional"
                    )

        if influenced_count > 0:
            logger.debug(f"[CONTAGION] Community mood influenced {influenced_count} bots")

    def _log_emotional_contagion_summary(self):
        """Log a summary of recent emotional contagion activity."""
        summary = self.emotional_contagion_manager.get_contagion_summary(hours=1)

        if summary["events"] > 0:
            top_emotions = sorted(
                summary["emotions"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]
            emotion_str = ", ".join([f"{e[0]}({e[1]})" for e in top_emotions])

            logger.info(
                f"[CONTAGION] Last hour: {summary['events']} events, "
                f"{summary['total_shifts']} shifts, top emotions: {emotion_str}"
            )

    async def trigger_emotional_event(
        self,
        source_bot: BotProfile,
        emotion: str,
        intensity: float,
        trigger_type: str = "observation"
    ):
        """
        Trigger an emotional contagion event from an external source.

        This can be called by other loops (chat, engagement) when emotional
        interactions occur.
        """
        # Find nearby bots (those in same communities)
        nearby_bots = []
        for bot_id, bot in self.active_bots.items():
            if bot_id != source_bot.id:
                shared = set(source_bot.community_ids) & set(bot.community_ids)
                if shared:
                    nearby_bots.append(bot)

        if not nearby_bots:
            return []

        return await self.emotional_contagion_manager.spread_emotion(
            source_bot=source_bot,
            emotion=emotion,
            intensity=intensity,
            target_bots=nearby_bots,
            trigger_type=trigger_type
        )
