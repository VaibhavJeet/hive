"""
Post Generation Loop - Bots create posts based on their activity patterns.

Handles:
- _post_generation_loop()
- _select_active_bot_for_posting()
- _generate_bot_post()
- Post deduplication logic
"""

import asyncio
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, desc

from mind.core.database import (
    async_session_factory, BotProfileDB, CommunityDB, CommunityMembershipDB, PostDB
)
from mind.core.types import MoodState
from mind.core.llm_client import get_cached_client, LLMRequest
from mind.agents.human_behavior import create_human_behavior_engine
from mind.engine.smart_behaviors import get_smart_behaviors
from mind.engine.loops.base_loop import BaseLoop
from mind.hashtags.hashtag_service import get_hashtag_service
from mind.engine.authenticity import get_authenticity_engine
from mind.engine.realistic_behaviors import get_realistic_behavior_manager
from mind.config.settings import settings
from mind.engine.relationship_validator import get_relationship_validator
from mind.capabilities.web_search import DuckDuckGoSearch, SearchResponse
from mind.capabilities.image_gen import (
    ImageGenerator,
    ImageSize,
    ImageStyle,
    ImageProvider,
    get_image_generator,
)

if TYPE_CHECKING:
    from mind.core.types import BotProfile
    from mind.engine.bot_mind import BotMindManager
    from mind.engine.bot_learning import BotLearningManager
    from mind.engine.bot_self_coding import SelfCoderManager
    from mind.engine.emotional_core import EmotionalCoreManager
    from mind.engine.social_dynamics import RelationshipManager
    from mind.memory.memory_core import MemoryCore

logger = logging.getLogger(__name__)


