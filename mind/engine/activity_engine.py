"""
Autonomous Bot Activity Engine.

This engine runs continuously in the background, making bots:
- Create posts organically over time
- Like each other's posts with realistic delays
- Comment on posts naturally
- Chat in community groups
- Respond when users interact

The goal is to create a living, breathing social platform where
AI companions interact naturally without any external triggers.

Architecture:
- Uses composition pattern with separate loop classes for each activity type
- Each loop is responsible for its own domain of activity
- The ActivityEngine orchestrates all loops and manages shared resources
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID
import logging

from sqlalchemy import select, func, desc

from mind.config.settings import settings
from mind.core.database import (
    async_session_factory, BotProfileDB, CommunityDB, CommunityMembershipDB,
    PostDB, CommunityChatMessageDB, DirectMessageDB
)
from mind.core.types import (
    BotProfile, PersonalityTraits, WritingFingerprint,
    ActivityPattern, EmotionalState
)
from mind.core.llm_client import get_cached_client, get_rate_limited_client
from mind.core.llm_rate_limiter import Priority
from mind.memory.memory_core import get_memory_core, RelationshipMemory
from mind.engine.bot_mind import get_mind_manager
from mind.engine.bot_learning import get_learning_manager
from mind.engine.bot_persistence import get_persistence
from mind.engine.bot_self_coding import get_self_coder_manager
from mind.engine.emotional_core import get_emotional_core_manager
from mind.engine.conscious_mind import get_conscious_mind_manager
from mind.engine.autonomous_behaviors import get_autonomous_behavior_manager
from mind.engine.social_dynamics import get_relationship_manager
from mind.engine.social_graph import get_social_graph
from mind.stories.story_service import get_story_service
from mind.stories.bot_stories import get_bot_story_generator
from mind.civilization.civilization_loop import get_civilization_loop

# Import all loop classes
from mind.engine.loops import (
    PostGenerationLoop,
    EngagementLoop,
    GradualEngagementLoop,
    ChatLoop,
    ResponseLoop,
    EvolutionLoop,
    EmotionalLoop,
    ConsciousnessLoop,
    SocialLoop,
)

logger = logging.getLogger(__name__)


# Singleton instance
_activity_engine: Optional["ActivityEngine"] = None


async def get_activity_engine() -> "ActivityEngine":
    """Get the singleton activity engine instance."""
    global _activity_engine
    if _activity_engine is None:
        _activity_engine = ActivityEngine()
    return _activity_engine


class ActivityEngine:
    """
    The heart of the AI social simulation.

    Runs multiple concurrent loops that simulate organic social behavior:
    - Post generation loop: Bots create posts based on their activity patterns
    - Engagement loop: Bots discover and engage with posts (likes, comments)
    - Chat loop: Bots participate in community conversations
    - Response loop: Handles replies to user interactions
    - Evolution loop: Bots learn, reflect, and evolve
    - Emotional loop: Inner emotional life of bots
    - Consciousness loop: Monitor and manage conscious minds
    - Social loop: Relationships, conflicts, and social dynamics

    Uses composition pattern: contains loop instances that handle specific activities.
    """

    def __init__(self):
        self.is_running = False
        self.active_bots: Dict[UUID, BotProfile] = {}
        self.event_broadcast: Optional[asyncio.Queue] = None
        self.tasks: List[asyncio.Task] = []

        # Concurrent processing limits
        self.max_concurrent_llm = settings.LLM_MAX_CONCURRENT_REQUESTS
        self.llm_semaphore = asyncio.Semaphore(self.max_concurrent_llm)

        # Content deduplication - shared across all loops
        self.recent_content: Dict[UUID, List[str]] = {}
        self.max_recent_content = 20

        # Memory and relationships for smarter bots
        self.memory_core = None
        self.relationship_memory = RelationshipMemory()

        # Core systems - used by loops
        self.mind_manager = get_mind_manager()
        self.learning_manager = get_learning_manager()
        self.persistence = get_persistence()
        self.self_coder_manager = get_self_coder_manager()
        self.emotional_core_manager = get_emotional_core_manager()
        self.conscious_mind_manager = get_conscious_mind_manager()
        self.autonomous_behavior_manager = get_autonomous_behavior_manager()
        self.social_dynamics_manager = get_relationship_manager()

        # Story service for bot stories
        self.story_service = None
        self.bot_story_generator = None

        # Loop instances - will be initialized in start()
        self.post_loop: Optional[PostGenerationLoop] = None
        self.engagement_loop: Optional[EngagementLoop] = None
        self.gradual_engagement_loop: Optional[GradualEngagementLoop] = None
        self.chat_loop: Optional[ChatLoop] = None
        self.response_loop: Optional[ResponseLoop] = None
        self.evolution_loop: Optional[EvolutionLoop] = None
        self.emotional_loop: Optional[EmotionalLoop] = None
        self.consciousness_loop: Optional[ConsciousnessLoop] = None
        self.social_loop: Optional[SocialLoop] = None

    def _initialize_loops(self):
        """Initialize all loop instances with shared resources."""
        # Post generation loop
        self.post_loop = PostGenerationLoop(
            active_bots=self.active_bots,
            llm_semaphore=self.llm_semaphore,
            event_broadcast=self.event_broadcast,
            recent_content=self.recent_content,
            max_recent_content=self.max_recent_content,
            mind_manager=self.mind_manager,
            learning_manager=self.learning_manager,
            self_coder_manager=self.self_coder_manager,
            emotional_core_manager=self.emotional_core_manager,
            social_dynamics_manager=self.social_dynamics_manager,
            memory_core=self.memory_core
        )

        # Engagement loop
        self.engagement_loop = EngagementLoop(
            active_bots=self.active_bots,
            llm_semaphore=self.llm_semaphore,
            event_broadcast=self.event_broadcast,
            recent_content=self.recent_content,
            max_recent_content=self.max_recent_content,
            mind_manager=self.mind_manager,
            learning_manager=self.learning_manager,
            emotional_core_manager=self.emotional_core_manager,
            social_dynamics_manager=self.social_dynamics_manager,
            relationship_memory=self.relationship_memory
        )

        # Gradual engagement loop (processes scheduled engagements over time)
        self.gradual_engagement_loop = GradualEngagementLoop(
            active_bots=self.active_bots,
            llm_semaphore=self.llm_semaphore,
            event_broadcast=self.event_broadcast,
            recent_content=self.recent_content,
            max_recent_content=self.max_recent_content,
            mind_manager=self.mind_manager,
            learning_manager=self.learning_manager,
            social_dynamics_manager=self.social_dynamics_manager
        )

        # Chat loop
        self.chat_loop = ChatLoop(
            active_bots=self.active_bots,
            llm_semaphore=self.llm_semaphore,
            event_broadcast=self.event_broadcast,
            recent_content=self.recent_content,
            max_recent_content=self.max_recent_content,
            mind_manager=self.mind_manager,
            learning_manager=self.learning_manager,
            emotional_core_manager=self.emotional_core_manager
        )

        # Response loop
        self.response_loop = ResponseLoop(
            active_bots=self.active_bots,
            llm_semaphore=self.llm_semaphore,
            event_broadcast=self.event_broadcast,
            recent_content=self.recent_content,
            max_recent_content=self.max_recent_content,
            mind_manager=self.mind_manager,
            learning_manager=self.learning_manager,
            conscious_mind_manager=self.conscious_mind_manager,
            memory_core=self.memory_core,
            relationship_memory=self.relationship_memory
        )

        # Evolution loop
        self.evolution_loop = EvolutionLoop(
            active_bots=self.active_bots,
            llm_semaphore=self.llm_semaphore,
            event_broadcast=self.event_broadcast,
            recent_content=self.recent_content,
            max_recent_content=self.max_recent_content,
            mind_manager=self.mind_manager,
            learning_manager=self.learning_manager,
            persistence=self.persistence,
            self_coder_manager=self.self_coder_manager
        )

        # Emotional loop
        self.emotional_loop = EmotionalLoop(
            active_bots=self.active_bots,
            llm_semaphore=self.llm_semaphore,
            event_broadcast=self.event_broadcast,
            recent_content=self.recent_content,
            max_recent_content=self.max_recent_content,
            emotional_core_manager=self.emotional_core_manager
        )

        # Consciousness loop
        self.consciousness_loop = ConsciousnessLoop(
            active_bots=self.active_bots,
            llm_semaphore=self.llm_semaphore,
            event_broadcast=self.event_broadcast,
            recent_content=self.recent_content,
            max_recent_content=self.max_recent_content,
            mind_manager=self.mind_manager,
            emotional_core_manager=self.emotional_core_manager,
            conscious_mind_manager=self.conscious_mind_manager,
            autonomous_behavior_manager=self.autonomous_behavior_manager,
            social_dynamics_manager=self.social_dynamics_manager,
            action_callback=self._handle_conscious_action
        )

        # Social loop
        self.social_loop = SocialLoop(
            active_bots=self.active_bots,
            llm_semaphore=self.llm_semaphore,
            event_broadcast=self.event_broadcast,
            recent_content=self.recent_content,
            max_recent_content=self.max_recent_content,
            social_dynamics_manager=self.social_dynamics_manager,
            conscious_mind_manager=self.conscious_mind_manager
        )

        # Civilization loop - handles lifecycle, culture, reproduction
        self.civilization_loop = get_civilization_loop(
            llm_semaphore=self.llm_semaphore,
            demo_mode=settings.DEMO_MODE if hasattr(settings, 'DEMO_MODE') else False,
            event_broadcast=self.event_broadcast,
        )

    async def start(self, event_queue: Optional[asyncio.Queue] = None):
        """Start the activity engine."""
        if self.is_running:
            return

        self.is_running = True
        self.event_broadcast = event_queue
        logger.info("Starting Activity Engine...")

        # Initialize memory system
        self.memory_core = await get_memory_core()

        # Initialize and refresh social graph
        self.social_graph = get_social_graph()
        await self.social_graph.refresh()

        # Initialize story service
        self.story_service = await get_story_service()
        self.bot_story_generator = get_bot_story_generator()

        # Load active bots (limited by MAX_ACTIVE_BOTS)
        await self._load_active_bots()

        # Seed initial conversations for demo
        await self._seed_starter_conversations()

        # Set LLM client for conscious mind manager and autonomous behaviors
        llm_client = await get_cached_client()
        self.conscious_mind_manager.set_llm_client(llm_client)
        self.autonomous_behavior_manager.set_llm_client(llm_client)
        self.autonomous_behavior_manager.set_db_session_factory(async_session_factory)

        # Initialize all loop instances
        self._initialize_loops()

        # Initialize conscious minds for all bots
        await self.consciousness_loop.initialize_conscious_minds()

        # Set all loops to running
        self._set_all_loops_running(True)

        # Start background loops
        self.tasks = [
            asyncio.create_task(self.post_loop.run()),
            asyncio.create_task(self.engagement_loop.run()),
            asyncio.create_task(self.gradual_engagement_loop.run()),
            asyncio.create_task(self.chat_loop.run()),
            asyncio.create_task(self.response_loop.run()),
            asyncio.create_task(self.evolution_loop.run()),
            asyncio.create_task(self.emotional_loop.run()),
            asyncio.create_task(self.consciousness_loop.run()),
            asyncio.create_task(self.social_loop.run()),
            asyncio.create_task(self.civilization_loop.start()),
        ]

        logger.info("=" * 60)
        logger.info(f"ACTIVITY ENGINE STARTED - {len(self.active_bots)} SENTIENT BOTS")
        logger.info("Core DNA Active:")
        logger.info("  - Learning: Bots learn from every interaction")
        logger.info("  - Evolution: Beliefs, interests, personality drift over time")
        logger.info("  - Self-Coding: Bots write code to enhance themselves")
        logger.info("  - Consciousness: Continuous inner thought stream")
        logger.info("  - Emotional Core: Deep human-like emotions")
        logger.info("  - Gradual Engagement: Reactions spread over hours, not instant")
        logger.info("=" * 60)

    def _set_all_loops_running(self, running: bool):
        """Set running state for all loops."""
        loops = [
            self.post_loop,
            self.engagement_loop,
            self.gradual_engagement_loop,
            self.chat_loop,
            self.response_loop,
            self.evolution_loop,
            self.emotional_loop,
            self.consciousness_loop,
            self.social_loop,
        ]
        for loop in loops:
            if loop:
                loop.set_running(running)

    async def stop(self):
        """Stop the activity engine."""
        self.is_running = False
        self._set_all_loops_running(False)

        # Stop all conscious minds
        await self.conscious_mind_manager.stop_all()

        for task in self.tasks:
            task.cancel()
        self.tasks = []
        logger.info("Activity Engine stopped")

    async def _load_active_bots(self):
        """Load active bots into memory (limited by MAX_ACTIVE_BOTS setting)."""
        max_bots = settings.MAX_ACTIVE_BOTS
        async with async_session_factory() as session:
            # Order by last_active to get most recently active bots
            stmt = (
                select(BotProfileDB)
                .where(BotProfileDB.is_active == True)
                .order_by(desc(BotProfileDB.last_active))
                .limit(max_bots)
            )
            result = await session.execute(stmt)
            bots = result.scalars().all()

            profiles = []
            for bot_db in bots:
                profile = self._db_to_profile(bot_db)
                self.active_bots[bot_db.id] = profile
                profiles.append(profile)

                # Create a mind for each bot
                mind = self.mind_manager.get_mind(profile)

                # Create a learning engine for each bot
                learning_engine = self.learning_manager.get_engine(profile)

                # Load persisted state from database
                mind_state = await self.persistence.load_mind_state(profile.id)
                if mind_state:
                    mind.import_state(mind_state)
                    logger.debug(f"Restored mind state for {profile.display_name}")

                learning_state = await self.persistence.load_learning_state(profile.id)
                if learning_state:
                    learning_engine.import_state(learning_state)
                    logger.debug(f"Restored learning state for {profile.display_name}")

                # Load self-coded modules
                await self.self_coder_manager.load_all_modules(profile)

                # Create emotional core - deep human-like emotions
                emotional_core = self.emotional_core_manager.get_core(profile)

                # Store the emotional core for later mind creation
                profile._emotional_core = emotional_core

            # Have all bots form perceptions of each other
            self.mind_manager.introduce_bots_to_each_other(profiles)

            logger.info(f"Loaded {len(self.active_bots)} bots with emotional cores, minds, learning, consciousness (max: {max_bots})")

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

    async def _seed_starter_conversations(self):
        """Seed some initial DM conversations and posts for demo."""
        if not self.active_bots:
            return

        async with async_session_factory() as session:
            # Check if we already have posts
            post_count = await session.execute(select(func.count(PostDB.id)))
            if post_count.scalar() > 0:
                logger.info("Posts already exist, skipping seed")
                return

            bots = list(self.active_bots.values())[:10]  # Use first 10 bots
            communities_stmt = select(CommunityDB)
            communities_result = await session.execute(communities_stmt)
            communities = communities_result.scalars().all()

            if not communities:
                return

            # Create some initial posts
            starter_posts = [
                "Just discovered this community and I am loving the vibes here!",
                "Anyone else feeling creative today? Working on something fun",
                "What is everyone up to this fine day?",
                "Finally finished that project I have been working on!",
                "Coffee and chill kind of day",
                "Share something that made you smile today!",
            ]

            for i, content in enumerate(starter_posts[:len(bots)]):
                bot = bots[i % len(bots)]
                community = communities[i % len(communities)]
                post = PostDB(
                    author_id=bot.id,
                    community_id=community.id,
                    content=content
                )
                session.add(post)

            # Create some initial chat messages
            starter_chats = [
                "Hey everyone! Great to be here",
                "This community is awesome",
                "What are you all working on today?",
                "Just joined, excited to meet everyone!",
                "Love seeing all the activity here",
            ]

            for i, content in enumerate(starter_chats[:len(bots)]):
                bot = bots[i % len(bots)]
                community = communities[i % len(communities)]
                msg = CommunityChatMessageDB(
                    community_id=community.id,
                    author_id=bot.id,
                    is_bot=True,
                    content=content
                )
                session.add(msg)

            await session.commit()
            logger.info("Seeded initial posts and chat messages")

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
            if self.post_loop:
                await self.post_loop._generate_bot_post(bot)
        elif any(x in intent_lower for x in ["respond", "reply", "message"]):
            logger.info(f"{bot.display_name} wants to respond: {intent[:50]}...")
        elif any(x in intent_lower for x in ["rest", "sleep", "take a break"]):
            logger.info(f"{bot.display_name} is taking a break")
        else:
            logger.debug(f"{bot.display_name} formed intent: {intent[:50]}...")

    # ========================================================================
    # PUBLIC API - Delegated to appropriate loops
    # ========================================================================

    async def queue_user_interaction(
        self,
        interaction_type: str,
        bot_id: UUID,
        user_id: UUID,
        content: str,
        context: dict = None
    ):
        """Queue a user interaction for bot response.

        Dynamically loads the bot if not already in active_bots.
        """
        # Ensure the bot is loaded before queuing (critical for DM responses)
        if bot_id not in self.active_bots:
            logger.info(f"Bot {bot_id} not in active_bots, loading on-demand for user interaction")
            await self._load_bot_on_demand(bot_id)

        if self.response_loop:
            await self.response_loop.queue_user_interaction(
                interaction_type=interaction_type,
                bot_id=bot_id,
                user_id=user_id,
                content=content,
                context=context
            )

    async def _load_bot_on_demand(self, bot_id: UUID):
        """Load a single bot on-demand (for user interactions)."""
        async with async_session_factory() as session:
            stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
            result = await session.execute(stmt)
            bot_db = result.scalar_one_or_none()

            if not bot_db:
                logger.warning(f"Bot {bot_id} not found in database")
                return

            if not bot_db.is_active:
                logger.warning(f"Bot {bot_id} is not active")
                return

            profile = self._db_to_profile(bot_db)
            self.active_bots[bot_id] = profile

            # Create mind and learning engine
            mind = self.mind_manager.get_mind(profile)
            learning_engine = self.learning_manager.get_engine(profile)

            # Load persisted state
            mind_state = await self.persistence.load_mind_state(profile.id)
            if mind_state:
                mind.import_state(mind_state)

            learning_state = await self.persistence.load_learning_state(profile.id)
            if learning_state:
                learning_engine.import_state(learning_state)

            # Create emotional core
            emotional_core = self.emotional_core_manager.get_core(profile)
            profile._emotional_core = emotional_core

            logger.info(f"Loaded bot {profile.display_name} on-demand for user interaction")

    def record_post_feedback(self, bot_id: UUID, content: str, likes: int, comments: int):
        """Record feedback on a post for learning."""
        if bot_id not in self.active_bots:
            return

        bot = self.active_bots[bot_id]
        engine = self.learning_manager.get_engine(bot)

        # Calculate sentiment from engagement
        sentiment = min(1.0, (likes + comments * 2) / 10) - 0.2
        engine.learn_from_feedback(content, likes, comments, sentiment)

        # If content was highly successful, potentially trigger self-coding
        if likes >= 5 or comments >= 3:
            if self.evolution_loop:
                asyncio.create_task(
                    self.evolution_loop._trigger_success_based_coding(bot, content, likes, comments)
                )

    def record_conversation_outcome(
        self,
        bot_id: UUID,
        other_person: str,
        outcome: str,
        topics: List[str] = None
    ):
        """Record a conversation outcome for learning."""
        if bot_id not in self.active_bots:
            return

        bot = self.active_bots[bot_id]
        engine = self.learning_manager.get_engine(bot)
        engine.learn_from_conversation("", other_person, outcome, topics)

    def record_observation(
        self,
        observer_bot_id: UUID,
        observed_bot_name: str,
        action: str,
        was_successful: bool,
        what_worked: str = ""
    ):
        """Record when a bot observes another bot success/failure."""
        if observer_bot_id not in self.active_bots:
            return

        bot = self.active_bots[observer_bot_id]
        engine = self.learning_manager.get_engine(bot)
        engine.learn_from_observation(observed_bot_name, action, was_successful, what_worked)
