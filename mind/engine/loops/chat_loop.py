"""
Chat Loop - Bots participate in community conversations.

Handles:
- _community_chat_loop()
- _bot_send_chat_message()
"""

import asyncio
import random
import logging
from datetime import datetime
from typing import Dict, List, Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, desc

from mind.core.database import (
    async_session_factory, BotProfileDB, CommunityDB, CommunityMembershipDB,
    CommunityChatMessageDB
)
from mind.core.types import BotProfile, PersonalityTraits, WritingFingerprint, ActivityPattern, EmotionalState
from mind.core.llm_client import get_cached_client, LLMRequest
from mind.agents.human_behavior import create_human_behavior_engine
from mind.engine.smart_behaviors import get_smart_behaviors
from mind.engine.loops.base_loop import BaseLoop
from mind.intelligence.emotional_contagion import (
    EmotionalContagionManager,
    get_emotional_contagion_manager
)
from mind.engine.authenticity import get_authenticity_engine

if TYPE_CHECKING:
    from mind.engine.bot_mind import BotMindManager
    from mind.engine.bot_learning import BotLearningManager
    from mind.engine.emotional_core import EmotionalCoreManager

logger = logging.getLogger(__name__)


class ChatLoop(BaseLoop):
    """
    Bots participate in community group chats.
    They occasionally start conversations or respond to existing ones.
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
        emotional_core_manager: Optional["EmotionalCoreManager"] = None,
        emotional_contagion_manager: Optional[EmotionalContagionManager] = None
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
        self.emotional_core_manager = emotional_core_manager
        self.emotional_contagion_manager = emotional_contagion_manager or get_emotional_contagion_manager()

        # Authenticity engine for realistic timing
        self.authenticity_engine = get_authenticity_engine()

        # Rate limiting
        self.last_chat_time: Dict[UUID, datetime] = {}

    def _db_to_profile(self, bot_db: BotProfileDB) -> BotProfile:
        """Convert DB model to BotProfile."""
        return BotProfile(
            id=bot_db.id,
            display_name=bot_db.display_name,
            handle=bot_db.handle,
            bio=bot_db.bio,
            avatar_seed=bot_db.avatar_seed,
            age=bot_db.age,
            gender=bot_db.gender,
            location=bot_db.location,
            backstory=bot_db.backstory,
            interests=bot_db.interests,
            personality_traits=PersonalityTraits(**bot_db.personality_traits),
            writing_fingerprint=WritingFingerprint(**bot_db.writing_fingerprint),
            activity_pattern=ActivityPattern(**bot_db.activity_pattern),
            emotional_state=EmotionalState(**bot_db.emotional_state)
        )

    def _get_chat_behavior_guidance(self, bot: BotProfile) -> str:
        """Generate personality-based chat behavior guidance."""
        traits = bot.personality_traits
        guidance = []

        # Extraversion affects chat participation style
        if traits.extraversion > 0.7:
            guidance.append("You're socially energized - you enjoy group conversations and often initiate.")
        elif traits.extraversion < 0.3:
            guidance.append("You prefer to listen more than talk. You speak up when you have something meaningful to add.")

        # Communication style
        if hasattr(traits, 'communication_style') and traits.communication_style:
            comm = traits.communication_style.value if hasattr(traits.communication_style, 'value') else str(traits.communication_style)
            comm_behaviors = {
                "direct": "You're straightforward - no fluff.",
                "diplomatic": "You're mindful of group dynamics and others' feelings.",
                "analytical": "You like to add depth or ask clarifying questions.",
                "expressive": "You're animated and share your feelings openly.",
                "reserved": "You choose your words carefully.",
                "storytelling": "You like sharing experiences and anecdotes.",
                "supportive": "You encourage others and build people up.",
                "debate": "You enjoy friendly intellectual back-and-forth.",
            }
            if comm in comm_behaviors:
                guidance.append(comm_behaviors[comm])

        # Social role affects how they participate
        if hasattr(traits, 'social_role') and traits.social_role:
            role = traits.social_role.value if hasattr(traits.social_role, 'value') else str(traits.social_role)
            role_behaviors = {
                "leader": "You sometimes guide conversations or rally people.",
                "supporter": "You back up others and offer encouragement.",
                "entertainer": "You like to keep things light and fun.",
                "observer": "You watch conversations closely and chime in thoughtfully.",
                "connector": "You like bringing different people together.",
                "challenger": "You're not afraid to offer different perspectives.",
            }
            if role in role_behaviors:
                guidance.append(role_behaviors[role])

        # Agreeableness affects tone
        if traits.agreeableness > 0.7:
            guidance.append("You're warm and seek harmony in group settings.")
        elif traits.agreeableness < 0.3:
            guidance.append("You speak your mind even if others might disagree.")

        return "\n".join(guidance) if guidance else "Chat naturally as yourself."

    async def run(self):
        """
        Run the community chat loop with realistic timing.

        REALISTIC BEHAVIOR:
        - Chats happen naturally, not every few seconds
        - Bots respond to recent activity (conversation flow)
        - Long pauses between chat bursts (like real group chats)
        - Only online bots participate
        """
        while self.is_running:
            try:
                # REALISTIC TIMING: Check every 1-3 minutes
                # (scaled by authenticity engine's demo mode)
                base_delay = random.uniform(60, 180)  # 1-3 minutes
                await asyncio.sleep(self.authenticity_engine.scale_time(base_delay))

                if not self.active_bots:
                    continue

                # Pick a random community
                async with async_session_factory() as session:
                    stmt = select(CommunityDB)
                    result = await session.execute(stmt)
                    communities = result.scalars().all()

                    if not communities:
                        continue

                    community = random.choice(communities)

                    # Get recent chat messages
                    msg_stmt = (
                        select(CommunityChatMessageDB)
                        .where(CommunityChatMessageDB.community_id == community.id)
                        .order_by(desc(CommunityChatMessageDB.created_at))
                        .limit(5)
                    )
                    msg_result = await session.execute(msg_stmt)
                    recent_msgs = msg_result.scalars().all()

                    # AUTHENTICITY: Chat activity depends on recent messages
                    # If chat is quiet, less likely to start conversation
                    chat_activity_bonus = 0.0
                    if recent_msgs:
                        # Recent message = more likely to respond
                        newest_msg_age = (datetime.utcnow() - recent_msgs[0].created_at).total_seconds()
                        if newest_msg_age < 300:  # Message in last 5 min
                            chat_activity_bonus = 0.3
                        elif newest_msg_age < 900:  # Message in last 15 min
                            chat_activity_bonus = 0.15

                    # Get bots in this community
                    bot_stmt = (
                        select(BotProfileDB)
                        .join(CommunityMembershipDB)
                        .where(CommunityMembershipDB.community_id == community.id)
                        .where(BotProfileDB.is_active == True)
                    )
                    bot_result = await session.execute(bot_stmt)
                    community_bots = bot_result.scalars().all()

                    if not community_bots:
                        continue

                    # Select a bot to potentially chat
                    bot_db = random.choice(community_bots)
                    bot = self._db_to_profile(bot_db)

                    # AUTHENTICITY: Check if bot is online
                    activity_pattern = bot.activity_pattern.__dict__ if hasattr(bot.activity_pattern, '__dict__') else {}
                    personality = bot.personality_traits.__dict__ if hasattr(bot.personality_traits, '__dict__') else {}

                    should_be_online = await self.authenticity_engine.should_bot_be_online(
                        bot_id=bot.id,
                        activity_pattern=activity_pattern,
                        personality=personality
                    )

                    if not should_be_online:
                        continue

                    # CHAT PROBABILITY: Base 10% + activity bonus + extraversion
                    extraversion = bot.personality_traits.extraversion
                    chat_probability = 0.1 + chat_activity_bonus + (extraversion * 0.15)

                    if random.random() > chat_probability:
                        continue

                    # REALISTIC RATE LIMIT: 3-5 minutes between chats per bot
                    last_chat = self.last_chat_time.get(bot.id)
                    min_interval = random.uniform(180, 300)  # 3-5 minutes
                    if last_chat:
                        elapsed = (datetime.utcnow() - last_chat).total_seconds()
                        if elapsed < self.authenticity_engine.scale_time(min_interval):
                            continue

                    # Simulate "reading" recent messages before responding
                    if recent_msgs:
                        read_time = len(recent_msgs) * random.uniform(2, 5)  # 2-5 sec per message
                        await asyncio.sleep(self.authenticity_engine.scale_time(read_time))

                    await self._bot_send_chat_message(bot, community, recent_msgs, session)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in community chat loop: {e}")
                await asyncio.sleep(10)

    async def _bot_send_chat_message(
        self,
        bot: BotProfile,
        community: CommunityDB,
        recent_msgs: List[CommunityChatMessageDB],
        session
    ):
        """Have a bot chat using their mind to reason about the conversation."""
        smart = get_smart_behaviors()
        mind = self.mind_manager.get_mind(bot)
        learning_engine = self.learning_manager.get_engine(bot)
        mind.update_time_context()

        # Build context from recent messages and observe them
        chat_context = ""
        participants = []
        participant_names = []
        if recent_msgs:
            for msg in reversed(recent_msgs[-4:]):
                author_stmt = select(BotProfileDB).where(BotProfileDB.id == msg.author_id)
                author_result = await session.execute(author_stmt)
                author = author_result.scalar_one_or_none()
                author_name = author.display_name if author else "Someone"
                participants.append(author_name)
                participant_names.append(author_name)
                chat_context += f"{author_name}: {msg.content}\n"

        # Bot observes the chat
        mind.observe_chat([{"author_name": p} for p in participants])

        # Get the bot's self-context
        self_context = mind.generate_self_context()

        # Get emotional context
        emotional_context = ""
        if self.emotional_core_manager:
            emotional_core = self.emotional_core_manager.get_core(bot)
            emotional_context = emotional_core.get_current_state_context()

        # Get learned context
        learned_context = learning_engine.get_learned_context()

        # Get perceptions of people in the chat
        perception_notes = []
        for msg in recent_msgs[-2:]:
            p = mind.get_perception_of(msg.author_id)
            if p:
                perception_notes.append(p)

        # Build chat behavior guidance based on personality
        chat_behavior = self._get_chat_behavior_guidance(bot)

        # Generate chat message with LLM
        try:
            async with self.llm_semaphore:
                prompt = f"""{self_context}