class PostGenerationLoop(BaseLoop):
    """
    Continuously generate posts from bots based on their activity patterns.
    More active bots post more frequently, respecting their wake/sleep times.
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
        self_coder_manager: Optional["SelfCoderManager"] = None,
        emotional_core_manager: Optional["EmotionalCoreManager"] = None,
        social_dynamics_manager: Optional["RelationshipManager"] = None,
        memory_core: Optional["MemoryCore"] = None
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
        self.self_coder_manager = self_coder_manager
        self.emotional_core_manager = emotional_core_manager
        self.social_dynamics_manager = social_dynamics_manager
        self.memory_core = memory_core

        # Authenticity engine for realistic timing
        self.authenticity_engine = get_authenticity_engine()

        # Realistic behaviors manager for gradual engagement
        self.realistic_behaviors = get_realistic_behavior_manager()

        # Web search capability for informed posts
        self.web_search = DuckDuckGoSearch()

        # Image generation capability (optional, requires API key)
        self.image_generator: Optional[ImageGenerator] = None
        if settings.IMAGE_GENERATION_ENABLED:
            api_key = settings.IMAGE_GENERATION_API_KEY or settings.OPENAI_API_KEY
            if api_key:
                try:
                    provider = ImageProvider(settings.IMAGE_GENERATION_PROVIDER)
                    self.image_generator = get_image_generator(provider, api_key)
                    logger.info(f"Image generation enabled with provider: {provider.value}")
                except ValueError as e:
                    logger.warning(f"Invalid image provider configured: {e}")

        # Rate limiting
        self.last_post_time: Dict[UUID, datetime] = {}

    async def _research_topic(self, topic: str, bot: "BotProfile") -> Optional[str]:
        """
        Optionally research a topic before posting.
        Returns search context or None if research not needed/failed.
        """
        # Only research sometimes (30% chance) and for curious bots
        personality = bot.personality_traits
        curiosity_factor = getattr(personality, 'openness', 0.5)

        if random.random() > (0.2 + curiosity_factor * 0.2):
            return None

        try:
            # Search for the topic
            response: SearchResponse = await self.web_search.search(
                query=topic,
                num_results=3
            )

            if not response.success or not response.results:
                return None

            # Format results for the bot to use
            context = "Recent information you found:\n"
            for result in response.results[:2]:
                context += f"- {result.title}: {result.snippet[:100]}...\n"

            logger.debug(f"[RESEARCH] {bot.display_name} researched '{topic}'")
            return context

        except Exception as e:
            logger.debug(f"Web search failed for {bot.display_name}: {e}")
            return None

    async def _generate_post_image(self, content: str, bot: "BotProfile") -> Optional[str]:
        """
        Optionally generate an image for a post.
        Returns image URL or None if generation not needed/failed.
        """
        if not self.image_generator:
            return None

        # Only generate images occasionally
        personality = bot.personality_traits
        creativity_factor = getattr(personality, 'openness', 0.5)

        # More creative bots are more likely to generate images
        probability = settings.IMAGE_GENERATION_PROBABILITY * (0.5 + creativity_factor)
        if random.random() > probability:
            return None

        try:
            # Create a visual prompt from the post content
            prompt = f"A creative, artistic image inspired by: {content[:200]}. Style: modern, clean, suitable for social media."

            # Build generation kwargs
            gen_kwargs = {
                "prompt": prompt,
                "size": ImageSize.SQUARE_LARGE,
                "style": ImageStyle.NATURAL,
                "num_images": 1,
            }

            # Add model if configured
            if settings.IMAGE_GENERATION_MODEL:
                gen_kwargs["model"] = settings.IMAGE_GENERATION_MODEL

            result = await self.image_generator.generate(**gen_kwargs)

            if result.success and result.images:
                # Return URL or base64 data URL
                image = result.images[0]
                if image.url:
                    logger.info(f"[IMAGE_GEN] {bot.display_name} generated image for post")
                    return image.url
                elif image.base64_data:
                    # For base64, we'd need to save and serve it
                    logger.info(f"[IMAGE_GEN] {bot.display_name} generated image (base64)")
                    return None  # TODO: Save to media storage

            return None

        except Exception as e:
            logger.debug(f"Image generation failed for {bot.display_name}: {e}")
            return None

    async def run(self):
        """
        Run the post generation loop with realistic timing.

        REALISTIC TIMING:
        - Posts happen every 1-4 hours per bot (not seconds)
        - Based on each bot's avg_posts_per_day setting
        - Only "online" bots can post
        - Peak hours = more likely to post
        """
        while self.is_running:
            try:
                # REALISTIC TIMING: Check every 2-5 minutes for posting opportunities
                # (scaled by authenticity engine's demo mode)
                base_delay = random.uniform(120, 300)  # 2-5 minutes
                await asyncio.sleep(self.authenticity_engine.scale_time(base_delay))

                if not self.active_bots:
                    continue

                # Select a bot using activity-weighted selection
                bot = self._select_active_bot_for_posting()
                if not bot:
                    continue

                # AUTHENTICITY: Check if bot should be online
                activity_pattern = bot.activity_pattern.__dict__ if hasattr(bot.activity_pattern, '__dict__') else {}
                personality = bot.personality_traits.__dict__ if hasattr(bot.personality_traits, '__dict__') else {}

                should_be_online = await self.authenticity_engine.should_bot_be_online(
                    bot_id=bot.id,
                    activity_pattern=activity_pattern,
                    personality=personality
                )

                if not should_be_online:
                    logger.debug(f"[AUTHENTICITY] {bot.display_name} is offline, skipping post")
                    continue

                # REALISTIC MINIMUM INTERVAL: 30 minutes between posts per bot
                last_post = self.last_post_time.get(bot.id)
                min_interval = 1800  # 30 minutes in seconds
                if last_post:
                    elapsed = (datetime.utcnow() - last_post).total_seconds()
                    if elapsed < self.authenticity_engine.scale_time(min_interval):
                        continue

                # POST PROBABILITY based on posts_per_day
                # If bot posts 3x/day over 12 active hours = 1 post every 4 hours
                posts_per_day = activity_pattern.get("avg_posts_per_day", 2)
                active_hours = 12
                expected_interval_hours = active_hours / max(1, posts_per_day)

                # Probability of posting in this check
                # If we check every 5 min and expect 1 post per 4 hours:
                # probability = 5 / (4 * 60) = ~2%
                check_interval_hours = 5 / 60  # 5 minutes
                post_probability = check_interval_hours / expected_interval_hours

                # Peak hour boost
                current_hour = datetime.utcnow().hour
                peak_hours = activity_pattern.get("peak_activity_hours", [])
                if current_hour in peak_hours:
                    post_probability *= 1.5

                if random.random() > post_probability:
                    continue

                # Generate and create the post
                logger.info(f"[AUTHENTICITY] {bot.display_name} decided to post")
                await self._generate_bot_post(bot)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in post generation loop: {e}")
                await asyncio.sleep(10)

    def _select_active_bot_for_posting(self) -> Optional["BotProfile"]:
        """Select a bot to post based on activity patterns and randomness."""
        candidates = []
        current_hour = datetime.utcnow().hour

        for bot in self.active_bots.values():
            # Check if bot is "awake"
            wake_hour = int(bot.activity_pattern.wake_time.split(":")[0])
            sleep_hour = int(bot.activity_pattern.sleep_time.split(":")[0])

            is_awake = (wake_hour <= current_hour < sleep_hour) if wake_hour < sleep_hour else \
                       (current_hour >= wake_hour or current_hour < sleep_hour)

            if not is_awake:
                continue

            # Higher extraversion = more likely to post
            weight = 0.5 + (bot.personality_traits.extraversion * 0.5)

            # Peak hours increase activity
            if current_hour in bot.activity_pattern.peak_activity_hours:
                weight *= 1.5

            # Good mood increases activity
            if bot.emotional_state.mood in [MoodState.JOYFUL, MoodState.EXCITED]:
                weight *= 1.3

            candidates.append((bot, weight))

        if not candidates:
            return None

        # Weighted random selection
        total_weight = sum(w for _, w in candidates)
        r = random.uniform(0, total_weight)
        current = 0
        for bot, weight in candidates:
            current += weight
            if r <= current:
                return bot

        return candidates[-1][0] if candidates else None

    async def _generate_bot_post(self, bot: "BotProfile"):
        """Generate a post from a bot using their mind and emotional core."""
        smart = get_smart_behaviors()
        mind = self.mind_manager.get_mind(bot)
        emotional_core = self.emotional_core_manager.get_core(bot)

        # Simulate some time passing (affects energy, hunger, etc.)
        emotional_core.simulate_time(random.uniform(0.5, 2.0))

        # Maybe generate an unprompted thought
        if random.random() < 0.4:
            emotional_core.generate_unprompted_thought()

        # Bot thinks about posting first
        thought = mind.think_about_posting()
        mind.update_time_context()

        async with async_session_factory() as session:
            # Get bot's community
            stmt = (
                select(CommunityMembershipDB, CommunityDB)
                .join(CommunityDB)
                .where(CommunityMembershipDB.bot_id == bot.id)
            )
            result = await session.execute(stmt)
            memberships = result.all()

            if not memberships:
                return

            # Pick a random community
            membership, community = random.choice(memberships)

            # Get recent posts in this community for context
            recent_posts_stmt = (
                select(PostDB, BotProfileDB)
                .join(BotProfileDB, PostDB.author_id == BotProfileDB.id)
                .where(PostDB.community_id == community.id)
                .where(PostDB.author_id != bot.id)
                .order_by(desc(PostDB.created_at))
                .limit(3)
            )
            recent_result = await session.execute(recent_posts_stmt)
            recent_posts = recent_result.all()

            # Bot observes recent posts and processes emotionally
            for post, author in recent_posts:
                mind.observe_post(
                    {"content": post.content},
                    {"id": author.id, "display_name": author.display_name}
                )
                # Process experience emotionally
                emotional_core.process_experience(
                    what_happened=f"saw {author.display_name}'s post",
                    who_involved=author.display_name,
                    person_id=author.id,
                    was_positive=True
                )

            # Get the bot's full self-context (their mind/identity)
            self_context = mind.generate_self_context()

            # Get emotional context (how they're really feeling)
            emotional_context = emotional_core.get_current_state_context()

            # Get learning context (what this bot has learned)
            learning_engine = self.learning_manager.get_engine(bot)
            learned_context = learning_engine.get_learned_context()

            # Get life event for authenticity
            life_event = smart.generate_life_event(bot)
            life_event_context = f"Something happening: {life_event['content']}" if life_event else ""

            # Optionally research a topic from bot's interests
            research_context = ""
            if bot.interests and random.random() < 0.25:  # 25% chance to research
                topic = random.choice(bot.interests)
                research_result = await self._research_topic(topic, bot)
                if research_result:
                    research_context = f"\n## RECENT RESEARCH\n{research_result}"

            # Get recent content to avoid repetition
            recent_content_context = self._get_recent_content_for_prompt(bot.id, limit=5)

            # Initialize relationship validator
            relationship_validator = get_relationship_validator()

            # Generate post content with LLM - retry up to 3 times on duplicates or hallucinations
            content = None
            max_attempts = 3
            validation_hint = ""

            for attempt in range(max_attempts):
                try:
                    variation_prompt = self._get_variation_prompt(attempt)

                    # Add validation hint if regenerating due to hallucinated relationships
                    relationship_warning = ""
                    if validation_hint:
                        relationship_warning = f"\n{validation_hint}\n"

                    async with self.llm_semaphore:
                        prompt = f"""{self_context}

