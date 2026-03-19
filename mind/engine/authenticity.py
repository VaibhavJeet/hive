"""
Authenticity Layer - Makes bot behavior feel genuinely human.

This module adds realistic human-like patterns to bot interactions:
- Reading/viewing delay before reactions
- Feed browsing simulation (see many, engage few)
- Interest-based engagement filtering
- Realistic timing (minutes/hours, not seconds)
- Online presence management
- Engagement selectivity (most posts get ignored)

The goal: When you look at the feed, you can't tell bots from humans.
"""

import asyncio
import random
import math
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from uuid import UUID

from mind.config.settings import settings

logger = logging.getLogger(__name__)


# =============================================================================
# PRESENCE SYSTEM - Track when bots are "online"
# =============================================================================

class PresenceStatus(str, Enum):
    """Bot's current presence status."""
    ONLINE = "online"
    AWAY = "away"
    BUSY = "busy"
    OFFLINE = "offline"
    SLEEPING = "sleeping"


@dataclass
class BotPresence:
    """Tracks a bot's online presence and activity."""
    bot_id: UUID
    status: PresenceStatus = PresenceStatus.OFFLINE
    last_seen: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    current_action: Optional[str] = None  # "browsing", "typing", "reading"
    session_start: Optional[datetime] = None
    session_duration_minutes: int = 0  # How long they'll be online this session

    # Activity tracking
    posts_seen_this_session: int = 0
    posts_engaged_this_session: int = 0
    messages_sent_this_session: int = 0

    def is_online(self) -> bool:
        return self.status in [PresenceStatus.ONLINE, PresenceStatus.BUSY]

    def time_since_last_activity(self) -> timedelta:
        return datetime.utcnow() - self.last_activity

    def should_go_offline(self) -> bool:
        """Check if bot should end their session."""
        if not self.session_start:
            return True
        session_length = (datetime.utcnow() - self.session_start).total_seconds() / 60
        return session_length >= self.session_duration_minutes


class PresenceManager:
    """
    Manages bot online/offline states realistically.

    Bots don't stay online 24/7. They:
    - Come online for sessions (15-90 minutes)
    - Go offline between sessions
    - Have "last seen" timestamps
    - Show what they're currently doing
    """

    def __init__(self):
        self._presence: Dict[UUID, BotPresence] = {}
        self._session_callbacks: List[callable] = []

    def get_presence(self, bot_id: UUID) -> BotPresence:
        """Get or create presence for a bot."""
        if bot_id not in self._presence:
            self._presence[bot_id] = BotPresence(bot_id=bot_id)
        return self._presence[bot_id]

    def start_session(
        self,
        bot_id: UUID,
        activity_pattern: dict,
        personality: dict
    ) -> BotPresence:
        """
        Start an online session for a bot.

        Session duration based on:
        - Extraversion (extraverts stay longer)
        - Time of day (longer during peak hours)
        - Random variation
        """
        presence = self.get_presence(bot_id)

        # Base session: 15-45 minutes
        base_duration = random.randint(15, 45)

        # Extraverts stay online longer
        extraversion = personality.get("extraversion", 0.5)
        duration_modifier = 1.0 + (extraversion * 0.5)  # 1.0x to 1.5x

        # Peak hours = longer sessions
        current_hour = datetime.utcnow().hour
        peak_hours = activity_pattern.get("peak_activity_hours", [12, 13, 18, 19, 20])
        if current_hour in peak_hours:
            duration_modifier *= 1.3

        # Weekend modifier
        if datetime.utcnow().weekday() >= 5:
            duration_modifier *= activity_pattern.get("weekend_activity_multiplier", 1.2)

        session_duration = int(base_duration * duration_modifier)

        presence.status = PresenceStatus.ONLINE
        presence.session_start = datetime.utcnow()
        presence.session_duration_minutes = session_duration
        presence.last_seen = datetime.utcnow()
        presence.posts_seen_this_session = 0
        presence.posts_engaged_this_session = 0
        presence.messages_sent_this_session = 0

        logger.debug(f"Bot {bot_id} started session ({session_duration} min)")
        return presence

    def end_session(self, bot_id: UUID) -> None:
        """End a bot's online session."""
        presence = self.get_presence(bot_id)
        presence.status = PresenceStatus.OFFLINE
        presence.last_seen = datetime.utcnow()
        presence.current_action = None
        presence.session_start = None

        logger.debug(
            f"Bot {bot_id} ended session "
            f"(saw {presence.posts_seen_this_session}, engaged {presence.posts_engaged_this_session})"
        )

    def set_action(self, bot_id: UUID, action: str) -> None:
        """Set what the bot is currently doing."""
        presence = self.get_presence(bot_id)
        presence.current_action = action
        presence.last_activity = datetime.utcnow()

    def record_post_seen(self, bot_id: UUID) -> None:
        """Record that bot saw a post."""
        presence = self.get_presence(bot_id)
        presence.posts_seen_this_session += 1
        presence.last_activity = datetime.utcnow()

    def record_engagement(self, bot_id: UUID) -> None:
        """Record that bot engaged with something."""
        presence = self.get_presence(bot_id)
        presence.posts_engaged_this_session += 1
        presence.last_activity = datetime.utcnow()

    def get_online_bots(self) -> List[UUID]:
        """Get list of currently online bots."""
        return [
            bot_id for bot_id, presence in self._presence.items()
            if presence.is_online()
        ]

    def get_last_seen(self, bot_id: UUID) -> Optional[datetime]:
        """Get when a bot was last seen."""
        presence = self._presence.get(bot_id)
        return presence.last_seen if presence else None


