"""
Consciousness Loop - Monitor and manage conscious minds.

Handles:
- _initialize_conscious_minds()
- _build_identity_context()
- _handle_conscious_action()
- _consciousness_monitor_loop()
"""

import asyncio
import logging
from typing import Callable, Dict, List, Optional, TYPE_CHECKING
from uuid import UUID

from mind.core.types import BotProfile
from mind.core.llm_client import get_cached_client
from mind.engine.loops.base_loop import BaseLoop

if TYPE_CHECKING:
    from mind.engine.bot_mind import BotMindManager
    from mind.engine.emotional_core import EmotionalCoreManager
    from mind.engine.conscious_mind import ConsciousMindManager
    from mind.engine.autonomous_behaviors import AutonomousBehaviorManager
    from mind.engine.social_dynamics import RelationshipManager

logger = logging.getLogger(__name__)


class ConsciousnessLoop(BaseLoop):
    """
    Monitor and manage conscious minds of all bots.
    Provides visibility into what bots are thinking.
    """

    def __init__(
        self,
        active_bots: Dict[UUID, BotProfile],
        llm_semaphore: asyncio.Semaphore,
        event_broadcast: Optional[asyncio.Queue] = None,
        recent_content: Optional[Dict[UUID, List[str]]] = None,
        max_recent_content: int = 20,
        mind_manager: Optional["BotMindManager"] = None,
        emotional_core_manager: Optional["EmotionalCoreManager"] = None,
        conscious_mind_manager: Optional["ConsciousMindManager"] = None,
        autonomous_behavior_manager: Optional["AutonomousBehaviorManager"] = None,
        social_dynamics_manager: Optional["RelationshipManager"] = None,
        action_callback: Optional[Callable] = None
    ):
        super().__init__(
            active_bots=active_bots,
            llm_semaphore=llm_semaphore,
            event_broadcast=event_broadcast,
            recent_content=recent_content,
            max_recent_content=max_recent_content
        )
        self.mind_manager = mind_manager
        self.emotional_core_manager = emotional_core_manager
        self.conscious_mind_manager = conscious_mind_manager
        self.autonomous_behavior_manager = autonomous_behavior_manager
        self.social_dynamics_manager = social_dynamics_manager
        self.action_callback = action_callback

    async def initialize_conscious_minds(self):
        """
        Initialize conscious minds for all active bots.
        This is where we create the continuous consciousness for each bot.
        """
        for bot_id, bot in self.active_bots.items():
            try:
                # Get the emotional core (stored during _load_active_bots)
                emotional_core = getattr(bot, '_emotional_core', None)
                if not emotional_core:
                    emotional_core = self.emotional_core_manager.get_core(bot)

                # Build identity context from mind
                mind = self.mind_manager.get_mind(bot)
                identity_context = self._build_identity_context(bot, mind)

                # Create the conscious mind
                conscious_mind = await self.conscious_mind_manager.create_mind(
                    bot_id=bot.id,
                    bot_name=bot.display_name,
                    identity_context=identity_context,
                    emotional_core=emotional_core
                )

                # Create autonomous behaviors for this bot
                autonomous_behaviors = self.autonomous_behavior_manager.get_behavior(
                    bot_id=bot.id,
                    bot_name=bot.display_name
                )

                # Give conscious mind access to event broadcast for world map
                conscious_mind.event_broadcast = self.event_broadcast

                # Connect consciousness to autonomous behaviors
                conscious_mind.set_autonomous_behaviors(autonomous_behaviors)

                # Connect to social dynamics for relationship awareness
                conscious_mind.set_relationship_manager(self.social_dynamics_manager)

                # Register action callback so consciousness can trigger actions
                if self.action_callback:
                    conscious_mind.register_action_callback(self.action_callback)

                logger.info(f"Awakened consciousness with agency for {bot.display_name}")

            except Exception as e:
                logger.error(f"Failed to create conscious mind for {bot.display_name}: {e}")

    def _build_identity_context(self, bot: BotProfile, mind) -> str:
        """Build identity context for the conscious mind."""
        identity = mind.identity

        values = ", ".join([v.name.replace("_", " ") for v in identity.core_values[:5]])
        quirks = ", ".join(identity.speech_quirks[:3]) if identity.speech_quirks else "none"
        passions = ", ".join(identity.passions[:3]) if identity.passions else "none"
        pet_peeves = ", ".join(identity.pet_peeves[:3]) if identity.pet_peeves else "none"

        return f"""I am {bot.display_name} (@{bot.handle}).

BIO: {bot.bio}

CORE VALUES: {values}
PASSIONS: {passions}
PET PEEVES: {pet_peeves}
SPEECH STYLE: {quirks}

BACKSTORY: {bot.backstory}

PERSONALITY:
- Extraversion: {bot.personality_traits.extraversion:.1f}
- Agreeableness: {bot.personality_traits.agreeableness:.1f}
- Openness: {bot.personality_traits.openness:.1f}
- Neuroticism: {bot.personality_traits.neuroticism:.1f}
- Conscientiousness: {bot.personality_traits.conscientiousness:.1f}

INTERESTS: {', '.join(bot.interests[:5])}"""

    async def _handle_conscious_action(self, bot_id: UUID, intent: str):
        """
        Handle actions that emerge from consciousness.
        The conscious mind may form intentions to act - this executes them.
        """
        bot = self.active_bots.get(bot_id)
        if not bot:
            return

        intent_lower = intent.lower()

        # Parse intent and trigger appropriate action
        if any(x in intent_lower for x in ["post", "share", "write something"]):
            if self.action_callback:
                await self.action_callback(bot_id, "post")
        elif any(x in intent_lower for x in ["respond", "reply", "message"]):
            # This would trigger a response - for now just log
            logger.info(f"{bot.display_name} wants to respond: {intent[:50]}...")
        elif any(x in intent_lower for x in ["rest", "sleep", "take a break"]):
            logger.info(f"{bot.display_name} is taking a break")
        else:
            logger.debug(f"{bot.display_name} formed intent: {intent[:50]}...")

    async def run(self):
        """Run the consciousness monitor loop."""
        while self.is_running:
            try:
                # Run monitoring every 5 minutes
                await asyncio.sleep(300)

                if not self.active_bots:
                    continue

                # Get states from all conscious minds
                states = self.conscious_mind_manager.get_all_states()

                # Log summary of consciousness states
                for bot_id, state in states.items():
                    bot = self.active_bots.get(bot_id)
                    if not bot:
                        continue

                    recent = state.get("recent_thoughts", [])
                    if recent:
                        latest = recent[-1]
                        logger.info(
                            f"[CONSCIOUSNESS] {bot.display_name} ({state.get('current_mode', '?')}): "
                            f"\"{latest.get('content', '')[:60]}...\""
                        )

                        # Broadcast thought for world map visualization
                        await self._broadcast_event("bot_thought", {
                            "bot_id": str(bot_id),
                            "bot_name": bot.display_name,
                            "mode": state.get("current_mode", "wandering"),
                            "content": latest.get("content", "")[:120],
                            "emotional_tone": latest.get("emotional_tone", "neutral"),
                        })

                    # Log any active goals
                    goals = state.get("active_goals", [])
                    for goal in goals[:2]:
                        if goal.get("emotional_investment", 0) > 0.5:
                            logger.debug(
                                f"{bot.display_name} pursuing: {goal.get('description', '?')[:40]}... "
                                f"({goal.get('progress', 0)*100:.0f}%)"
                            )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in consciousness monitor loop: {e}")
                await asyncio.sleep(60)
