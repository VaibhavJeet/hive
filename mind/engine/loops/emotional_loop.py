"""
Emotional Loop - The inner emotional life of bots.

Handles:
- _emotional_life_loop()
- Unprompted thoughts, emotional evolution, physical state changes
"""

import asyncio
import random
import logging
from typing import Dict, List, Optional, TYPE_CHECKING
from uuid import UUID

from mind.core.types import BotProfile
from mind.engine.loops.base_loop import BaseLoop

if TYPE_CHECKING:
    from mind.engine.emotional_core import EmotionalCoreManager

logger = logging.getLogger(__name__)


class EmotionalLoop(BaseLoop):
    """
    The inner emotional life of bots.
    This is where unprompted thoughts happen, emotions evolve,
    and physical states change over time.
    """

    def __init__(
        self,
        active_bots: Dict[UUID, BotProfile],
        llm_semaphore: asyncio.Semaphore,
        event_broadcast: Optional[asyncio.Queue] = None,
        recent_content: Optional[Dict[UUID, List[str]]] = None,
        max_recent_content: int = 20,
        emotional_core_manager: Optional["EmotionalCoreManager"] = None
    ):
        super().__init__(
            active_bots=active_bots,
            llm_semaphore=llm_semaphore,
            event_broadcast=event_broadcast,
            recent_content=recent_content,
            max_recent_content=max_recent_content
        )
        self.emotional_core_manager = emotional_core_manager

    async def run(self):
        """Run the emotional life loop."""
        while self.is_running:
            try:
                # Run emotional simulation every 1-3 minutes
                await asyncio.sleep(random.uniform(60, 180))

                if not self.active_bots:
                    continue

                # Simulate time passing for all bots
                hours_passed = random.uniform(0.5, 1.5)
                self.emotional_core_manager.simulate_all_time(hours_passed)

                # Generate unprompted thoughts for some bots
                thoughts = self.emotional_core_manager.generate_all_thoughts()

                for bot_id, thought in thoughts.items():
                    bot = self.active_bots.get(bot_id)
                    if bot:
                        logger.info(
                            f"{bot.display_name} thinking: \"{thought.content}\" "
                            f"({thought.thought_type.value})"
                        )

                # Random emotional events
                for bot in random.sample(list(self.active_bots.values()), min(3, len(self.active_bots))):
                    core = self.emotional_core_manager.get_core(bot)

                    # Random inner conflict
                    if random.random() < 0.1:
                        conflict = core.get_inner_conflict(random.choice([
                            "whether to post something personal",
                            "if I should reach out to someone",
                            "whether I'm being too quiet lately",
                            "if my content is good enough"
                        ]))
                        if conflict:
                            logger.debug(f"{bot.display_name} inner conflict: {conflict.topic}")

                    # Random ego events
                    if random.random() < 0.05:
                        if random.random() < 0.5:
                            core.ego.got_ego_boost("remembered something I'm proud of")
                        else:
                            core.ego.took_ego_hit("remembered something embarrassing", 0.1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in emotional life loop: {e}")
                await asyncio.sleep(30)