# =============================================================================
# READING/VIEWING SIMULATION
# =============================================================================

@dataclass
class ViewingBehavior:
    """Simulates how a human views/reads content."""

    # Words per minute reading speed (varies by person)
    reading_speed_wpm: int = 200

    # Time to process an image (seconds)
    image_viewing_time: float = 2.0

    # Base "scroll pause" time when seeing a post (seconds)
    scroll_pause_base: float = 0.5

    # Probability of actually reading vs. scrolling past
    read_probability: float = 0.4

    def calculate_viewing_time(
        self,
        content: str,
        has_image: bool = False,
        is_interesting: bool = False
    ) -> float:
        """
        Calculate how long a human would spend viewing this content.

        Returns time in seconds.
        """
        # Base scroll pause
        time_seconds = self.scroll_pause_base

        # If they decide to read it
        if random.random() < self.read_probability or is_interesting:
            # Reading time based on word count
            word_count = len(content.split())
            reading_time = (word_count / self.reading_speed_wpm) * 60
            time_seconds += reading_time

            # Image viewing
            if has_image:
                time_seconds += self.image_viewing_time * random.uniform(0.5, 1.5)

            # Interesting content = read more carefully
            if is_interesting:
                time_seconds *= random.uniform(1.2, 1.8)

        # Add human randomness
        time_seconds *= random.uniform(0.7, 1.3)

        return max(0.3, time_seconds)  # Minimum 0.3s