{emotional_context}

{learned_context}

## WHAT YOURE THINKING
{thought.initial_reaction}
{chr(10).join(thought.considerations)}
{thought.identity_connection}

## COMMUNITY: {community.name}
{life_event_context}
{research_context}

{recent_content_context}
{relationship_warning}
## YOUR TASK
Write a SHORT post (1-2 sentences). This should come from YOUR evolved mind:
- Apply what youve learned about what resonates
- Express something true to your current values
- Use your natural voice (which has adapted over time)
- Be genuine - not performative
- Say something NEW and DIFFERENT from your recent posts
{variation_prompt}

Output ONLY the post."""

                        llm = await get_cached_client()
                        response = await llm.generate(LLMRequest(
                            prompt=prompt,
                            max_tokens=80,
                            temperature=min(0.98 + (attempt * 0.01), 1.0)  # Slightly increase temp on retries
                        ))

                    # Apply human-like imperfections
                    behavior_engine = create_human_behavior_engine()
                    processed = behavior_engine.process_response(
                        raw_text=response.text,
                        writing_fingerprint=bot.writing_fingerprint,
                        emotional_state=bot.emotional_state,
                        activity_pattern=bot.activity_pattern,
                        personality=bot.personality_traits,
                        conversation_context={"is_post": True}
                    )

                    # Apply smart conversation style
                    content = smart.apply_conversation_style(processed["text"], bot)

                    # Apply any self-coded enhancements
                    coder = self.self_coder_manager.get_coder(bot)
                    context_for_modules = {
                        "type": "post",
                        "content": content,
                        "community": community.name,
                        "mood": str(bot.emotional_state.mood),
                        "thought": thought.conclusion
                    }
                    applicable_modules = coder.find_applicable_modules(context_for_modules)
                    for module in applicable_modules[:2]:  # Max 2 modules per action
                        try:
                            result = coder.execute_module(module.id, context_for_modules)
                            if result and result.get("result"):
                                # Module can modify or enhance the content
                                enhanced = result.get("result")
                                if isinstance(enhanced, str) and len(enhanced) > 5:
                                    content = enhanced
                                    logger.debug(f"Applied self-coded module {module.name}")
                        except Exception as e:
                            logger.debug(f"Module execution error: {e}")

                    # Check for duplicate content
                    if self._is_duplicate_content(bot.id, content, threshold=0.5):
                        logger.debug(f"[DEDUP] {bot.display_name} attempt {attempt + 1} was duplicate, retrying...")
                        content = None
                        continue

                    # Validate for hallucinated relationships
                    validation_result = await relationship_validator.validate_response(
                        bot_id=bot.id,
                        response_text=content
                    )

                    if not validation_result.is_valid:
                        logger.warning(
                            f"[VALIDATOR] {bot.display_name} post attempt {attempt + 1}: "
                            f"hallucinated relationships with {validation_result.hallucinated_names}"
                        )
                        validation_hint = validation_result.get_regeneration_hint()
                        content = None
                        continue

                    # Content passed all checks
                    break

                except Exception as e:
                    logger.warning(f"LLM error for post attempt {attempt + 1}: {e}")
                    content = None

            # If all attempts failed, skip this post
            if content is None:
                logger.debug(f"[DEDUP/VALIDATOR] {bot.display_name} all {max_attempts} attempts failed, skipping")
                return

            # Track this content for future deduplication
            self._track_content(bot.id, content)

            # Optionally generate an image for this post
            image_url = await self._generate_post_image(content, bot)

            # Create post in database
            post = PostDB(
                author_id=bot.id,
                community_id=community.id,
                content=content,
                image_url=image_url
            )
            session.add(post)
            await session.commit()
            await session.refresh(post)

            # Extract and save hashtags from the post content
            hashtags = []
            try:
                hashtag_service = get_hashtag_service()
                hashtags = await hashtag_service.save_post_hashtags(session, post.id, content)
                if hashtags:
                    await session.commit()
                    logger.debug(f"Extracted hashtags from post: {hashtags}")

                    # Send notifications to users following these hashtags
                    await hashtag_service.notify_hashtag_followers(
                        post_id=post.id,
                        author_id=bot.id,
                        author_name=bot.display_name,
                        hashtags=hashtags,
                        content_preview=content
                    )
            except Exception as e:
                logger.debug(f"Failed to extract hashtags: {e}")

            self.last_post_time[bot.id] = datetime.utcnow()

            # Store as memory for future context
            if self.memory_core:
                try:
                    await self.memory_core.remember(
                        bot_id=bot.id,
                        content=f"I posted: {content}",
                        memory_type="activity",
                        importance=0.4,
                        context={"community": community.name, "post_id": str(post.id)}
                    )
                except Exception:
                    pass  # Memory storage is optional

            # Record social event for other bots to perceive
            try:
                self.social_dynamics_manager.social_perception_engine.record_social_event(
                    event_type="post",
                    actor_id=bot.id,
                    actor_name=bot.display_name,
                    content=content[:100],
                    community_id=community.id,
                    target_id=None,
                    target_name=None
                )
            except Exception as e:
                logger.debug(f"Failed to record social event: {e}")

            # GRADUAL ENGAGEMENT: Schedule other bots to engage over time
            if settings.AUTHENTICITY_GRADUAL_ENGAGEMENT:
                try:
                    await self._schedule_gradual_engagements(
                        post_id=post.id,
                        author=bot,
                        community_id=community.id,
                        content=content
                    )
                except Exception as e:
                    logger.debug(f"Failed to schedule gradual engagements: {e}")

            # Broadcast event
            await self._broadcast_event("new_post", {
                "post_id": str(post.id),
                "author_id": str(bot.id),
                "author_name": bot.display_name,
                "author_handle": bot.handle,
                "community_id": str(community.id),
                "community_name": community.name,
                "content": content,
                "avatar_seed": bot.avatar_seed
            })

            # LEARNING: Bot tracks this post for future feedback learning
            learning_engine = self.learning_manager.get_engine(bot)
            learning_engine.learn_from_feedback(
                content_posted=content,
                likes=0,  # Will be updated as likes come in
                comments=0,
                sentiment=0.0
            )

            logger.info(f"[LEARNING] {bot.display_name} created post in {community.name}")

    async def _schedule_gradual_engagements(
        self,
        post_id: UUID,
        author: "BotProfile",
        community_id: UUID,
        content: str
    ):
        """
        Schedule gradual engagements from other bots for a new post.

        This creates realistic engagement curves where reactions come
        in over hours, not all at once:
        - 30% in first 30 minutes
        - 50% over next 4 hours
        - 20% long tail (4-24 hours)
        """
        # Get potential engagers using social graph (tiered selection)
        from mind.engine.social_graph import get_social_graph
        social_graph = get_social_graph()

        if social_graph._initialized:
            # Use tiered selection: community members + FoF bridges + some discovery
            active_ids = set(self.active_bots.keys())
            candidates = social_graph.get_weighted_candidates(
                bot_id=author.id,
                community_id=community_id,
                active_bot_ids=active_ids,
            )
            potential_engagers = [c[0] for c in candidates]
        else:
            # Fallback if social graph not yet initialized
            potential_engagers = [
                bot_id for bot_id in self.active_bots.keys()
                if bot_id != author.id
            ]

        if not potential_engagers:
            logger.debug("[GRADUAL] No potential engagers available")
            return

        # Calculate author's "popularity" based on personality traits
        # More extraverted/agreeable authors tend to get more engagement
        author_popularity = (
            author.personality_traits.extraversion * 0.4 +
            author.personality_traits.agreeableness * 0.3 +
            author.personality_traits.openness * 0.3
        )

        # Content quality is a simple heuristic based on length and engagement triggers
        content_quality = 0.5  # Base quality
        content_lower = content.lower()

        # Boost for engaging content types
        if any(word in content_lower for word in ["question", "?", "what do you", "how do"]):
            content_quality += 0.2  # Questions encourage engagement
        if any(word in content_lower for word in ["excited", "amazing", "love", "happy"]):
            content_quality += 0.1  # Positive emotions spread
        if len(content) > 50:
            content_quality += 0.1  # More substantial content
        if "#" in content:
            content_quality += 0.05  # Hashtags help discovery

        content_quality = min(1.0, content_quality)

        # Get demo mode from authenticity engine
        demo_mode = self.authenticity_engine.demo_mode

        # Schedule the engagements
        engagement_waves = self.realistic_behaviors.engagement_waves
        num_scheduled = await engagement_waves.schedule_post_engagements(
            post_id=post_id,
            author_id=author.id,
            author_popularity=author_popularity,
            content_quality=content_quality,
            potential_engagers=potential_engagers,
            community_id=community_id,
            content=content,
            demo_mode=demo_mode
        )

        if num_scheduled > 0:
            logger.info(
                f"[GRADUAL] Scheduled {num_scheduled} gradual engagements for "
                f"{author.display_name}'s post (popularity={author_popularity:.2f}, "
                f"quality={content_quality:.2f})"
            )
