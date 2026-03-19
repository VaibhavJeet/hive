"""
Realistic Behaviors - Advanced human-like patterns for bot interactions.

This module adds the "final mile" of authenticity:
- Typing indicators with realistic duration
- Read receipts with gradual "seen" status
- Gradual engagement curves (posts get reactions over time)
- Social proof (bots follow what others engage with)
- Daily mood variations affecting all interactions
- Natural conversation callbacks (referencing past chats)
- Reaction variety (different emoji reactions)
"""

import asyncio
import random
import math
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Set
from uuid import UUID
from collections import defaultdict

logger = logging.getLogger(__name__)


# =============================================================================
# TYPING INDICATORS
# =============================================================================

@dataclass
class TypingState:
    """Tracks a bot's typing state."""
    is_typing: bool = False
    started_at: Optional[datetime] = None
    expected_duration_seconds: float = 0
    target_chat_id: Optional[UUID] = None  # Community or DM


class TypingIndicatorManager:
    """
    Manages realistic typing indicators.

    Typing duration is based on:
    - Message length (more words = longer typing)
    - Bot's typing speed trait
    - Random human variation
    """

    # Words per minute typing speeds (varies by person)
    SLOW_WPM = 25
    AVERAGE_WPM = 40
    FAST_WPM = 65

    def __init__(self):
        self._typing_states: Dict[UUID, TypingState] = {}
        self._typing_speeds: Dict[UUID, float] = {}  # bot_id -> WPM

    def assign_typing_speed(self, bot_id: UUID, personality: dict) -> float:
        """Assign a consistent typing speed to a bot based on personality."""
        if bot_id in self._typing_speeds:
            return self._typing_speeds[bot_id]

        # Base on neuroticism (anxious = faster) and age
        neuroticism = personality.get("neuroticism", 0.5)
        extraversion = personality.get("extraversion", 0.5)

        # Younger, more neurotic = faster typing
        base_wpm = self.AVERAGE_WPM
        base_wpm += (neuroticism - 0.5) * 20  # -10 to +10
        base_wpm += (extraversion - 0.5) * 10  # -5 to +5

        # Add random personal variation
        base_wpm *= random.uniform(0.8, 1.2)

        # Clamp to reasonable range
        wpm = max(self.SLOW_WPM, min(self.FAST_WPM, base_wpm))
        self._typing_speeds[bot_id] = wpm

        return wpm

    def calculate_typing_duration(
        self,
        bot_id: UUID,
        message: str,
        personality: dict
    ) -> float:
        """
        Calculate how long typing should be displayed.

        Returns duration in seconds.
        """
        wpm = self.assign_typing_speed(bot_id, personality)
        word_count = len(message.split())

        # Base typing time
        minutes = word_count / wpm
        seconds = minutes * 60

        # Add "thinking" time before typing starts
        thinking_time = random.uniform(0.5, 2.0)

        # Add occasional pauses (like correcting typos)
        pause_count = random.randint(0, min(3, word_count // 10))
        pause_time = pause_count * random.uniform(0.3, 1.0)

        # Human variation
        seconds *= random.uniform(0.8, 1.3)

        total = thinking_time + seconds + pause_time

        # Minimum 1 second, maximum 30 seconds
        return max(1.0, min(30.0, total))

    async def start_typing(
        self,
        bot_id: UUID,
        chat_id: UUID,
        message: str,
        personality: dict,
        broadcast_callback: Optional[callable] = None
    ) -> float:
        """
        Start typing indicator and return duration.

        If broadcast_callback is provided, will broadcast typing event.
        """
        duration = self.calculate_typing_duration(bot_id, message, personality)

        self._typing_states[bot_id] = TypingState(
            is_typing=True,
            started_at=datetime.utcnow(),
            expected_duration_seconds=duration,
            target_chat_id=chat_id
        )

        if broadcast_callback:
            await broadcast_callback("typing_start", {
                "bot_id": str(bot_id),
                "chat_id": str(chat_id),
                "duration_hint": duration
            })

        return duration

    async def stop_typing(
        self,
        bot_id: UUID,
        broadcast_callback: Optional[callable] = None
    ):
        """Stop typing indicator."""
        state = self._typing_states.get(bot_id)

        if state and state.is_typing:
            state.is_typing = False

            if broadcast_callback:
                await broadcast_callback("typing_stop", {
                    "bot_id": str(bot_id),
                    "chat_id": str(state.target_chat_id)
                })

    def is_typing(self, bot_id: UUID) -> bool:
        """Check if a bot is currently typing."""
        state = self._typing_states.get(bot_id)
        return state.is_typing if state else False


# =============================================================================
# READ RECEIPTS
# =============================================================================

@dataclass
class ReadReceipt:
    """Tracks when a message was seen."""
    message_id: UUID
    reader_id: UUID
    seen_at: datetime


class ReadReceiptManager:
    """
    Manages "seen" status for messages.

    Key behaviors:
    - Not instant - bots "read" messages gradually
    - Some bots read faster than others
    - Online bots see messages faster
    """

    def __init__(self):
        # message_id -> list of reader_ids
        self._receipts: Dict[UUID, List[ReadReceipt]] = defaultdict(list)
        # bot_id -> last message they've seen
        self._last_seen: Dict[UUID, UUID] = {}

    def calculate_read_delay(
        self,
        is_online: bool,
        relationship_closeness: float,
        personality: dict
    ) -> float:
        """
        Calculate delay before marking message as "seen".

        Returns delay in seconds.
        """
        if is_online:
            # Online: 5 seconds to 2 minutes
            base = random.uniform(5, 120)
        else:
            # Offline: Will be processed when they come online
            base = random.uniform(300, 7200)  # 5 min to 2 hours

        # Close relationships = check messages faster
        base *= (1.5 - relationship_closeness * 0.5)

        # Conscientiousness affects how quickly they check messages
        conscientiousness = personality.get("conscientiousness", 0.5)
        base *= (1.3 - conscientiousness * 0.3)

        return max(2.0, base)

    async def mark_as_read(
        self,
        message_id: UUID,
        reader_id: UUID,
        delay_seconds: float = 0,
        broadcast_callback: Optional[callable] = None
    ):
        """Mark a message as read after optional delay."""
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

        receipt = ReadReceipt(
            message_id=message_id,
            reader_id=reader_id,
            seen_at=datetime.utcnow()
        )

        self._receipts[message_id].append(receipt)
        self._last_seen[reader_id] = message_id

        if broadcast_callback:
            await broadcast_callback("message_read", {
                "message_id": str(message_id),
                "reader_id": str(reader_id),
                "seen_at": receipt.seen_at.isoformat()
            })

    def get_readers(self, message_id: UUID) -> List[UUID]:
        """Get list of bots who have seen a message."""
        return [r.reader_id for r in self._receipts.get(message_id, [])]

    def has_read(self, message_id: UUID, reader_id: UUID) -> bool:
        """Check if a specific bot has seen a message."""
        return reader_id in self.get_readers(message_id)


# =============================================================================
# GRADUAL ENGAGEMENT CURVES
# =============================================================================

@dataclass
class ScheduledEngagement:
    """A scheduled engagement action."""
    post_id: UUID
    bot_id: UUID
    action: str  # "like" or "comment"
    scheduled_at: datetime
    execute_at: datetime
    executed: bool = False
    community_id: Optional[UUID] = None
    author_id: Optional[UUID] = None
    content: Optional[str] = None


class EngagementWaveManager:
    """
    Manages gradual engagement on posts over time.

    Instead of: Post created -> All reactions happen at once
    Reality: Post created -> Gradual wave of engagement over hours

    This creates realistic engagement curves:
    - Initial spike (first 30 min): 30% of total engagement
    - Growth phase (30 min - 4 hours): 50% of total engagement
    - Long tail (4+ hours): 20% of total engagement
    """

    def __init__(self):
        # Track scheduled engagement waves
        self._engagement_waves: Dict[UUID, List[dict]] = defaultdict(list)
        # Scheduled engagements queue (sorted by execute_at time)
        self._scheduled_engagements: List[ScheduledEngagement] = []
        # Lock for thread-safe access
        self._lock = asyncio.Lock()

    def generate_engagement_schedule(
        self,
        post_id: UUID,
        author_popularity: float,  # 0-1
        content_quality: float,    # 0-1
        potential_engagers: List[UUID],
        demo_mode: bool = False
    ) -> List[dict]:
        """
        Generate a schedule of when different bots will engage.

        Returns list of {bot_id, action, delay_seconds}
        """
        schedule = []
        time_multiplier = 0.1 if demo_mode else 1.0

        # Calculate total engagement (not everyone engages)
        base_engagement_rate = 0.15  # 15% of viewers engage

        # Popularity and quality boost engagement
        engagement_rate = base_engagement_rate * (0.5 + author_popularity) * (0.5 + content_quality)
        engagement_rate = min(0.5, engagement_rate)  # Cap at 50%

        # Determine who will engage
        num_engagers = int(len(potential_engagers) * engagement_rate)
        selected_engagers = random.sample(
            potential_engagers,
            min(num_engagers, len(potential_engagers))
        )

        for i, bot_id in enumerate(selected_engagers):
            # Determine engagement type
            if random.random() < 0.85:
                action = "like"
            else:
                action = "comment"

            # Calculate delay using engagement curve
            delay = self._calculate_engagement_delay(
                position=i,
                total=len(selected_engagers),
                demo_mode=demo_mode
            )

            schedule.append({
                "bot_id": bot_id,
                "action": action,
                "delay_seconds": delay * time_multiplier
            })

        self._engagement_waves[post_id] = schedule
        return schedule

    async def schedule_post_engagements(
        self,
        post_id: UUID,
        author_id: UUID,
        author_popularity: float,
        content_quality: float,
        potential_engagers: List[UUID],
        community_id: Optional[UUID] = None,
        content: Optional[str] = None,
        demo_mode: bool = False
    ) -> int:
        """
        Schedule gradual engagements for a new post.

        This is the main entry point for integrating with post creation.
        Returns the number of engagements scheduled.
        """
        # Generate the engagement schedule
        schedule = self.generate_engagement_schedule(
            post_id=post_id,
            author_popularity=author_popularity,
            content_quality=content_quality,
            potential_engagers=potential_engagers,
            demo_mode=demo_mode
        )

        if not schedule:
            return 0

        now = datetime.utcnow()

        async with self._lock:
            for item in schedule:
                engagement = ScheduledEngagement(
                    post_id=post_id,
                    bot_id=item["bot_id"],
                    action=item["action"],
                    scheduled_at=now,
                    execute_at=now + timedelta(seconds=item["delay_seconds"]),
                    community_id=community_id,
                    author_id=author_id,
                    content=content
                )
                self._scheduled_engagements.append(engagement)

            # Sort by execution time
            self._scheduled_engagements.sort(key=lambda x: x.execute_at)

        logger.info(
            f"Scheduled {len(schedule)} gradual engagements for post {post_id} "
            f"(demo_mode={demo_mode})"
        )
        return len(schedule)

    async def get_due_engagements(self, limit: int = 10) -> List[ScheduledEngagement]:
        """
        Get engagements that are due to be executed.

        Returns up to `limit` engagements whose execute_at time has passed.
        """
        now = datetime.utcnow()
        due = []

        async with self._lock:
            for engagement in self._scheduled_engagements:
                if engagement.executed:
                    continue
                if engagement.execute_at <= now:
                    due.append(engagement)
                    if len(due) >= limit:
                        break
                else:
                    # List is sorted, so we can stop early
                    break

        return due

    async def mark_engagement_executed(self, engagement: ScheduledEngagement) -> None:
        """Mark an engagement as executed."""
        async with self._lock:
            engagement.executed = True

    async def mark_engagement_failed(self, engagement: ScheduledEngagement) -> None:
        """Mark an engagement as failed (will not retry)."""
        async with self._lock:
            engagement.executed = True  # Mark as done to prevent retry

    async def cleanup_old_engagements(self, max_age_hours: int = 48) -> int:
        """
        Remove old executed engagements to free memory.

        Returns the number of engagements cleaned up.
        """
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        removed = 0

        async with self._lock:
            original_count = len(self._scheduled_engagements)
            self._scheduled_engagements = [
                e for e in self._scheduled_engagements
                if not (e.executed and e.scheduled_at < cutoff)
            ]
            removed = original_count - len(self._scheduled_engagements)

        if removed > 0:
            logger.debug(f"Cleaned up {removed} old scheduled engagements")

        return removed

    def get_pending_count(self) -> int:
        """Get the number of pending (not executed) engagements."""
        return sum(1 for e in self._scheduled_engagements if not e.executed)

    def get_stats(self) -> dict:
        """Get statistics about scheduled engagements."""
        now = datetime.utcnow()
        total = len(self._scheduled_engagements)
        executed = sum(1 for e in self._scheduled_engagements if e.executed)
        pending = total - executed
        due = sum(
            1 for e in self._scheduled_engagements
            if not e.executed and e.execute_at <= now
        )

        return {
            "total_scheduled": total,
            "executed": executed,
            "pending": pending,
            "due_now": due,
            "posts_with_schedules": len(self._engagement_waves)
        }

    def _calculate_engagement_delay(
        self,
        position: int,
        total: int,
        demo_mode: bool
    ) -> float:
        """
        Calculate when this engagement should happen.

        Uses a realistic distribution:
        - Early engagements cluster in first 30 minutes
        - Middle engagements spread across hours
        - Late engagements trickle in
        """
        # Normalize position to 0-1
        normalized = position / max(1, total - 1) if total > 1 else 0

        if normalized < 0.3:
            # Initial spike: First 30% engage in 0-30 minutes
            minutes = random.uniform(0, 30) * (normalized / 0.3)
        elif normalized < 0.8:
            # Growth phase: Next 50% engage in 30 min - 4 hours
            normalized_in_phase = (normalized - 0.3) / 0.5
            minutes = 30 + (random.uniform(0, 210) * normalized_in_phase)
        else:
            # Long tail: Last 20% trickle in over 4-24 hours
            normalized_in_phase = (normalized - 0.8) / 0.2
            minutes = 240 + (random.uniform(0, 1200) * normalized_in_phase)

        # Add random jitter
        minutes *= random.uniform(0.7, 1.3)

        # Demo mode: Compress timeline
        if demo_mode:
            minutes *= 0.1

        return minutes * 60  # Convert to seconds


# =============================================================================
# SOCIAL PROOF ENGINE
# =============================================================================

class SocialProofEngine:
    """
    Bots are more likely to engage with content that others engaged with.

    This creates bandwagon effects and trending content, just like real
    social networks.
    """

    def __init__(self):
        # Track engagement counts for recent posts
        self._engagement_counts: Dict[UUID, dict] = {}
        self._engagement_timestamps: Dict[UUID, datetime] = {}

    def record_engagement(
        self,
        post_id: UUID,
        engagement_type: str  # "like", "comment", "share"
    ):
        """Record an engagement for social proof calculation."""
        if post_id not in self._engagement_counts:
            self._engagement_counts[post_id] = {"likes": 0, "comments": 0, "shares": 0}
            self._engagement_timestamps[post_id] = datetime.utcnow()

        if engagement_type == "like":
            self._engagement_counts[post_id]["likes"] += 1
        elif engagement_type == "comment":
            self._engagement_counts[post_id]["comments"] += 1
        elif engagement_type == "share":
            self._engagement_counts[post_id]["shares"] += 1

    def get_engagement_boost(
        self,
        post_id: UUID,
        viewer_personality: dict
    ) -> float:
        """
        Calculate engagement probability boost based on social proof.

        Returns a multiplier (1.0 = no boost, 2.0 = 2x more likely)
        """
        if post_id not in self._engagement_counts:
            return 1.0

        counts = self._engagement_counts[post_id]
        total = counts["likes"] + counts["comments"] * 3 + counts["shares"] * 5

        # More engagement = higher boost (logarithmic)
        base_boost = 1.0 + math.log1p(total) * 0.2

        # Conformity (agreeableness + neuroticism) affects susceptibility
        agreeableness = viewer_personality.get("agreeableness", 0.5)
        neuroticism = viewer_personality.get("neuroticism", 0.5)
        conformity = (agreeableness + neuroticism) / 2

        # High conformity = more affected by social proof
        personality_modifier = 0.7 + conformity * 0.6  # 0.7 to 1.3

        return base_boost * personality_modifier

    def cleanup_old_entries(self, max_age_hours: int = 48):
        """Remove old engagement tracking data."""
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)

        to_remove = [
            post_id for post_id, timestamp in self._engagement_timestamps.items()
            if timestamp < cutoff
        ]

        for post_id in to_remove:
            del self._engagement_counts[post_id]
            del self._engagement_timestamps[post_id]


# =============================================================================
# DAILY MOOD SYSTEM
# =============================================================================

class MoodType(str, Enum):
    """Daily mood states."""
    GREAT = "great"        # Extra social, positive
    GOOD = "good"          # Normal behavior
    MEH = "meh"            # Less active
    LOW = "low"            # Much less active, shorter responses
    BUSY = "busy"          # Quick responses, less engagement


@dataclass
class DailyMood:
    """A bot's mood for the day."""
    mood: MoodType
    energy_modifier: float  # 0.5 to 1.5
    sociability_modifier: float  # 0.5 to 1.5
    response_length_modifier: float  # 0.5 to 1.5
    set_at: datetime = field(default_factory=datetime.utcnow)


class DailyMoodManager:
    """
    Manages daily mood variations for bots.

    Each bot gets a "mood of the day" that affects:
    - How often they post/engage
    - How long their responses are
    - How social they are in chats
    """

    MOOD_DISTRIBUTIONS = {
        MoodType.GREAT: 0.15,   # 15% chance
        MoodType.GOOD: 0.45,    # 45% chance
        MoodType.MEH: 0.25,     # 25% chance
        MoodType.LOW: 0.10,     # 10% chance
        MoodType.BUSY: 0.05,    # 5% chance
    }

    MOOD_MODIFIERS = {
        MoodType.GREAT: {"energy": 1.4, "sociability": 1.5, "response_length": 1.3},
        MoodType.GOOD: {"energy": 1.0, "sociability": 1.0, "response_length": 1.0},
        MoodType.MEH: {"energy": 0.7, "sociability": 0.7, "response_length": 0.8},
        MoodType.LOW: {"energy": 0.5, "sociability": 0.5, "response_length": 0.6},
        MoodType.BUSY: {"energy": 0.6, "sociability": 0.4, "response_length": 0.5},
    }

    def __init__(self):
        self._daily_moods: Dict[UUID, DailyMood] = {}

    def get_or_assign_mood(
        self,
        bot_id: UUID,
        personality: dict
    ) -> DailyMood:
        """Get today's mood or assign a new one."""
        existing = self._daily_moods.get(bot_id)

        # Check if mood is from today
        if existing:
            hours_since = (datetime.utcnow() - existing.set_at).total_seconds() / 3600
            if hours_since < 20:  # Mood lasts ~20 hours
                return existing

        # Assign new mood
        return self._assign_mood(bot_id, personality)

    def _assign_mood(
        self,
        bot_id: UUID,
        personality: dict
    ) -> DailyMood:
        """Assign a new daily mood based on personality."""
        # Personality affects mood distribution
        neuroticism = personality.get("neuroticism", 0.5)
        extraversion = personality.get("extraversion", 0.5)

        # Adjust probabilities based on personality
        weights = dict(self.MOOD_DISTRIBUTIONS)

        # High neuroticism = more mood swings (more extreme moods)
        if neuroticism > 0.6:
            weights[MoodType.GREAT] *= 1.2
            weights[MoodType.LOW] *= 1.5
            weights[MoodType.GOOD] *= 0.7

        # High extraversion = generally better moods
        if extraversion > 0.6:
            weights[MoodType.GREAT] *= 1.3
            weights[MoodType.LOW] *= 0.6

        # Normalize weights
        total = sum(weights.values())
        weights = {k: v / total for k, v in weights.items()}

        # Select mood
        moods = list(weights.keys())
        probs = list(weights.values())
        selected_mood = random.choices(moods, weights=probs)[0]

        modifiers = self.MOOD_MODIFIERS[selected_mood]

        daily_mood = DailyMood(
            mood=selected_mood,
            energy_modifier=modifiers["energy"],
            sociability_modifier=modifiers["sociability"],
            response_length_modifier=modifiers["response_length"]
        )

        self._daily_moods[bot_id] = daily_mood
        logger.debug(f"Bot {bot_id} mood for today: {selected_mood.value}")

        return daily_mood


# =============================================================================
# CONVERSATION CALLBACK MEMORY
# =============================================================================

@dataclass
class ConversationMemory:
    """Memory of a past conversation."""
    other_person_id: UUID
    other_person_name: str
    topic: str
    timestamp: datetime
    sentiment: str  # "positive", "neutral", "negative"


class ConversationCallbackManager:
    """
    Tracks past conversations so bots can reference them naturally.

    "Hey! How did that interview go?" (referencing past chat)
    "Did you end up trying that recipe?"
    """

    MAX_MEMORIES_PER_BOT = 20

    def __init__(self):
        self._memories: Dict[UUID, List[ConversationMemory]] = defaultdict(list)

    def record_conversation(
        self,
        bot_id: UUID,
        other_person_id: UUID,
        other_person_name: str,
        topic: str,
        sentiment: str = "neutral"
    ):
        """Record a conversation topic for future callbacks."""
        memory = ConversationMemory(
            other_person_id=other_person_id,
            other_person_name=other_person_name,
            topic=topic,
            timestamp=datetime.utcnow(),
            sentiment=sentiment
        )

        memories = self._memories[bot_id]
        memories.append(memory)

        # Keep only recent memories
        if len(memories) > self.MAX_MEMORIES_PER_BOT:
            memories.pop(0)

    def get_callback_prompt(
        self,
        bot_id: UUID,
        other_person_id: UUID
    ) -> Optional[str]:
        """
        Get a conversation callback prompt if appropriate.

        Returns a prompt like "You recently talked with X about Y" or None.
        """
        memories = self._memories.get(bot_id, [])

        # Find relevant memories with this person
        relevant = [
            m for m in memories
            if m.other_person_id == other_person_id
            and (datetime.utcnow() - m.timestamp).days < 7  # Within a week
        ]

        if not relevant:
            return None

        # 30% chance to reference past conversation
        if random.random() > 0.3:
            return None

        memory = random.choice(relevant)
        days_ago = (datetime.utcnow() - memory.timestamp).days

        if days_ago == 0:
            time_ref = "earlier today"
        elif days_ago == 1:
            time_ref = "yesterday"
        else:
            time_ref = f"{days_ago} days ago"

        return (
            f"You talked with {memory.other_person_name} {time_ref} about: "
            f"{memory.topic}. Consider naturally referencing this."
        )


# =============================================================================
# REACTION VARIETY
# =============================================================================

class ReactionType(str, Enum):
    """Different reaction types beyond just "like"."""
    LIKE = "like"           # ❤️
    LOVE = "love"           # 😍
    HAHA = "haha"           # 😂
    WOW = "wow"             # 😮
    SAD = "sad"             # 😢
    ANGRY = "angry"         # 😠
    FIRE = "fire"           # 🔥
    CLAP = "clap"           # 👏
    THINK = "think"         # 🤔


class ReactionSelector:
    """
    Selects appropriate reactions based on content and personality.

    Not everyone just "likes" - people use different reactions
    based on content and their personality.
    """

    def select_reaction(
        self,
        content: str,
        personality: dict,
        relationship_closeness: float = 0.0
    ) -> ReactionType:
        """Select an appropriate reaction for the content."""
        content_lower = content.lower()

        # Content-based reaction hints
        if any(word in content_lower for word in ["funny", "lol", "haha", "😂", "joke"]):
            if random.random() < 0.6:
                return ReactionType.HAHA

        if any(word in content_lower for word in ["sad", "sorry", "lost", "miss", "😢"]):
            if random.random() < 0.4:
                return ReactionType.SAD

        if any(word in content_lower for word in ["wow", "amazing", "incredible", "😮"]):
            if random.random() < 0.5:
                return ReactionType.WOW

        if any(word in content_lower for word in ["congrat", "proud", "achieved", "success"]):
            if random.random() < 0.5:
                return ReactionType.CLAP

        if any(word in content_lower for word in ["hot", "fire", "🔥", "lit", "awesome"]):
            if random.random() < 0.4:
                return ReactionType.FIRE

        # Personality-based selection
        agreeableness = personality.get("agreeableness", 0.5)
        extraversion = personality.get("extraversion", 0.5)

        # Close relationships = more expressive reactions
        if relationship_closeness > 0.7:
            if random.random() < 0.3:
                return ReactionType.LOVE

        # Default to like with some variation
        if random.random() < 0.8:
            return ReactionType.LIKE

        # Occasional variety
        return random.choice([
            ReactionType.FIRE, ReactionType.CLAP,
            ReactionType.WOW, ReactionType.THINK
        ])


# =============================================================================
# SINGLETON MANAGER
# =============================================================================

class RealisticBehaviorManager:
    """
    Central manager for all realistic behavior systems.

    Provides a single interface to all authenticity features.
    """

    def __init__(self):
        self.typing = TypingIndicatorManager()
        self.read_receipts = ReadReceiptManager()
        self.engagement_waves = EngagementWaveManager()
        self.social_proof = SocialProofEngine()
        self.daily_mood = DailyMoodManager()
        self.conversation_callbacks = ConversationCallbackManager()
        self.reactions = ReactionSelector()

        logger.info("RealisticBehaviorManager initialized")

    def get_behavior_context(
        self,
        bot_id: UUID,
        personality: dict,
        other_person_id: Optional[UUID] = None
    ) -> dict:
        """
        Get combined behavior context for a bot's action.

        Returns modifiers and prompts that affect behavior.
        """
        # Get daily mood
        mood = self.daily_mood.get_or_assign_mood(bot_id, personality)

        # Get conversation callback if applicable
        callback_prompt = None
        if other_person_id:
            callback_prompt = self.conversation_callbacks.get_callback_prompt(
                bot_id, other_person_id
            )

        return {
            "mood": mood.mood.value,
            "energy_modifier": mood.energy_modifier,
            "sociability_modifier": mood.sociability_modifier,
            "response_length_modifier": mood.response_length_modifier,
            "conversation_callback": callback_prompt,
            "typing_speed": self.typing._typing_speeds.get(bot_id, 40)
        }


# Singleton instance
_realistic_behavior_manager: Optional[RealisticBehaviorManager] = None


def get_realistic_behavior_manager() -> RealisticBehaviorManager:
    """Get the singleton realistic behavior manager."""
    global _realistic_behavior_manager
    if _realistic_behavior_manager is None:
        _realistic_behavior_manager = RealisticBehaviorManager()
    return _realistic_behavior_manager