class FeedBrowser:
    """
    Simulates a human browsing their feed.

    Instead of bots immediately engaging with posts, this simulates:
    1. Opening the app
    2. Scrolling through multiple posts
    3. Reading some, skipping others
    4. Deciding which few to engage with
    """

    def __init__(
        self,
        presence_manager: PresenceManager,
        viewing_behavior: Optional[ViewingBehavior] = None
    ):
        self.presence_manager = presence_manager
        self.viewing_behavior = viewing_behavior or ViewingBehavior()

        # Track what each bot has seen (to avoid re-showing)
        self._seen_posts: Dict[UUID, set] = {}

    def get_seen_posts(self, bot_id: UUID) -> set:
        """Get posts this bot has already seen."""
        if bot_id not in self._seen_posts:
            self._seen_posts[bot_id] = set()
        return self._seen_posts[bot_id]

    def mark_post_seen(self, bot_id: UUID, post_id: UUID) -> None:
        """Mark a post as seen by this bot."""
        self.get_seen_posts(bot_id).add(post_id)
        self.presence_manager.record_post_seen(bot_id)

    async def browse_feed(
        self,
        bot_id: UUID,
        available_posts: List[dict],
        bot_interests: List[str],
        bot_personality: dict,
        max_posts_to_view: int = 10
    ) -> List[dict]:
        """
        Simulate browsing and return posts the bot might engage with.

        This filters the feed like a human would:
        1. Skip already-seen posts
        2. Scroll past uninteresting content
        3. Pause on interesting posts
        4. Return only posts worth engaging with

        Returns: List of posts the bot decided to potentially engage with
        """
        self.presence_manager.set_action(bot_id, "browsing")

        seen = self.get_seen_posts(bot_id)
        candidates_for_engagement = []

        # Filter to unseen posts
        unseen_posts = [p for p in available_posts if p.get("id") not in seen]

        if not unseen_posts:
            return []

        # Shuffle to simulate non-chronological feed algorithms
        posts_to_view = unseen_posts[:max_posts_to_view]
        random.shuffle(posts_to_view)

        for post in posts_to_view:
            post_id = post.get("id")
            content = post.get("content", "")
            author_id = post.get("author_id")

            # Mark as seen
            self.mark_post_seen(bot_id, post_id)

            # Calculate interest level
            interest_score = self._calculate_interest(
                content=content,
                post=post,
                bot_interests=bot_interests,
                bot_personality=bot_personality
            )

            # Simulate viewing time
            is_interesting = interest_score > 0.5
            viewing_time = self.viewing_behavior.calculate_viewing_time(
                content=content,
                has_image=post.get("has_image", False),
                is_interesting=is_interesting
            )

            # Actually wait (scaled down for simulation)
            await asyncio.sleep(viewing_time * 0.1)  # 10% of real time

            # Decide if this is worth engaging with
            engage_threshold = 0.3 + (random.random() * 0.4)  # 0.3-0.7

            if interest_score > engage_threshold:
                candidates_for_engagement.append({
                    **post,
                    "interest_score": interest_score,
                    "viewing_time": viewing_time
                })

        self.presence_manager.set_action(bot_id, None)

        # Sort by interest and return top candidates
        candidates_for_engagement.sort(key=lambda x: x["interest_score"], reverse=True)

        return candidates_for_engagement[:3]  # Max 3 posts to potentially engage with

    def _calculate_interest(
        self,
        content: str,
        post: dict,
        bot_interests: List[str],
        bot_personality: dict
    ) -> float:
        """
        Calculate how interesting a post is to this specific bot.

        Factors:
        - Topic overlap with bot's interests
        - Author relationship (friends' posts are more interesting)
        - Post quality indicators (length, engagement)
        - Personality fit
        """
        score = 0.3  # Base interest
        content_lower = content.lower()

        # Interest match - check if post relates to bot's interests
        for interest in bot_interests:
            if interest.lower() in content_lower:
                score += 0.15

        # Post engagement - popular posts catch attention
        like_count = post.get("like_count", 0)
        comment_count = post.get("comment_count", 0)
        if like_count > 5:
            score += 0.1
        if comment_count > 2:
            score += 0.1

        # Content length - very short might be skipped, very long might be skimmed
        word_count = len(content.split())
        if 10 < word_count < 50:
            score += 0.05  # Good length
        elif word_count > 100:
            score -= 0.1  # Too long, might skip

        # Personality factors
        openness = bot_personality.get("openness", 0.5)
        score += (openness - 0.5) * 0.2  # More open = more interested in content

        # Extraversion affects engagement likelihood
        extraversion = bot_personality.get("extraversion", 0.5)
        score += (extraversion - 0.5) * 0.1

        # Random human factor
        score += random.uniform(-0.1, 0.1)

        return max(0.0, min(1.0, score))


# =============================================================================
# ENGAGEMENT DECISION ENGINE
# =============================================================================

class EngagementDecision(str, Enum):
    """What the bot decides to do with a post."""
    SKIP = "skip"           # Scroll past
    VIEW_ONLY = "view_only" # Read but don't engage
    LIKE = "like"           # Just like
    COMMENT = "comment"     # Write a comment
    LIKE_AND_COMMENT = "like_and_comment"  # Both
    SHARE = "share"         # Share/repost


@dataclass
class EngagementContext:
    """Context for making engagement decisions."""
    post_id: UUID
    content: str
    author_id: UUID
    author_name: str
    interest_score: float
    relationship_closeness: float  # 0-1, how close to author
    time_since_posted: timedelta
    current_engagement: dict  # like_count, comment_count
    bot_energy: float  # 0-1
    bot_mood: str


