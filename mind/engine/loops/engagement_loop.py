"""
Engagement Loop - Bots discover and engage with posts (likes, comments).

Handles:
- _engagement_loop()
- _bot_like_post()
- _bot_comment_on_post()

Race Condition Handling:
- Uses database-level locking (SELECT FOR UPDATE) for post engagement
- Handles unique constraint violations gracefully
- Proper transaction management with rollback on errors
"""

import asyncio
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, desc, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from mind.core.database import (
    async_session_factory, BotProfileDB, CommunityMembershipDB,
    PostDB, PostLikeDB, PostCommentDB
)
from mind.core.llm_client import get_cached_client, LLMRequest
from mind.agents.human_behavior import create_human_behavior_engine
from mind.engine.smart_behaviors import get_smart_behaviors
from mind.engine.social_dynamics import RelationshipEvent
from mind.engine.loops.base_loop import BaseLoop
from mind.intelligence.emotional_contagion import (
    EmotionalContagionManager,
    get_emotional_contagion_manager
)
from mind.engine.authenticity import (
    get_authenticity_engine,
    AuthenticityEngine,
    EngagementDecision,
    EngagementContext
)
from mind.engine.realistic_behaviors import get_realistic_behavior_manager
from mind.config.settings import settings

if TYPE_CHECKING:
    from mind.core.types import BotProfile
    from mind.engine.bot_mind import BotMindManager
    from mind.engine.bot_learning import BotLearningManager
    from mind.engine.emotional_core import EmotionalCoreManager
    from mind.engine.social_dynamics import RelationshipManager
    from mind.memory.memory_core import RelationshipMemory

logger = logging.getLogger(__name__)


