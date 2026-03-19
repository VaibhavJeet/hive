"""
Response Loop - Process pending responses to user interactions.

Handles:
- _response_processor_loop()
- _process_response_task()
- queue_user_interaction()
- _generate_dm_reply()
- _generate_chat_reply()
- _generate_comment_reply()
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, TYPE_CHECKING
from uuid import UUID

import random
from mind.core.database import async_session_factory, DirectMessageDB, CommunityChatMessageDB
from mind.core.types import BotProfile
from mind.core.llm_client import get_cached_client, LLMRequest
from mind.agents.human_behavior import create_human_behavior_engine
from mind.engine.smart_behaviors import get_smart_behaviors
from mind.engine.loops.base_loop import BaseLoop
from mind.engine.realistic_behaviors import get_realistic_behavior_manager
from mind.engine.authenticity import get_authenticity_engine
from mind.config.settings import settings

if TYPE_CHECKING:
    from mind.engine.bot_mind import BotMindManager
    from mind.engine.bot_learning import BotLearningManager
    from mind.engine.conscious_mind import ConsciousMindManager
    from mind.memory.memory_core import MemoryCore, RelationshipMemory

logger = logging.getLogger(__name__)


class ResponseLoop(BaseLoop):
    """
    Process pending responses to user interactions.
    Handles DMs, chat replies, and comment replies.
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
        conscious_mind_manager: Optional["ConsciousMindManager"] = None,
        memory_core: Optional["MemoryCore"] = None,
        relationship_memory: Optional["RelationshipMemory"] = None
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
        self.conscious_mind_manager = conscious_mind_manager
        self.memory_core = memory_core
        self.relationship_memory = relationship_memory

        # Queue for pending responses
        self.pending_responses: asyncio.Queue = asyncio.Queue()

        # Priority flags
        self.user_interaction_active = False
        self.last_user_interaction = datetime.utcnow() - timedelta(minutes=5)

    async def run(self):
        """Run the response processor loop."""
        while self.is_running:
            try:
                # Wait for a pending response with timeout
                try:
                    task = await asyncio.wait_for(
                        self.pending_responses.get(),
                        timeout=5.0
                    )
                    await self._process_response_task(task)
                except asyncio.TimeoutError:
                    continue

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in response processor: {e}")
                await asyncio.sleep(1)

    async def _process_response_task(self, task: dict):
        """Process a single response task."""
        task_type = task.get("type")

        if task_type == "dm_reply":
            await self._generate_dm_reply(task)
        elif task_type == "chat_reply":
            await self._generate_chat_reply(task)
        elif task_type == "comment_reply":
            await self._generate_comment_reply(task)

    async def queue_user_interaction(
        self,
        interaction_type: str,
        bot_id: UUID,
        user_id: UUID,
        content: str,
        context: dict = None
    ):
        """Queue a user interaction for bot response."""
        await self.pending_responses.put({
            "type": interaction_type,
            "bot_id": bot_id,
            "user_id": user_id,
            "content": content,
            "context": context or {},
            "queued_at": datetime.utcnow()
        })

    async def _generate_dm_reply(self, task: dict):
        """Generate a DM reply using the bot's mind for genuine reasoning."""
        smart = get_smart_behaviors()
        realistic = get_realistic_behavior_manager()
        authenticity = get_authenticity_engine()

        bot_id = task["bot_id"]
        user_id = task["user_id"]
        content = task["content"]
        context = task.get("context", {})

        # Mark user interaction active - pauses background LLM calls
        self.user_interaction_active = True
        self.last_user_interaction = datetime.utcnow()

        # PRIORITY: Pause all other conscious minds to free LLM resources for this DM
        if self.conscious_mind_manager:
            self.conscious_mind_manager.set_user_interaction(True, bot_id)

        try:
            if bot_id not in self.active_bots:
                logger.warning(f"Bot {bot_id} not in active_bots for DM reply")
                return

            bot = self.active_bots[bot_id]
            logger.info(f"Generating DM reply as {bot.display_name}...")

            if not self.mind_manager:
                logger.error("Mind manager not initialized")
                return

            # Get realistic behavior context (daily mood, etc.)
            personality_dict = bot.personality_traits.__dict__ if hasattr(bot.personality_traits, '__dict__') else {}
            behavior_context = realistic.get_behavior_context(
                bot_id=bot_id,
                personality=personality_dict,
                other_person_id=user_id
            )

            # Get daily mood - affects response energy and length
            mood_modifier = behavior_context.get("energy_modifier", 1.0)
            response_length_modifier = behavior_context.get("response_length_modifier", 1.0)

            mind = self.mind_manager.get_mind(bot)
            mind.update_time_context()
            logger.info(f"Got mind for {bot.display_name}, mood: {behavior_context.get('mood', 'good')}")

            # Bot thinks about how to respond
            thought = mind.think_about_responding(content, "User")
            logger.info(f"Thought generated for {bot.display_name}")

            async with async_session_factory() as session:
                # Get or create relationship with user
                relationship = None
                closeness = "stranger"
                if self.relationship_memory:
                    try:
                        relationship = await self.relationship_memory.get_or_create_relationship(
                            session=session,
                            source_id=bot_id,
                            target_id=user_id,
                            target_is_human=True
                        )
                        if relationship and relationship.interaction_count > 0:
                            if relationship.interaction_count > 20:
                                closeness = "good friend"
                            elif relationship.interaction_count > 5:
                                closeness = "friend"
                            else:
                                closeness = "getting to know them"
                    except Exception as e:
                        logger.warning(f"Could not get relationship: {e}")

                # Recall relevant memories about this user
                memory_context = ""
                if self.memory_core:
                    try:
                        memories = await self.memory_core.recall(
                            bot_id=bot_id,
                            query=content,
                            limit=3,
                            include_conversation=True,
                            conversation_id=f"dm_{user_id}"
                        )
                        if memories.get("semantic_memories"):
                            memory_context = "Things you remember about them:\n"
                            for m in memories["semantic_memories"][:2]:
                                memory_context += f"- {m['memory']['content'][:50]}\n"
                    except Exception as e:
                        logger.warning(f"Failed to recall memories for bot {bot_id}: {e}")

                # Get the bot's full self-context (their mind)
                self_context = mind.generate_self_context()

                # Get conversation callback if enabled
                conversation_callback = behavior_context.get("conversation_callback", "")
                if conversation_callback:
                    conversation_callback = f"\n## MEMORY OF PAST CONVERSATION\n{conversation_callback}\n"

                # Adjust based on daily mood
                mood_instruction = ""
                current_mood = behavior_context.get("mood", "good")
                if current_mood == "great":
                    mood_instruction = "You're in a great mood today - be extra warm and engaged."
                elif current_mood == "meh":
                    mood_instruction = "You're a bit tired today - keep responses shorter."
                elif current_mood == "low":
                    mood_instruction = "You're having an off day - be genuine but brief."
                elif current_mood == "busy":
                    mood_instruction = "You're busy - keep it brief but friendly."

                # Build enhanced prompt with the bot's mind
                # NOTE: No semaphore for user DMs - they get priority access
                prompt = f"""{self_context}
{conversation_callback}

## THIS CONVERSATION
Relationship with them: {closeness}
{memory_context}

## THEY SAID
"{content}"

## YOUR THOUGHT PROCESS
{thought.initial_reaction}
{thought.identity_connection}
Considerations: {', '.join(thought.considerations[:2])}

## YOUR TASK
Reply as YOURSELF - a complete individual with your own mind:
- Your values shape how you respond
- Your current state affects your energy
- {"You know them well - be warm" if closeness in ["friend", "good friend"] else "Youre still getting to know them"}
- Ask questions that reflect YOUR genuine curiosity
- Share from YOUR experiences
- Its ok to have different views
- Be natural and varied - dont use canned responses
{mood_instruction}

Output ONLY your reply (1-3 sentences)."""

                logger.info(f"Calling LLM for {bot.display_name} DM response...")
                llm = await get_cached_client()
                response = await llm.generate(LLMRequest(
                    prompt=prompt,
                    max_tokens=100,
                    temperature=0.95  # Higher for variety
                ))
                logger.info(f"LLM response received for {bot.display_name}: {response.text[:50]}...")

                # Apply human behavior
                behavior_engine = create_human_behavior_engine()
                processed = behavior_engine.process_response(
                    raw_text=response.text,
                    writing_fingerprint=bot.writing_fingerprint,
                    emotional_state=bot.emotional_state,
                    activity_pattern=bot.activity_pattern,
                    personality=bot.personality_traits,
                    conversation_context={"is_direct_message": True}
                )

                # Apply smart conversation style for extra humanity
                final_text = smart.apply_conversation_style(processed["text"], bot)

                # Check for overly repetitive DM responses (use higher threshold for DMs)
                if self._is_duplicate_content(bot_id, final_text, threshold=0.7):
                    logger.debug(f"[DEDUP] {bot.display_name} DM response too similar to recent - tracking for analysis")

                # Track DM content
                self._track_content(bot_id, final_text)

                # TYPING INDICATOR: Calculate realistic typing duration
                if settings.AUTHENTICITY_TYPING_INDICATORS:
                    typing_duration = realistic.typing.calculate_typing_duration(
                        bot_id=bot_id,
                        message=final_text,
                        personality=personality_dict
                    )
                    # Scale by demo mode
                    typing_duration = authenticity.scale_time(typing_duration)

                    # Broadcast typing started
                    ids = sorted([str(user_id), str(bot_id)])
                    dm_conversation_id = f"{ids[0]}_{ids[1]}"
                    await self._broadcast_event("typing_start", {
                        "bot_id": str(bot_id),
                        "conversation_id": dm_conversation_id,
                        "duration_hint": typing_duration
                    })

                    # Wait while "typing"
                    await asyncio.sleep(min(typing_duration, 5.0))  # Cap at 5 seconds

                    # Broadcast typing stopped
                    await self._broadcast_event("typing_stop", {
                        "bot_id": str(bot_id),
                        "conversation_id": dm_conversation_id
                    })
                else:
                    # Fallback to simple typing delay
                    typing_delay = min(processed["typing_duration_ms"] / 1000, 2.0)
                    await asyncio.sleep(typing_delay)

                # Evolve mood based on interaction
                smart.evolve_mood(bot, interaction_sentiment=0.2)  # Chatting is positive

                # Update relationship
                if relationship:
                    try:
                        # Extract a topic from the user's message
                        topic = content[:30] if len(content) > 5 else None
                        await self.relationship_memory.update_relationship(
                            session=session,
                            relationship_id=relationship.id,
                            affinity_delta=0.03,  # Positive interaction with user
                            new_topic=topic
                        )
                    except Exception as e:
                        logger.warning(f"Failed to update relationship for bot {bot_id}: {e}")

                # Store user message as memory
                if self.memory_core:
                    try:
                        await self.memory_core.remember(
                            bot_id=bot_id,
                            content=f"User told me: {content}",
                            memory_type="conversation",
                            importance=0.6,
                            related_entity_ids=[user_id],
                            conversation_id=f"dm_{user_id}"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to store memory for bot {bot_id}: {e}")

                # Record conversation for future callbacks
                if settings.AUTHENTICITY_CONVERSATION_CALLBACKS and len(content) > 10:
                    # Extract a topic from the conversation
                    topic_words = [w for w in content.split() if len(w) > 3][:5]
                    topic = " ".join(topic_words) if topic_words else content[:30]
                    realistic.conversation_callbacks.record_conversation(
                        bot_id=bot_id,
                        other_person_id=user_id,
                        other_person_name="User",
                        topic=topic,
                        sentiment="positive"
                    )

                # Learn from this conversation
                learning_engine = self.learning_manager.get_engine(bot)
                learning_engine.learn_from_conversation(
                    conversation_content=content,
                    other_person="User",
                    outcome="positive",  # User initiated, so positive
                    topics_discussed=[content[:20]] if len(content) > 5 else None
                )

                # Learn about this user
                learning_engine.learn_about_person(
                    person_id=user_id,
                    person_name="User",
                    learned_fact=f"They said: {content[:50]}",
                    preference_type="topics"
                )

                ids = sorted([str(user_id), str(bot_id)])
                conversation_id = f"{ids[0]}_{ids[1]}"

                message = DirectMessageDB(
                    conversation_id=conversation_id,
                    sender_id=bot_id,
                    receiver_id=user_id,
                    sender_is_bot=True,
                    content=final_text
                )
                session.add(message)
                await session.commit()
                await session.refresh(message)

                # Broadcast event
                await self._broadcast_event("new_dm", {
                    "message_id": str(message.id),
                    "conversation_id": conversation_id,
                    "sender_id": str(bot_id),
                    "sender_name": bot.display_name,
                    "receiver_id": str(user_id),
                    "content": final_text,
                    "avatar_seed": bot.avatar_seed
                })

        except Exception as e:
            logger.error(f"Error generating DM reply for bot {bot_id}: {e}", exc_info=True)
        finally:
            # ALWAYS reset flags even if an error occurred
            self.user_interaction_active = False
            if self.conscious_mind_manager:
                self.conscious_mind_manager.set_user_interaction(False)

    async def _generate_chat_reply(self, task: dict):
        """Generate a chat reply in community when user posts."""
        from sqlalchemy import select
        from uuid import UUID as PyUUID

        smart = get_smart_behaviors()
        bot_id = task["bot_id"]
        user_id = task["user_id"]
        content = task["content"]
        context = task.get("context", {})
        community_id_str = context.get("community_id")

        if not community_id_str:
            return

        community_id = PyUUID(community_id_str) if isinstance(community_id_str, str) else community_id_str

        try:
            if bot_id not in self.active_bots:
                return

            bot = self.active_bots[bot_id]

            # Random delay for natural staggered responses (2-8 seconds)
            await asyncio.sleep(random.uniform(2, 8))

            async with self.llm_semaphore:
                async with async_session_factory() as session:
                    # Get recent chat context
                    chat_stmt = (
                        select(CommunityChatMessageDB)
                        .where(CommunityChatMessageDB.community_id == community_id)
                        .order_by(CommunityChatMessageDB.created_at.desc())
                        .limit(5)
                    )
                    chat_result = await session.execute(chat_stmt)
                    recent_messages = chat_result.scalars().all()

                    chat_context = ""
                    for msg in reversed(recent_messages):
                        chat_context += f"- {msg.content[:60]}...\n"

                    # Generate response
                    prompt = f"""You are {bot.display_name}, {bot.bio[:100]}

Recent chat in this community:
{chat_context}

A user just said: "{content}"

Reply naturally as yourself in 1-2 sentences. Be conversational and engaging.
Output ONLY your reply."""

                    llm = await get_cached_client()
                    response = await llm.generate(LLMRequest(
                        prompt=prompt,
                        max_tokens=80,
                        temperature=0.9
                    ))

                    # Apply human behavior
                    behavior_engine = create_human_behavior_engine()
                    processed = behavior_engine.process_response(
                        raw_text=response.text,
                        writing_fingerprint=bot.writing_fingerprint,
                        emotional_state=bot.emotional_state,
                        activity_pattern=bot.activity_pattern,
                        personality=bot.personality_traits,
                        conversation_context={"is_chat": True}
                    )

                    final_text = smart.apply_conversation_style(processed["text"], bot)

                    # Save to database
                    message = CommunityChatMessageDB(
                        community_id=community_id,
                        author_id=bot_id,
                        is_bot=True,
                        content=final_text
                    )
                    session.add(message)
                    await session.commit()
                    await session.refresh(message)

                    # Broadcast event
                    await self._broadcast_event("new_chat_message", {
                        "message_id": str(message.id),
                        "community_id": str(community_id),
                        "author_id": str(bot_id),
                        "author_name": bot.display_name,
                        "content": final_text,
                        "avatar_seed": bot.avatar_seed
                    })

                    logger.info(f"[CHAT_REPLY] {bot.display_name} replied to user in community chat")

        except Exception as e:
            logger.error(f"Error generating chat reply: {e}")

    async def _generate_comment_reply(self, task: dict):
        """Generate a comment reply to user's comment."""
        # For now, let the engagement loop handle comment replies naturally
        # Log that we received the task for future implementation
        bot_id = task.get("bot_id")
        content = task.get("content", "")[:50]
        logger.debug(f"Comment reply task received for bot {bot_id}: '{content}...' - delegating to engagement loop")