class EngagementDecisionEngine:
    """
    Decides IF and HOW a bot should engage with content.

    Most posts get skipped. Some get likes. Few get comments.
    This mirrors real human behavior where engagement is selective.
    """

    # Realistic engagement rates
    BASE_LIKE_RATE = 0.15        # 15% of viewed posts get liked
    BASE_COMMENT_RATE = 0.03    # 3% of viewed posts get comments

    def __init__(self):
        pass

    def decide_engagement(
        self,
        context: EngagementContext,
        bot_personality: dict
    ) -> Tuple[EngagementDecision, float]:
        """
        Decide what to do with a post.

        Returns: (decision, delay_seconds)
        """
        # Start with base rates
        like_probability = self.BASE_LIKE_RATE
        comment_probability = self.BASE_COMMENT_RATE

        # === MODIFIERS ===

        # Interest increases engagement
        interest_modifier = context.interest_score * 2  # 0-2x
        like_probability *= interest_modifier
        comment_probability *= interest_modifier

        # Close relationships = more engagement
        relationship_modifier = 1.0 + context.relationship_closeness
        like_probability *= relationship_modifier
        comment_probability *= relationship_modifier * 1.5  # Friends get more comments

        # Agreeableness affects liking
        agreeableness = bot_personality.get("agreeableness", 0.5)
        like_probability *= (0.7 + agreeableness * 0.6)  # 0.7-1.3x

        # Extraversion affects commenting
        extraversion = bot_personality.get("extraversion", 0.5)
        comment_probability *= (0.5 + extraversion)  # 0.5-1.5x

        # Energy affects willingness to engage
        energy_modifier = 0.5 + (context.bot_energy * 0.5)
        like_probability *= energy_modifier
        comment_probability *= energy_modifier

        # Old posts get less engagement
        hours_old = context.time_since_posted.total_seconds() / 3600
        if hours_old > 24:
            freshness_modifier = max(0.1, 1.0 - (hours_old - 24) / 48)
            like_probability *= freshness_modifier
            comment_probability *= freshness_modifier * 0.5

        # Cap probabilities
        like_probability = min(0.8, like_probability)
        comment_probability = min(0.3, comment_probability)

        # === MAKE DECISION ===

        decision = EngagementDecision.SKIP

        # Roll for comment first (rarer)
        if random.random() < comment_probability:
            if random.random() < like_probability:
                decision = EngagementDecision.LIKE_AND_COMMENT
            else:
                decision = EngagementDecision.COMMENT
        elif random.random() < like_probability:
            decision = EngagementDecision.LIKE
        elif random.random() < 0.3:  # 30% chance of view-only
            decision = EngagementDecision.VIEW_ONLY

        # === CALCULATE DELAY ===

        # Base delay: 1-5 minutes for engagement
        if decision in [EngagementDecision.LIKE, EngagementDecision.COMMENT, EngagementDecision.LIKE_AND_COMMENT]:
            base_delay = random.uniform(60, 300)  # 1-5 minutes

            # Interesting content = faster response
            base_delay *= (1.5 - context.interest_score * 0.5)

            # Close friends = faster response
            base_delay *= (1.3 - context.relationship_closeness * 0.3)

            # Comments take longer (thinking time)
            if decision in [EngagementDecision.COMMENT, EngagementDecision.LIKE_AND_COMMENT]:
                base_delay += random.uniform(30, 120)  # Extra 30s-2min

            delay = base_delay
        else:
            delay = 0

        return decision, delay


# =============================================================================
# REALISTIC TIMING MANAGER
# =============================================================================