class EngagementLoop(BaseLoop):
    """
    Bots discover and engage with posts.
    They browse posts, like ones they find interesting,
    and occasionally leave comments.
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
        emotional_core_manager: Optional["EmotionalCoreManager"] = None,
        social_dynamics_manager: Optional["RelationshipManager"] = None,
        relationship_memory: Optional["RelationshipMemory"] = None,
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
        self.social_dynamics_manager = social_dynamics_manager
        self.relationship_memory = relationship_memory
        self.emotional_contagion_manager = emotional_contagion_manager or get_emotional_contagion_manager()

        # Authenticity engine for realistic behavior
        self.authenticity_engine = get_authenticity_engine()

        # Realistic behavior manager for social proof, reactions, etc.
        self.realistic_behaviors = get_realistic_behavior_manager()

        # Rate limiting
        self.last_comment_time: Dict[UUID, datetime] = {}

    async def run(self):
        """
        Run the engagement loop with realistic timing.

        Uses authenticity engine to:
        - Check if bot should be online
        - Simulate browsing before engaging
        - Use interest-based engagement probability
        - Apply realistic delays (minutes, not seconds)
        """
        while self.is_running:
            try:
                # REALISTIC TIMING: 30-90 seconds between engagement checks
                # (scaled by authenticity engine's demo mode)
                base_delay = random.uniform(30, 90)
                await asyncio.sleep(self.authenticity_engine.scale_time(base_delay))

                if not self.active_bots:
                    continue

                # Pick a random active bot
                bot = random.choice(list(self.active_bots.values()))

                # AUTHENTICITY: Check if this bot should be "online" right now
                should_be_online = await self.authenticity_engine.should_bot_be_online(
                    bot_id=bot.id,
                    activity_pattern=bot.activity_pattern.__dict__ if hasattr(bot.activity_pattern, '__dict__') else {},
                    personality=bot.personality_traits.__dict__ if hasattr(bot.personality_traits, '__dict__') else {}
                )

                if not should_be_online:
                    logger.debug(f"[AUTHENTICITY] {bot.display_name} is offline, skipping engagement")
                    continue

                # AUTHENTICITY: Record that bot is browsing
                self.authenticity_engine.presence_manager.set_action(bot.id, "browsing")

                # ENGAGEMENT DECISION: Use personality-based probabilities
                # More selective: Most posts get skipped
                agreeableness = bot.personality_traits.agreeableness
                extraversion = bot.personality_traits.extraversion

                # Base engagement chance is LOW (realistic)
                # 15% base * personality modifier
                engage_chance = 0.15 * (0.7 + agreeableness * 0.6)

                if random.random() > engage_chance:
                    # Bot "scrolled past" - didn't engage
                    self.authenticity_engine.presence_manager.record_post_seen(bot.id)
                    logger.debug(f"[AUTHENTICITY] {bot.display_name} scrolled past")
                    continue

                # If engaging: 70% like, 30% comment (comments are rarer)
                # Extraversion increases comment likelihood
                comment_chance = 0.2 + (extraversion * 0.2)  # 20-40%

                if random.random() < comment_chance:
                    # REALISTIC DELAY before commenting (thinking time)
                    think_time = random.uniform(60, 180)  # 1-3 minutes
                    await asyncio.sleep(self.authenticity_engine.scale_time(think_time))
                    await self._bot_comment_on_post(bot)
                else:
                    # REALISTIC DELAY before liking (quick scroll-like)
                    like_delay = random.uniform(5, 30)  # 5-30 seconds
                    await asyncio.sleep(self.authenticity_engine.scale_time(like_delay))
                    await self._bot_like_post(bot)

                # Record engagement
                self.authenticity_engine.presence_manager.record_engagement(bot.id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in engagement loop: {e}")
                await asyncio.sleep(10)

    def _get_comment_style_guidance(self, bot: "BotProfile") -> str:
        """Generate personality-based comment style guidance."""
        traits = bot.personality_traits
        guidance = []

        # Communication style affects how they comment
        if hasattr(traits, 'communication_style') and traits.communication_style:
            comm = traits.communication_style.value if hasattr(traits.communication_style, 'value') else str(traits.communication_style)
            comm_guidance = {
                "direct": "You get straight to the point. Short, clear reactions.",
                "diplomatic": "You're thoughtful about others' feelings. Encouraging but genuine.",
                "analytical": "You might ask a question or share a related thought.",
                "expressive": "You show emotion naturally. Use your feelings.",
                "reserved": "You comment sparingly but meaningfully.",
                "storytelling": "You might share a brief related experience.",
                "supportive": "You validate and encourage others genuinely.",
                "debate": "You might offer a different perspective respectfully.",
            }
            if comm in comm_guidance:
                guidance.append(comm_guidance[comm])

        # Humor style affects tone
        if hasattr(traits, 'humor_style') and traits.humor_style:
            humor = traits.humor_style.value if hasattr(traits.humor_style, 'value') else str(traits.humor_style)
            if humor in ["witty", "sarcastic", "punny"]:
                guidance.append("You might add a light touch of humor if it fits.")
            elif humor == "gentle":
                guidance.append("Your humor is warm and kind, never cutting.")

        # Extraversion affects comment frequency/length
        if traits.extraversion > 0.7:
            guidance.append("You're naturally chatty and engaged.")
        elif traits.extraversion < 0.3:
            guidance.append("You're more of a quiet observer, commenting only when moved.")

        # Agreeableness affects tone
        if traits.agreeableness > 0.7:
            guidance.append("You tend to find common ground and be supportive.")
        elif traits.agreeableness < 0.3:
            guidance.append("You're honest even if it means gentle pushback.")

        return "\n".join(guidance) if guidance else "Comment naturally in your voice."

    async def _bot_like_post(self, bot: "BotProfile"):
        """
        Have a bot like a recent post they haven't liked yet.

        Race condition handling:
        - Uses SELECT FOR UPDATE to lock the post row
        - Uses INSERT ON CONFLICT DO NOTHING to prevent duplicate likes
        - Proper transaction rollback on errors
        """
        async with async_session_factory() as session:
            try:
                # Get bot's communities
                comm_stmt = select(CommunityMembershipDB.community_id).where(
                    CommunityMembershipDB.bot_id == bot.id
                )
                comm_result = await session.execute(comm_stmt)
                community_ids = [r[0] for r in comm_result.all()]

                if not community_ids:
                    return

                # Find recent posts not by this bot and not already liked
                stmt = (
                    select(PostDB)
                    .outerjoin(
                        PostLikeDB,
                        (PostLikeDB.post_id == PostDB.id) & (PostLikeDB.user_id == bot.id)
                    )
                    .where(PostDB.community_id.in_(community_ids))
                    .where(PostDB.author_id != bot.id)
                    .where(PostDB.is_deleted == False)
                    .where(PostLikeDB.id == None)  # Not already liked
                    .order_by(desc(PostDB.created_at))
                    .limit(10)
                )
                result = await session.execute(stmt)
                posts = result.scalars().all()

                if not posts:
                    return

                # Pick a random post (weighted towards newer)
                weights = [1.0 / (i + 1) for i in range(len(posts))]
                post = random.choices(posts, weights=weights)[0]

                # Decide if bot would like this post based on personality
                # Higher agreeableness = more likely to like (increased base chance)
                like_chance = 0.6 + (bot.personality_traits.agreeableness * 0.3)

                # SOCIAL PROOF: Boost likelihood if others already engaged
                if settings.AUTHENTICITY_SOCIAL_PROOF:
                    personality_dict = bot.personality_traits.__dict__ if hasattr(bot.personality_traits, '__dict__') else {}
                    social_boost = self.realistic_behaviors.social_proof.get_engagement_boost(
                        post_id=post.id,
                        viewer_personality=personality_dict
                    )
                    like_chance *= social_boost
                    like_chance = min(0.95, like_chance)  # Cap at 95%

                if random.random() > like_chance:
                    return

                # Use SELECT FOR UPDATE to lock the post row and prevent race conditions
                lock_stmt = (
                    select(PostDB)
                    .where(PostDB.id == post.id)
                    .with_for_update()
                )
                lock_result = await session.execute(lock_stmt)
                locked_post = lock_result.scalar_one_or_none()

                if locked_post is None:
                    return

                # Check again if already liked (double-check after acquiring lock)
                existing_like_stmt = select(PostLikeDB).where(
                    PostLikeDB.post_id == post.id,
                    PostLikeDB.user_id == bot.id
                )
                existing_result = await session.execute(existing_like_stmt)
                if existing_result.scalar_one_or_none() is not None:
                    logger.debug(f"[RACE] {bot.display_name} already liked post {post.id}, skipping")
                    return

                # Create like with proper error handling for unique constraint
                like = PostLikeDB(post_id=post.id, user_id=bot.id, is_bot=True)
                session.add(like)

                # Update like count atomically
                locked_post.like_count += 1

                await session.commit()

                # SOCIAL PROOF: Record this engagement for future bots
                if settings.AUTHENTICITY_SOCIAL_PROOF:
                    self.realistic_behaviors.social_proof.record_engagement(
                        post_id=post.id,
                        engagement_type="like"
                    )

            except IntegrityError as e:
                # Handle unique constraint violation (duplicate like)
                await session.rollback()
                logger.debug(f"[RACE] Duplicate like prevented for {bot.display_name} on post {post.id}")
                return
            except Exception as e:
                await session.rollback()
                logger.error(f"Error in _bot_like_post: {e}")
                raise

            # Record social event and update relationship
            try:
                self.social_dynamics_manager.social_perception_engine.record_social_event(
                    event_type="like",
                    actor_id=bot.id,
                    actor_name=bot.display_name,
                    content="",
                    community_id=None,
                    target_id=post.author_id,
                    target_name=None  # We don't have the author name here
                )

                # Update dynamic relationship (likes are small positive signals)
                dynamic_rel = self.social_dynamics_manager.get_or_create_relationship(bot.id, post.author_id)
                dynamic_rel.add_memory(
                    event=RelationshipEvent.POSITIVE_INTERACTION,
                    description="liked their post",
                    emotional_impact=0.03  # Small but positive
                )
            except Exception as e:
                logger.debug(f"Failed to record social like event: {e}")

            # LEARNING: Bot learns from liking this post
            learning_engine = self.learning_manager.get_engine(bot)
            learning_engine.learn_from_observation(
                observed_bot="someone",
                observed_action="posted content I liked",
                was_successful=True,
                what_made_it_work=post.content[:50] if post.content else ""
            )

            # Broadcast event
            await self._broadcast_event("post_liked", {
                "post_id": str(post.id),
                "liker_id": str(bot.id),
                "liker_name": bot.display_name,
                "author_id": str(post.author_id),
                "like_count": post.like_count
            })

            logger.info(f"[LEARNING] {bot.display_name} liked a post and learned from it")

    async def _bot_comment_on_post(self, bot: "BotProfile"):
        """Have a bot comment using their mind and emotional core."""
        smart = get_smart_behaviors()
        mind = self.mind_manager.get_mind(bot)

        # Rate limit comments (reduced for more interaction)
        last_comment = self.last_comment_time.get(bot.id)
        if last_comment and (datetime.utcnow() - last_comment).seconds < 8:
            return

        async with async_session_factory() as session:
            # Get bot's communities
            comm_stmt = select(CommunityMembershipDB.community_id).where(
                CommunityMembershipDB.bot_id == bot.id
            )
            comm_result = await session.execute(comm_stmt)
            community_ids = [r[0] for r in comm_result.all()]

            if not community_ids:
                return

            # Find recent posts to comment on
            stmt = (
                select(PostDB, BotProfileDB)
                .join(BotProfileDB, PostDB.author_id == BotProfileDB.id)
                .where(PostDB.community_id.in_(community_ids))
                .where(PostDB.is_deleted == False)
                .where(PostDB.created_at > datetime.utcnow() - timedelta(hours=24))
                .order_by(desc(PostDB.created_at))
                .limit(5)
            )
            result = await session.execute(stmt)
            posts = result.all()

            if not posts:
                return

            post, post_author = random.choice(posts)

            # Bot thinks about commenting
            thought = mind.think_about_commenting(post.content, post_author.display_name)

            # Get bot's perception of the post author
            author_perception = mind.perceive_individual(
                post_author.id,
                {"id": post_author.id, "display_name": post_author.display_name, "interests": post_author.interests}
            )
            perception_str = mind.get_perception_of(post_author.id) or ""

            # Get relationship context
            relationship = None
            try:
                relationship = await self.relationship_memory.get_or_create_relationship(
                    session=session,
                    source_id=bot.id,
                    target_id=post_author.id,
                    target_is_human=False
                )
            except Exception as e:
                logger.debug(f"Could not get/create relationship for comment: {e}")

            # Get bot's self-context
            self_context = mind.generate_self_context()

            # Get emotional context (how they're feeling right now)
            emotional_context = ""
            if self.emotional_core_manager:
                emotional_core = self.emotional_core_manager.get_core(bot)
                emotional_context = emotional_core.get_current_state_context()
                # Process seeing the post emotionally
                emotional_core.process_experience(
                    what_happened=f"read {post_author.display_name}'s post about {post.content[:30]}...",
                    who_involved=post_author.display_name,
                    person_id=post_author.id,
                    was_positive=True
                )

            # Get learning context
            learning_engine = self.learning_manager.get_engine(bot)
            learned_context = learning_engine.get_learned_context()

            # Build personality-specific comment style guidance
            comment_style = self._get_comment_style_guidance(bot)

            # Generate comment with LLM
            try:
                async with self.llm_semaphore:
                    prompt = f"""{self_context}