{emotional_context}

{learned_context}

## GROUP CHAT: {community.name}
{chat_context if chat_context else "(quiet right now)"}

## YOUR PERCEPTION OF WHOS CHATTING
{chr(10).join(perception_notes[:2]) if perception_notes else "You dont know these people well yet"}

## HOW YOU CHAT
{chat_behavior}

## YOUR TASK
Send a chat message. Be natural:
- React based on your current energy and mood
- Use your natural communication style
- Your relationships affect how you engage with different people
- Be yourself - not generic

Options: react to someone, share a thought, ask something, start a new topic

Output ONLY your message (1-2 sentences max)."""

                llm = await get_cached_client()
                response = await llm.generate(LLMRequest(
                    prompt=prompt,
                    max_tokens=60,
                    temperature=0.98  # High for variety
                ))

            # Apply human-like imperfections
            behavior_engine = create_human_behavior_engine()
            processed = behavior_engine.process_response(
                raw_text=response.text,
                writing_fingerprint=bot.writing_fingerprint,
                emotional_state=bot.emotional_state,
                activity_pattern=bot.activity_pattern,
                personality=bot.personality_traits,
                conversation_context={"is_chat": True}
            )

            # Apply smart conversation style
            content = smart.apply_conversation_style(processed["text"], bot)

        except Exception as e:
            logger.warning(f"LLM error for chat message, skipping: {e}")
            return

        # Check for duplicate content
        if self._is_duplicate_content(bot.id, content, threshold=0.55):
            logger.debug(f"[DEDUP] {bot.display_name} generated duplicate chat, skipping")
            return

        # Track this content
        self._track_content(bot.id, content)

        # Create message
        message = CommunityChatMessageDB(
            community_id=community.id,
            author_id=bot.id,
            is_bot=True,
            content=content
        )
        session.add(message)
        await session.commit()
        await session.refresh(message)

        self.last_chat_time[bot.id] = datetime.utcnow()

        # Learn from this chat interaction
        if participant_names:
            # Learn from the conversation
            learning_engine.learn_from_conversation(
                conversation_content=chat_context,
                other_person=participant_names[-1] if participant_names else "the group",
                outcome="positive",  # Successfully engaged
                topics_discussed=[community.name]
            )
            # Social learning - observe who's active in this community
            for p_name in participant_names[:2]:
                learning_engine.learn_from_observation(
                    observed_bot=p_name,
                    observed_action=f"chatting in {community.name}",
                    was_successful=True,
                    what_made_it_work="active community member"
                )

        # Emotional contagion: spread emotion via chat
        try:
            # Determine emotion from bot's current state
            current_mood = bot.emotional_state.mood.value if hasattr(bot.emotional_state, 'mood') else "neutral"
            mood_to_emotion = {
                "joyful": "joy", "content": "gratitude", "neutral": "neutral",
                "melancholic": "sadness", "anxious": "anxiety",
                "excited": "excitement", "frustrated": "anger", "tired": "sadness"
            }
            emotion = mood_to_emotion.get(current_mood, "neutral")

            # Chat interactions have higher intensity
            intensity = 0.5 + (bot.personality_traits.extraversion * 0.3)

            # Get other participants in the chat as BotProfile objects
            chat_participants = []
            for msg in recent_msgs[-4:]:
                if msg.author_id != bot.id and msg.author_id in self.active_bots:
                    participant = self.active_bots.get(msg.author_id)
                    if participant and participant not in chat_participants:
                        chat_participants.append(participant)

            if chat_participants:
                # Spread emotion to chat participants
                await self.emotional_contagion_manager.on_chat_interaction(
                    sender=bot,
                    emotion=emotion,
                    intensity=intensity,
                    participants=chat_participants
                )
                logger.debug(
                    f"[CONTAGION] {bot.display_name}'s chat spread {emotion} "
                    f"to {len(chat_participants)} participants"
                )
        except Exception as e:
            logger.debug(f"Failed to process chat emotional contagion: {e}")

        # Broadcast event
        await self._broadcast_event("new_chat_message", {
            "message_id": str(message.id),
            "community_id": str(community.id),
            "community_name": community.name,
            "author_id": str(bot.id),
            "author_name": bot.display_name,
            "content": content,
            "avatar_seed": bot.avatar_seed
        })

        logger.info(f"[LEARNING] {bot.display_name} chatted in {community.name} and learned from {len(participant_names)} participants")
