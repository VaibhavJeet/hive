"""
Gradual Engagement Loop - Processes scheduled engagements over time.

When a bot posts something, this loop ensures other bots react gradually:
- 30% of engagement in first 30 minutes
- 50% over next 4 hours
- 20% long tail (4-24 hours)

This creates realistic engagement curves instead of instant reactions.
"""

import asyncio
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from mind.core.database import (
    async_session_factory, BotProfileDB, PostDB, PostLikeDB, PostCommentDB
)
from mind.core.llm_client import get_cached_client, LLMRequest
from mind.agents.human_behavior import create_human_behavior_engine
from mind.engine.smart_behaviors import get_smart_behaviors
from mind.engine.social_dynamics import RelationshipEvent
from mind.engine.loops.base_loop import BaseLoop
from mind.engine.authenticity import get_authenticity_engine
from mind.engine.realistic_behaviors import (
    get_realistic_behavior_manager,
    ScheduledEngagement
)
from mind.config.settings import settings

if TYPE_CHECKING:
    from mind.core.types import BotProfile
    from mind.engine.bot_mind import BotMindManager
    from mind.engine.bot_learning import BotLearningManager
    from mind.engine.social_dynamics import RelationshipManager

logger = logging.getLogger(__name__)


class GradualEngagementLoop(BaseLoop):
    """
    Processes scheduled gradual engagements.

    This loop runs continuously and:
    1. Checks for scheduled engagements that are due
    2. Executes them (likes, comments) with realistic behavior
    3. Cleans up old completed engagements

    Works in conjunction with EngagementWaveManager which schedules
    engagements when posts are created.
    """

    def __init__(
        self,
        active_bots: Dict[UUID, "BotProfile"],
        llm_semaphore: asyncio.Semaphore,
        event_broadcast: Optional[asyncio.Queue] = None,
        recent_content: Optional[Dict[UUID, List[str]]] = None,
        max_recent_content: int = 20,
        mind_manager: Optional["BotMindManager"] = None,
        learning_manager: Optional["BotLearningManager"] = None,
        social_dynamics_manager: Optional["RelationshipManager"] = None
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
        self.social_dynamics_manager = social_dynamics_manager

        # Get managers
        self.authenticity_engine = get_authenticity_engine()
        self.realistic_behaviors = get_realistic_behavior_manager()

        # Track last cleanup time
        self._last_cleanup = datetime.utcnow()

    async def run(self):
        """
        Run the gradual engagement processing loop.

        Checks every 5-15 seconds for due engagements and processes them.
        """
        logger.info("[GRADUAL] Gradual engagement loop started")

        while self.is_running:
            try:
                # Check for due engagements every 5-15 seconds
                # (scaled by demo mode)
                check_interval = random.uniform(5, 15)
                await asyncio.sleep(
                    self.authenticity_engine.scale_time(check_interval)
                )

                # Get due engagements
                engagement_waves = self.realistic_behaviors.engagement_waves
                due_engagements = await engagement_waves.get_due_engagements(limit=5)

                if due_engagements:
                    logger.debug(
                        f"[GRADUAL] Processing {len(due_engagements)} due engagements"
                    )

                    for engagement in due_engagements:
                        try:
                            await self._process_engagement(engagement)
                        except Exception as e:
                            logger.error(
                                f"[GRADUAL] Error processing engagement: {e}"
                            )
                            await engagement_waves.mark_engagement_failed(engagement)

                # Periodic cleanup (every hour)
                if (datetime.utcnow() - self._last_cleanup).total_seconds() > 3600:
                    await engagement_waves.cleanup_old_engagements()
                    self._last_cleanup = datetime.utcnow()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[GRADUAL] Error in gradual engagement loop: {e}")
                await asyncio.sleep(10)

        logger.info("[GRADUAL] Gradual engagement loop stopped")

    async def _process_engagement(self, engagement: ScheduledEngagement):
        """Process a single scheduled engagement."""
        engagement_waves = self.realistic_behaviors.engagement_waves

        # Get the bot
        bot = self.active_bots.get(engagement.bot_id)
        if not bot:
            logger.debug(
                f"[GRADUAL] Bot {engagement.bot_id} not active, skipping engagement"
            )
            await engagement_waves.mark_engagement_executed(engagement)
            return

        # Check if bot should be online
        personality = bot.personality_traits.__dict__ if hasattr(
            bot.personality_traits, '__dict__'
        ) else {}
        activity_pattern = bot.activity_pattern.__dict__ if hasattr(
            bot.activity_pattern, '__dict__'
        ) else {}

        should_be_online = await self.authenticity_engine.should_bot_be_online(
            bot_id=bot.id,
            activity_pattern=activity_pattern,
            personality=personality
        )

        if not should_be_online:
            # Reschedule for later (add 10-30 minutes)
            delay = random.uniform(600, 1800)
            engagement.execute_at = datetime.utcnow() + timedelta(
                seconds=self.authenticity_engine.scale_time(delay)
            )
            logger.debug(
                f"[GRADUAL] {bot.display_name} offline, rescheduling engagement"
            )
            return

        # Process based on action type
        if engagement.action == "like":
            success = await self._execute_like(engagement, bot)
        elif engagement.action == "comment":
            success = await self._execute_comment(engagement, bot)
        else:
            logger.warning(f"[GRADUAL] Unknown action: {engagement.action}")
            success = False

        # Mark as executed
        await engagement_waves.mark_engagement_executed(engagement)

        if success:
            logger.info(
                f"[GRADUAL] {bot.display_name} {engagement.action}d post "
                f"{engagement.post_id}"
            )

    async def _execute_like(
        self,
        engagement: ScheduledEngagement,
        bot: "BotProfile"
    ) -> bool:
        """Execute a like action."""
        async with async_session_factory() as session:
            try:
                # Get the post
                post_stmt = select(PostDB).where(
                    PostDB.id == engagement.post_id,
                    PostDB.is_deleted == False
                )
                result = await session.execute(post_stmt)
                post = result.scalar_one_or_none()

                if not post:
                    logger.debug(
                        f"[GRADUAL] Post {engagement.post_id} not found or deleted"
                    )
                    return False

                # Check if already liked
                existing_stmt = select(PostLikeDB).where(
                    PostLikeDB.post_id == post.id,
                    PostLikeDB.user_id == bot.id
                )
                existing = await session.execute(existing_stmt)
                if existing.scalar_one_or_none():
                    logger.debug(
                        f"[GRADUAL] {bot.display_name} already liked post"
                    )
                    return False

                # Create like
                like = PostLikeDB(
                    post_id=post.id,
                    user_id=bot.id,
                    is_bot=True
                )
                session.add(like)
                post.like_count += 1

                await session.commit()

                # Record social proof
                if settings.AUTHENTICITY_SOCIAL_PROOF:
                    self.realistic_behaviors.social_proof.record_engagement(
                        post_id=post.id,
                        engagement_type="like"
                    )

                # Update relationship
                try:
                    if self.social_dynamics_manager and engagement.author_id:
                        self.social_dynamics_manager.social_perception_engine.record_social_event(
                            event_type="like",
                            actor_id=bot.id,
                            actor_name=bot.display_name,
                            content="",
                            community_id=engagement.community_id,
                            target_id=engagement.author_id,
                            target_name=None
                        )

                        dynamic_rel = self.social_dynamics_manager.get_or_create_relationship(
                            bot.id, engagement.author_id
                        )
                        dynamic_rel.add_memory(
                            event=RelationshipEvent.POSITIVE_INTERACTION,
                            description="liked their post",
                            emotional_impact=0.03
                        )
                except Exception as e:
                    logger.debug(f"[GRADUAL] Failed to record social event: {e}")

                # Broadcast event
                await self._broadcast_event("post_liked", {
                    "post_id": str(post.id),
                    "liker_id": str(bot.id),
                    "liker_name": bot.display_name,
                    "author_id": str(engagement.author_id) if engagement.author_id else None,
                    "like_count": post.like_count,
                    "gradual": True,
                })

                # Track cross-community interaction for migration
                if engagement.community_id:
                    try:
                        from mind.engine.social_graph import get_social_graph
                        social_graph = get_social_graph()
                        social_graph.record_cross_community_interaction(
                            bot.id, engagement.community_id
                        )
                    except Exception:
                        pass  # Best-effort tracking

                return True

            except IntegrityError:
                await session.rollback()
                logger.debug(
                    f"[GRADUAL] Duplicate like prevented for {bot.display_name}"
                )
                return False
            except Exception as e:
                await session.rollback()
                logger.error(f"[GRADUAL] Error executing like: {e}")
                return False

    async def _execute_comment(
        self,
        engagement: ScheduledEngagement,
        bot: "BotProfile"
    ) -> bool:
        """Execute a comment action."""
        smart = get_smart_behaviors()

        async with async_session_factory() as session:
            try:
                # Get the post with author
                post_stmt = (
                    select(PostDB, BotProfileDB)
                    .join(BotProfileDB, PostDB.author_id == BotProfileDB.id)
                    .where(
                        PostDB.id == engagement.post_id,
                        PostDB.is_deleted == False
                    )
                )
                result = await session.execute(post_stmt)
                row = result.first()

                if not row:
                    logger.debug(
                        f"[GRADUAL] Post {engagement.post_id} not found"
                    )
                    return False

                post, post_author = row

                # Get bot's mind for generating comment
                mind = self.mind_manager.get_mind(bot) if self.mind_manager else None

                # Generate comment content
                content = await self._generate_comment_content(
                    bot, post, post_author, mind
                )

                if not content:
                    return False

                # Create comment
                comment = PostCommentDB(
                    post_id=post.id,
                    author_id=bot.id,
                    is_bot=True,
                    content=content
                )
                session.add(comment)
                post.comment_count += 1

                await session.commit()
                await session.refresh(comment)

                # Record social proof
                if settings.AUTHENTICITY_SOCIAL_PROOF:
                    self.realistic_behaviors.social_proof.record_engagement(
                        post_id=post.id,
                        engagement_type="comment"
                    )

                # Update relationship
                try:
                    if self.social_dynamics_manager:
                        self.social_dynamics_manager.social_perception_engine.record_social_event(
                            event_type="comment",
                            actor_id=bot.id,
                            actor_name=bot.display_name,
                            content=content[:100],
                            community_id=engagement.community_id,
                            target_id=post_author.id,
                            target_name=post_author.display_name
                        )

                        dynamic_rel = self.social_dynamics_manager.get_or_create_relationship(
                            bot.id, post_author.id
                        )
                        dynamic_rel.add_memory(
                            event=RelationshipEvent.POSITIVE_INTERACTION,
                            description=f"commented on their post: {content[:30]}",
                            emotional_impact=0.1
                        )
                except Exception as e:
                    logger.debug(f"[GRADUAL] Failed to record social event: {e}")

                # Broadcast event
                await self._broadcast_event("new_comment", {
                    "comment_id": str(comment.id),
                    "post_id": str(post.id),
                    "author_id": str(bot.id),
                    "author_name": bot.display_name,
                    "post_author_id": str(post_author.id),
                    "content": content,
                    "avatar_seed": bot.avatar_seed,
                    "gradual": True,
                })

                # Track cross-community interaction for migration
                if engagement.community_id:
                    try:
                        from mind.engine.social_graph import get_social_graph
                        social_graph = get_social_graph()
                        social_graph.record_cross_community_interaction(
                            bot.id, engagement.community_id
                        )
                    except Exception:
                        pass  # Best-effort tracking

                return True

            except Exception as e:
                await session.rollback()
                logger.error(f"[GRADUAL] Error executing comment: {e}")
                return False

    async def _generate_comment_content(
        self,
        bot: "BotProfile",
        post: PostDB,
        post_author: BotProfileDB,
        mind
    ) -> Optional[str]:
        """Generate comment content using LLM."""
        try:
            # Get context for the comment
            self_context = ""
            if mind:
                self_context = mind.generate_self_context()
                thought = mind.think_about_commenting(
                    post.content, post_author.display_name
                )
                thought_context = f"""## YOUR THOUGHT PROCESS
{thought.initial_reaction}
{thought.identity_connection}
{thought.conclusion}"""
            else:
                thought_context = ""

            # Simple prompt for comment
            async with self.llm_semaphore:
                prompt = f"""{self_context}

## YOU SAW THIS POST
{post_author.display_name}: "{post.content}"

{thought_context}

## YOUR TASK
Write a SHORT comment (1 sentence). React naturally:
- Be genuine, not performative
- Say something UNIQUE
- Show your personality

Output ONLY your comment."""

                llm = await get_cached_client()
                response = await llm.generate(LLMRequest(
                    prompt=prompt,
                    max_tokens=50,
                    temperature=0.98
                ))

            # Apply human-like imperfections
            behavior_engine = create_human_behavior_engine()
            processed = behavior_engine.process_response(
                raw_text=response.text,
                writing_fingerprint=bot.writing_fingerprint,
                emotional_state=bot.emotional_state,
                activity_pattern=bot.activity_pattern,
                personality=bot.personality_traits,
                conversation_context={"is_comment": True}
            )

            # Apply smart conversation style
            smart = get_smart_behaviors()
            content = smart.apply_conversation_style(processed["text"], bot)

            # Track for deduplication
            self._track_content(bot.id, content)

            return content

        except Exception as e:
            logger.warning(f"[GRADUAL] Failed to generate comment: {e}")
            return None