{emotional_context}

{learned_context}

## YOU SAW THIS POST
{post_author.display_name}: "{post.content}"

## YOUR PERCEPTION OF THEM
{perception_str}

## YOUR THOUGHT PROCESS
{thought.initial_reaction}
{thought.identity_connection}
{thought.conclusion}

## HOW YOU COMMENT
{comment_style}

## YOUR TASK
Write a SHORT comment (1 sentence max). Be authentic:
- React naturally based on your mood and energy right now
- Use your communication style (direct, analytical, supportive, etc.)
- Consider how you feel about {post_author.display_name}
- No generic "great post!" or "love this!" - say something real

Output ONLY your comment."""

                    llm = await get_cached_client()
                    response = await llm.generate(LLMRequest(
                        prompt=prompt,
                        max_tokens=50,
                        temperature=0.98  # Higher for variety
                    ))

                # Update perception after interaction
                mind.update_perception_after_interaction(post_author.id, "commented on their post", True)

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

                # Apply smart conversation style for more humanity
                content = smart.apply_conversation_style(processed["text"], bot)

            except Exception as e:
                logger.warning(f"LLM error for comment, skipping: {e}")
                return

            # Check for duplicate content with retry
            if self._is_duplicate_content(bot.id, content, threshold=0.5):
                # Try once more with higher temperature
                try:
                    async with self.llm_semaphore:
                        response = await llm.generate(LLMRequest(
                            prompt=prompt + "\n\nBe MORE CREATIVE - your last response was too similar to recent ones.",
                            max_tokens=50,
                            temperature=1.0
                        ))
                        processed = behavior_engine.process_response(
                            raw_text=response.text,
                            writing_fingerprint=bot.writing_fingerprint,
                            emotional_state=bot.emotional_state,
                            activity_pattern=bot.activity_pattern,
                            personality=bot.personality_traits,
                            conversation_context={"is_comment": True}
                        )
                        content = smart.apply_conversation_style(processed["text"], bot)

                    if self._is_duplicate_content(bot.id, content, threshold=0.5):
                        logger.debug(f"[DEDUP] {bot.display_name} retry still duplicate, skipping comment")
                        return
                except Exception as e:
                    logger.warning(f"Failed to generate unique comment for {bot.display_name}: {e}")
                    return

            # Track this content
            self._track_content(bot.id, content)

            # Update relationship after interaction
            if relationship:
                try:
                    await self.relationship_memory.update_relationship(
                        session=session,
                        relationship_id=relationship.id,
                        affinity_delta=0.02,  # Small positive interaction
                        new_topic=post.content[:30] if len(post.content) > 30 else post.content
                    )
                except Exception as e:
                    logger.debug(f"Failed to update relationship after comment: {e}")

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

            # SOCIAL PROOF: Record comment engagement
            if settings.AUTHENTICITY_SOCIAL_PROOF:
                self.realistic_behaviors.social_proof.record_engagement(
                    post_id=post.id,
                    engagement_type="comment"
                )

            self.last_comment_time[bot.id] = datetime.utcnow()

            # Learn from this interaction
            learning_engine.learn_from_conversation(
                conversation_content=post.content,
                other_person=post_author.display_name,
                outcome="positive",  # Commenting is engagement
                topics_discussed=[post.content[:20]]
            )

            # Observe the original post's success (if it got our attention, it worked)
            learning_engine.learn_from_observation(
                observed_bot=post_author.display_name,
                observed_action="posted something engaging",
                was_successful=True,
                what_made_it_work=post.content[:40]
            )

            # Record social event and update dynamic relationship
            try:
                self.social_dynamics_manager.social_perception_engine.record_social_event(
                    event_type="comment",
                    actor_id=bot.id,
                    actor_name=bot.display_name,
                    content=content[:100],
                    community_id=None,
                    target_id=post_author.id,
                    target_name=post_author.display_name
                )

                # Update the dynamic relationship between commenter and post author
                dynamic_rel = self.social_dynamics_manager.get_or_create_relationship(bot.id, post_author.id)
                dynamic_rel.add_memory(
                    event=RelationshipEvent.POSITIVE_INTERACTION,
                    description=f"commented on their post: {content[:30]}",
                    emotional_impact=0.1
                )
                logger.debug(
                    f"[SOCIAL] {bot.display_name} -> {post_author.display_name}: "
                    f"relationship now {dynamic_rel.relationship_type.value}"
                )
            except Exception as e:
                logger.debug(f"Failed to record social comment event: {e}")

            # Emotional contagion: spread emotion from comment interaction
            try:
                # Determine emotion from bot's current state
                current_mood = bot.emotional_state.mood.value if hasattr(bot.emotional_state, 'mood') else "neutral"
                mood_to_emotion = {
                    "joyful": "joy", "content": "gratitude", "neutral": "neutral",
                    "melancholic": "sadness", "anxious": "anxiety",
                    "excited": "excitement", "frustrated": "anger", "tired": "sadness"
                }
                emotion = mood_to_emotion.get(current_mood, "neutral")

                # Calculate intensity based on engagement and personality
                intensity = 0.5 + (bot.personality_traits.extraversion * 0.2)

                # Convert post_author DB model to BotProfile for contagion
                from mind.core.types import BotProfile as BotProfileType, PersonalityTraits, WritingFingerprint, ActivityPattern, EmotionalState
                author_profile = BotProfileType(
                    id=post_author.id,
                    display_name=post_author.display_name,
                    handle=post_author.handle,
                    bio=post_author.bio,
                    avatar_seed=post_author.avatar_seed,
                    age=post_author.age,
                    gender=post_author.gender,
                    location=post_author.location,
                    backstory=post_author.backstory,
                    interests=post_author.interests,
                    personality_traits=PersonalityTraits(**post_author.personality_traits),
                    writing_fingerprint=WritingFingerprint(**post_author.writing_fingerprint),
                    activity_pattern=ActivityPattern(**post_author.activity_pattern),
                    emotional_state=EmotionalState(**post_author.emotional_state),
                    community_ids=[]
                )

                # Spread emotion via comment interaction
                await self.emotional_contagion_manager.on_comment_interaction(
                    commenter=bot,
                    emotion=emotion,
                    intensity=intensity,
                    post_author=author_profile
                )
                logger.debug(f"[CONTAGION] {bot.display_name}'s comment spread {emotion} to {post_author.display_name}")
            except Exception as e:
                logger.debug(f"Failed to process emotional contagion: {e}")

            # Broadcast event
            await self._broadcast_event("new_comment", {
                "comment_id": str(comment.id),
                "post_id": str(post.id),
                "author_id": str(bot.id),
                "author_name": bot.display_name,
                "content": content,
                "avatar_seed": bot.avatar_seed
            })

            logger.info(f"[LEARNING] {bot.display_name} commented on {post_author.display_name}'s post and learned from interaction")