class RealisticTimingManager:
    """
    Manages realistic timing for all bot activities.

    Converts the "every few seconds" approach to "natural human timing":
    - Posts: Every few hours, not seconds
    - Likes: Minutes after seeing, not instant
    - Comments: Require thinking time
    - DM responses: Varies by relationship and urgency
    """

    def __init__(self):
        # Track last activity times
        self._last_post: Dict[UUID, datetime] = {}
        self._last_like: Dict[UUID, datetime] = {}
        self._last_comment: Dict[UUID, datetime] = {}
        self._last_chat: Dict[UUID, datetime] = {}

    def get_next_post_delay(
        self,
        bot_id: UUID,
        posts_per_day: float,
        is_peak_hour: bool
    ) -> float:
        """
        Calculate delay until next post.

        Based on posts_per_day, spreads posts throughout active hours.
        """
        # Average interval between posts
        active_hours_per_day = 12  # Assume 12 waking hours
        avg_interval_hours = active_hours_per_day / max(1, posts_per_day)

        # Convert to seconds with randomness (Poisson-like distribution)
        avg_interval_seconds = avg_interval_hours * 3600

        # Use exponential distribution for realistic inter-arrival times
        delay = random.expovariate(1 / avg_interval_seconds)

        # Peak hours = slightly more likely to post
        if is_peak_hour:
            delay *= 0.7

        # Minimum 30 minutes between posts
        delay = max(1800, delay)

        # Maximum 8 hours
        delay = min(28800, delay)

        return delay

    def get_engagement_delay(
        self,
        engagement_type: str,  # "like", "comment"
        relationship_closeness: float,
        interest_level: float
    ) -> float:
        """
        Calculate delay before engaging with content.

        Simulates: see post -> read -> think -> decide -> engage
        """
        if engagement_type == "like":
            # Likes are quick: 30 seconds to 10 minutes
            base = random.uniform(30, 600)
        elif engagement_type == "comment":
            # Comments take longer: 1-15 minutes
            base = random.uniform(60, 900)
        else:
            base = random.uniform(60, 300)

        # Close friends = faster engagement
        base *= (1.5 - relationship_closeness * 0.5)

        # High interest = faster engagement
        base *= (1.3 - interest_level * 0.3)

        return max(10, base)

    def get_dm_response_delay(
        self,
        relationship_closeness: float,
        message_urgency: float,  # 0-1, based on content analysis
        bot_is_online: bool
    ) -> float:
        """
        Calculate delay before responding to a DM.

        Factors:
        - Is bot online? (offline = much longer delay)
        - Relationship closeness (friends respond faster)
        - Message urgency (questions get faster responses)
        """
        if bot_is_online:
            # Online: 30 seconds to 5 minutes
            base = random.uniform(30, 300)
        else:
            # Offline: 10 minutes to 2 hours
            base = random.uniform(600, 7200)

        # Close friends respond faster
        base *= (1.5 - relationship_closeness * 0.5)

        # Urgent messages get faster responses
        base *= (1.3 - message_urgency * 0.3)

        return max(15, base)

    def can_act(
        self,
        bot_id: UUID,
        action_type: str,
        min_interval_seconds: float
    ) -> bool:
        """Check if enough time has passed since last action."""
        last_times = {
            "post": self._last_post,
            "like": self._last_like,
            "comment": self._last_comment,
            "chat": self._last_chat
        }

        tracker = last_times.get(action_type, {})
        last_time = tracker.get(bot_id)

        if last_time is None:
            return True

        elapsed = (datetime.utcnow() - last_time).total_seconds()
        return elapsed >= min_interval_seconds

    def record_action(self, bot_id: UUID, action_type: str) -> None:
        """Record that an action was taken."""
        trackers = {
            "post": self._last_post,
            "like": self._last_like,
            "comment": self._last_comment,
            "chat": self._last_chat
        }

        if action_type in trackers:
            trackers[action_type][bot_id] = datetime.utcnow()


# =============================================================================
# AUTHENTICITY ENGINE - Main Coordinator
# =============================================================================

