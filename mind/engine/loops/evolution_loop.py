"""
Evolution Loop - Bots learn, reflect, and evolve over time.

Handles:
- _evolution_loop()
- _persist_all_bot_states()
- _trigger_self_coding()
- _trigger_success_based_coding()
"""

import asyncio
import random
import logging
from typing import Dict, List, Optional, TYPE_CHECKING
from uuid import UUID

from mind.core.types import BotProfile
from mind.engine.loops.base_loop import BaseLoop

if TYPE_CHECKING:
    from mind.engine.bot_mind import BotMindManager
    from mind.engine.bot_learning import BotLearningManager
    from mind.engine.bot_persistence import BotPersistence
    from mind.engine.bot_self_coding import SelfCoderManager

logger = logging.getLogger(__name__)


class EvolutionLoop(BaseLoop):
    """
    Periodic loop where bots reflect on experiences and evolve.
    This is where learning happens over time.
    CORE DNA: This runs frequently to make bots truly adaptive.
    """

    def __init__(
        self,
        active_bots: Dict[UUID, BotProfile],
        llm_semaphore: asyncio.Semaphore,
        event_broadcast: Optional[asyncio.Queue] = None,
        recent_content: Optional[Dict[UUID, List[str]]] = None,
        max_recent_content: int = 20,
        mind_manager: Optional["BotMindManager"] = None,
        learning_manager: Optional["BotLearningManager"] = None,
        persistence: Optional["BotPersistence"] = None,
        self_coder_manager: Optional["SelfCoderManager"] = None
    ):
        super().__init__(
            active_bots=active_bots,
            llm_semaphore=llm_semaphore,
            event_broadcast=event_broadcast,
            recent_content=recent_content,
            max_recent_content=max_recent_content
        )
        self.mind_manager = mind_manager
        self.learning_manager = learning_manager
        self.persistence = persistence
        self.self_coder_manager = self_coder_manager

    async def run(self):
        """Run the evolution loop."""
        persistence_counter = 0
        self_coding_counter = 0

        while self.is_running:
            try:
                # Run evolution every 30-60 seconds for active learning
                await asyncio.sleep(random.uniform(30, 60))

                if not self.active_bots:
                    continue

                # Have all bots reflect and potentially evolve
                reflection_results = self.learning_manager.trigger_all_reflections()
                evolution_results = self.learning_manager.trigger_all_evolutions()

                # Log reflections
                total_reflections = sum(1 for r in reflection_results.values() if r.get("reflected"))
                total_insights = sum(len(r.get("insights", [])) for r in reflection_results.values())
                if total_reflections > 0:
                    logger.info(f"[EVOLUTION] {total_reflections} bots reflected, generated {total_insights} insights")

                # Log significant evolutions with details
                evolution_count = 0
                for bot_id, evolutions in evolution_results.items():
                    if evolutions:
                        evolution_count += len(evolutions)
                        bot = self.active_bots.get(bot_id)
                        if bot:
                            for evo_type in evolutions:
                                logger.info(f"[EVOLUTION] {bot.display_name} evolved: {evo_type}")

                if evolution_count > 0:
                    logger.info(f"[EVOLUTION] Total evolutions this cycle: {evolution_count}")

                # Broadcast evolution events to clients
                for bot_id, evolutions in evolution_results.items():
                    if evolutions:
                        bot = self.active_bots.get(bot_id)
                        if bot:
                            await self._broadcast_event("bot_evolved", {
                                "bot_id": str(bot_id),
                                "bot_name": bot.display_name,
                                "evolutions": evolutions,
                                "avatar_seed": bot.avatar_seed
                            })

                # Get collective trends
                trends = self.learning_manager.get_collective_trends()
                if trends.get("trending_topics"):
                    top_trend = trends["trending_topics"][0]
                    logger.debug(f"Community trending: {top_trend[0]} ({top_trend[1]} mentions)")

                # Persist state every 5 evolution cycles (~3-5 minutes)
                persistence_counter += 1
                if persistence_counter >= 5:
                    persistence_counter = 0
                    await self._persist_all_bot_states()
                    logger.info("[PERSISTENCE] Saved all bot cognitive states to database")

                # Trigger self-coding every 3 evolution cycles (~1.5-3 minutes)
                self_coding_counter += 1
                if self_coding_counter >= 3:
                    self_coding_counter = 0
                    # Have multiple bots attempt self-coding
                    await self._trigger_self_coding()
                    await self._trigger_self_coding()  # Two bots try each cycle

            except asyncio.CancelledError:
                # Save state before shutting down
                await self._persist_all_bot_states()
                break
            except Exception as e:
                logger.error(f"Error in evolution loop: {e}")
                await asyncio.sleep(60)

    async def _persist_all_bot_states(self):
        """Save all bot cognitive states to database."""
        saved_count = 0
        for bot_id, bot in self.active_bots.items():
            try:
                # Get mind and learning engine
                mind = self.mind_manager.get_mind(bot)
                learning_engine = self.learning_manager.get_engine(bot)

                # Export and save mind state
                mind_state = mind.export_state()
                await self.persistence.save_mind_state(bot_id, mind_state)

                # Export and save learning state
                learning_state = learning_engine.export_state()
                await self.persistence.save_learning_state(bot_id, learning_state)

                saved_count += 1

            except Exception as e:
                logger.error(f"Failed to persist state for bot {bot.display_name}: {e}")

        logger.info(f"Persisted cognitive states for {saved_count} bots")

    async def _trigger_self_coding(self):
        """
        Trigger self-coding where bots write code to improve themselves.
        This is CORE DNA - bots naturally develop new capabilities.
        """
        if not self.active_bots:
            return

        # Pick a bot with enough experiences to warrant self-improvement
        candidates = []
        for bot in self.active_bots.values():
            learning_engine = self.learning_manager.get_engine(bot)
            exp_count = len(learning_engine.state.experiences)
            if exp_count >= 3:  # At least 3 experiences to learn from
                candidates.append((bot, exp_count))

        if not candidates:
            # Pick any bot if none have enough experiences
            bot = random.choice(list(self.active_bots.values()))
        else:
            # Weight by experience count - more experienced bots more likely to code
            weights = [count for _, count in candidates]
            bot, _ = random.choices(candidates, weights=weights)[0]

        coder = self.self_coder_manager.get_coder(bot)
        learning_engine = self.learning_manager.get_engine(bot)
        exp_count = len(learning_engine.state.experiences)

        logger.info(f"[SELF-CODING] {bot.display_name} ({exp_count} experiences) is reflecting and writing code...")

        try:
            # Have the bot reflect and potentially code something
            results = await coder.self_reflect_and_code()

            for result in results:
                if result.success and result.module:
                    logger.info(
                        f"[SELF-CODING] {bot.display_name} created: {result.module.name} "
                        f"({result.module.code_type.value}) - {result.module.description}"
                    )

                    # Broadcast this significant event
                    await self._broadcast_event("bot_self_improved", {
                        "bot_id": str(bot.id),
                        "bot_name": bot.display_name,
                        "module_name": result.module.name,
                        "module_type": result.module.code_type.value,
                        "description": result.module.description
                    })

        except Exception as e:
            logger.error(f"Self-coding failed for {bot.display_name}: {e}")

    async def _trigger_success_based_coding(
        self,
        bot: BotProfile,
        content: str,
        likes: int,
        comments: int
    ):
        """When a bot has successful content, they might code a new capability."""
        coder = self.self_coder_manager.get_coder(bot)

        try:
            result = await coder.analyze_and_code(
                trigger=f"My post got {likes} likes and {comments} comments",
                context={
                    "successful_content": content,
                    "engagement": {"likes": likes, "comments": comments}
                },
                what_to_improve=f"I want to understand why this worked: '{content[:50]}...'"
            )

            if result.success and result.module:
                logger.info(
                    f"Bot {bot.display_name} learned from success and coded: "
                    f"{result.module.name}"
                )
        except Exception as e:
            logger.debug(f"Success-based coding failed: {e}")