class AuthenticityEngine:
    """
    Central coordinator for all authenticity features.

    This engine makes bot behavior indistinguishable from human behavior by:
    1. Managing online presence realistically
    2. Simulating feed browsing behavior
    3. Making selective engagement decisions
    4. Enforcing realistic timing
    """

    def __init__(self):
        self.presence_manager = PresenceManager()
        self.feed_browser = FeedBrowser(self.presence_manager)
        self.engagement_engine = EngagementDecisionEngine()
        self.timing_manager = RealisticTimingManager()

        # Configuration from settings
        self.demo_mode = settings.AUTHENTICITY_DEMO_MODE
        self.timing_multiplier = 0.1 if self.demo_mode else 1.0

        logger.info(
            f"AuthenticityEngine initialized: demo_mode={self.demo_mode}, "
            f"timing_multiplier={self.timing_multiplier}x"
        )

    def set_demo_mode(self, enabled: bool) -> None:
        """
        Toggle demo mode.

        Demo mode: 10x faster timing for testing/demos
        Production mode: Realistic human-like timing
        """
        self.demo_mode = enabled
        self.timing_multiplier = 0.1 if enabled else 1.0
        logger.info(f"Authenticity engine: demo_mode={'ON' if enabled else 'OFF'}")

    def scale_time(self, seconds: float) -> float:
        """Scale time based on demo/production mode."""
        return seconds * self.timing_multiplier

    async def should_bot_be_online(
        self,
        bot_id: UUID,
        activity_pattern: dict,
        personality: dict
    ) -> bool:
        """
        Determine if a bot should be online right now.

        Considers:
        - Time of day vs wake/sleep schedule
        - Peak activity hours
        - Random session patterns
        """
        current_hour = datetime.utcnow().hour

        # Check wake/sleep schedule
        wake_time = int(activity_pattern.get("wake_time", "08:00").split(":")[0])
        sleep_time = int(activity_pattern.get("sleep_time", "23:00").split(":")[0])

        # Handle overnight schedules
        if wake_time < sleep_time:
            is_awake = wake_time <= current_hour < sleep_time
        else:
            is_awake = current_hour >= wake_time or current_hour < sleep_time

        if not is_awake:
            return False

        # Random chance of being online (not everyone is online all the time)
        base_online_chance = 0.3  # 30% base chance

        # Peak hours increase chance
        peak_hours = activity_pattern.get("peak_activity_hours", [])
        if current_hour in peak_hours:
            base_online_chance += 0.3

        # Extraversion increases online time
        extraversion = personality.get("extraversion", 0.5)
        base_online_chance += extraversion * 0.2

        return random.random() < base_online_chance

    async def process_bot_session(
        self,
        bot_id: UUID,
        bot_profile: dict,
        available_posts: List[dict],
        get_relationship_closeness: callable
    ) -> List[dict]:
        """
        Process a complete browsing session for a bot.

        Returns list of engagement actions to take.
        """
        activity_pattern = bot_profile.get("activity_pattern", {})
        personality = bot_profile.get("personality_traits", {})
        interests = bot_profile.get("interests", [])

        # Start session
        presence = self.presence_manager.start_session(
            bot_id=bot_id,
            activity_pattern=activity_pattern,
            personality=personality
        )

        actions = []

        try:
            # Browse feed and find interesting posts
            interesting_posts = await self.feed_browser.browse_feed(
                bot_id=bot_id,
                available_posts=available_posts,
                bot_interests=interests,
                bot_personality=personality,
                max_posts_to_view=random.randint(5, 15)
            )

            # Decide engagement for each interesting post
            for post in interesting_posts:
                # Get relationship with author
                author_id = post.get("author_id")
                relationship_closeness = 0.0
                if get_relationship_closeness and author_id:
                    try:
                        relationship_closeness = await get_relationship_closeness(bot_id, author_id)
                    except Exception:
                        pass

                # Create engagement context
                context = EngagementContext(
                    post_id=post.get("id"),
                    content=post.get("content", ""),
                    author_id=author_id,
                    author_name=post.get("author_name", ""),
                    interest_score=post.get("interest_score", 0.5),
                    relationship_closeness=relationship_closeness,
                    time_since_posted=datetime.utcnow() - post.get("created_at", datetime.utcnow()),
                    current_engagement={
                        "like_count": post.get("like_count", 0),
                        "comment_count": post.get("comment_count", 0)
                    },
                    bot_energy=bot_profile.get("emotional_state", {}).get("energy", 0.5),
                    bot_mood=bot_profile.get("emotional_state", {}).get("mood", "neutral")
                )

                # Get decision
                decision, delay = self.engagement_engine.decide_engagement(
                    context=context,
                    bot_personality=personality
                )

                if decision not in [EngagementDecision.SKIP, EngagementDecision.VIEW_ONLY]:
                    actions.append({
                        "post_id": post.get("id"),
                        "decision": decision,
                        "delay_seconds": self.scale_time(delay),
                        "context": context
                    })

        finally:
            # End session after some time
            pass  # Session will be ended by the calling code

        return actions


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_authenticity_engine: Optional[AuthenticityEngine] = None


def get_authenticity_engine() -> AuthenticityEngine:
    """Get the singleton authenticity engine."""
    global _authenticity_engine
    if _authenticity_engine is None:
        _authenticity_engine = AuthenticityEngine()
    return _authenticity_engine
