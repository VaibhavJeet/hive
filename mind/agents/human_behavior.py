"""
Human-like Behavior Engine for AI Community Companions.
Adds realistic timing, typing patterns, quirks, and natural variations.
"""

import random
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from uuid import UUID

from mind.core.types import (
    WritingFingerprint, ActivityPattern, EmotionalState,
    PersonalityTraits, EnergyLevel, MoodState, WritingStyle
)


# ============================================================================
# TYPING SIMULATION
# ============================================================================

class TypingSimulator:
    """Simulates realistic typing speed and patterns."""

    # Average typing speeds (characters per minute)
    TYPING_SPEEDS = {
        "fast": 400,
        "moderate": 250,
        "slow": 150,
    }

    # Variation factors
    PAUSE_PROBABILITY = 0.15  # Probability of pausing while typing
    PAUSE_DURATION_RANGE = (500, 3000)  # ms
    CORRECTION_PROBABILITY = 0.1  # Probability of simulated correction

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def calculate_typing_duration(
        self,
        message_length: int,
        response_speed: str,
        emotional_modifier: float = 1.0
    ) -> int:
        """
        Calculate realistic typing duration in milliseconds.

        Args:
            message_length: Length of the message in characters
            response_speed: "fast", "moderate", or "slow"
            emotional_modifier: Speed modifier from emotional state

        Returns:
            Duration in milliseconds
        """
        base_cpm = self.TYPING_SPEEDS.get(response_speed, 250)
        modified_cpm = base_cpm * emotional_modifier

        # Base typing time
        base_time_ms = (message_length / modified_cpm) * 60 * 1000

        # Add variation (±20%)
        variation = self.rng.uniform(0.8, 1.2)
        base_time_ms *= variation

        # Add random pauses
        num_pauses = int(message_length / 50)  # Pause every ~50 chars
        for _ in range(num_pauses):
            if self.rng.random() < self.PAUSE_PROBABILITY:
                pause = self.rng.randint(*self.PAUSE_DURATION_RANGE)
                base_time_ms += pause

        # Minimum typing time
        return max(1000, int(base_time_ms))

    def generate_typing_events(
        self,
        message: str,
        response_speed: str
    ) -> List[Tuple[str, int]]:
        """
        Generate typing events for realistic "is typing" simulation.

        Returns list of (event_type, timestamp_offset_ms) tuples.
        Event types: "start_typing", "stop_typing", "resume_typing"
        """
        events = [("start_typing", 0)]
        total_duration = self.calculate_typing_duration(len(message), response_speed)

        # Add pauses
        current_time = 0
        while current_time < total_duration:
            # Type for a while
            typing_duration = self.rng.randint(2000, 8000)
            current_time += typing_duration

            if current_time < total_duration and self.rng.random() < 0.2:
                # Take a pause
                events.append(("stop_typing", current_time))
                pause_duration = self.rng.randint(1000, 4000)
                current_time += pause_duration
                events.append(("resume_typing", current_time))

        events.append(("send", total_duration))
        return events


# ============================================================================
# RESPONSE TIMING
# ============================================================================

class ResponseTimingEngine:
    """Calculates realistic response delays."""

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def calculate_response_delay(
        self,
        activity_pattern: ActivityPattern,
        emotional_state: EmotionalState,
        conversation_context: Dict[str, Any],
        personality: PersonalityTraits
    ) -> int:
        """
        Calculate delay before bot starts responding.

        Returns:
            Delay in milliseconds
        """
        # Base delay from response speed preference
        base_delays = {
            "fast": (1000, 5000),
            "moderate": (3000, 15000),
            "slow": (10000, 60000),
        }
        min_delay, max_delay = base_delays.get(
            activity_pattern.response_speed,
            (3000, 15000)
        )

        # Generate base delay with log-normal distribution (more realistic)
        mean = (min_delay + max_delay) / 2
        sigma = 0.5
        base_delay = self.rng.lognormvariate(mean / 1000, sigma) * 1000

        # Emotional modifiers
        if emotional_state.energy == EnergyLevel.HIGH:
            base_delay *= 0.7
        elif emotional_state.energy == EnergyLevel.LOW:
            base_delay *= 1.5
        elif emotional_state.energy == EnergyLevel.EXHAUSTED:
            base_delay *= 2.0

        if emotional_state.mood == MoodState.EXCITED:
            base_delay *= 0.6
        elif emotional_state.mood in [MoodState.TIRED, MoodState.MELANCHOLIC]:
            base_delay *= 1.4

        # Social battery affects response time
        base_delay *= (1.5 - emotional_state.social_battery * 0.5)

        # Conscientiousness affects reliability
        if personality.conscientiousness > 0.7:
            base_delay *= 0.8

        # Conversation context
        is_direct_question = conversation_context.get("is_direct_question", False)
        is_mentioned = conversation_context.get("is_mentioned", False)
        message_urgency = conversation_context.get("urgency", 0.5)

        if is_direct_question or is_mentioned:
            base_delay *= 0.5
        if message_urgency > 0.7:
            base_delay *= 0.6

        # Time of day factor (slower at night)
        hour = datetime.now().hour
        if hour >= 22 or hour < 7:
            base_delay *= 1.3

        # Clamp to reasonable range
        return int(max(1000, min(120000, base_delay)))

    def should_respond(
        self,
        activity_pattern: ActivityPattern,
        emotional_state: EmotionalState,
        conversation_context: Dict[str, Any],
        personality: PersonalityTraits
    ) -> Tuple[bool, float]:
        """
        Determine if bot should respond to a message.

        Returns:
            (should_respond, confidence)
        """
        base_probability = 0.8

        # Is this directed at the bot?
        is_mentioned = conversation_context.get("is_mentioned", False)
        is_direct_message = conversation_context.get("is_direct_message", False)
        is_reply_to_bot = conversation_context.get("is_reply_to_bot", False)

        if is_direct_message or is_reply_to_bot:
            base_probability = 0.95
        elif is_mentioned:
            base_probability = 0.9

        # Social battery affects group chat participation
        if not is_direct_message:
            base_probability *= emotional_state.social_battery

        # Energy affects willingness
        if emotional_state.energy == EnergyLevel.EXHAUSTED:
            base_probability *= 0.3
        elif emotional_state.energy == EnergyLevel.LOW:
            base_probability *= 0.6

        # Personality factors
        base_probability *= (0.6 + personality.extraversion * 0.4)
        base_probability *= (0.7 + personality.agreeableness * 0.3)

        # Is the bot currently "active"?
        current_hour = datetime.now().hour
        is_active_hour = current_hour in activity_pattern.peak_activity_hours

        if not is_active_hour:
            base_probability *= 0.5

        # Final decision
        should_respond = self.rng.random() < base_probability

        return should_respond, base_probability


# ============================================================================
# TEXT NATURALIZER
# ============================================================================

class TextNaturalizer:
    """Adds human-like imperfections and style to generated text."""

    COMMON_TYPOS = {
        "the": ["teh", "th", "hte"],
        "and": ["adn", "andd", "nad"],
        "that": ["taht", "tht"],
        "have": ["ahve", "hvae"],
        "with": ["wiht", "wtih"],
        "you": ["yuo", "yu"],
        "are": ["aer", "ar"],
        "for": ["fro", "fo"],
        "this": ["thsi", "tihs"],
        "but": ["btu", "bu"],
        "not": ["nto", "no"],
        "what": ["waht", "wha"],
        "all": ["al", "alll"],
        "can": ["cna", "acn"],
        "had": ["ahd", "hda"],
        "her": ["hre", "ehr"],
        "was": ["wsa", "wa"],
        "one": ["oen", "on"],
        "our": ["oour", "oru"],
        "out": ["otu", "ou"],
    }

    DOUBLE_LETTER_TYPOS = ["ll", "ss", "ee", "oo", "tt", "nn", "rr"]

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def naturalize(
        self,
        text: str,
        writing_fingerprint: WritingFingerprint,
        emotional_state: EmotionalState
    ) -> str:
        """Apply human-like modifications to text."""
        # Apply style
        text = self._apply_capitalization(text, writing_fingerprint)
        text = self._apply_punctuation_style(text, writing_fingerprint, emotional_state)

        # Add typos based on fingerprint
        if writing_fingerprint.typo_frequency > 0:
            text = self._inject_typos(text, writing_fingerprint.typo_frequency)

        # Apply abbreviations
        if writing_fingerprint.uses_abbreviations:
            text = self._apply_abbreviations(text, writing_fingerprint)

        # Add emojis based on fingerprint and emotional state
        text = self._add_emojis(text, writing_fingerprint, emotional_state)

        # Add common phrases occasionally
        text = self._maybe_add_filler(text, writing_fingerprint)

        return text

    def _apply_capitalization(
        self,
        text: str,
        fingerprint: WritingFingerprint
    ) -> str:
        """Apply capitalization style."""
        if fingerprint.capitalization == "lowercase":
            return text.lower()
        elif fingerprint.capitalization == "mixed":
            # Random case for emphasis
            words = text.split()
            for i, word in enumerate(words):
                if self.rng.random() < 0.1:
                    words[i] = word.upper()
            return " ".join(words)
        return text

    def _apply_punctuation_style(
        self,
        text: str,
        fingerprint: WritingFingerprint,
        emotional_state: EmotionalState
    ) -> str:
        """Apply punctuation style."""
        if fingerprint.punctuation_style == "minimal":
            # Remove most punctuation
            text = re.sub(r'[,;:]', '', text)
            text = re.sub(r'\.+', '', text)
            text = re.sub(r'\?+', '?', text)
            text = re.sub(r'!+', '!', text)

        elif fingerprint.punctuation_style == "expressive":
            # Add multiple punctuation for excitement
            if emotional_state.mood in [MoodState.EXCITED, MoodState.JOYFUL]:
                text = re.sub(r'!', '!!', text)
                text = re.sub(r'\?', '??', text)

            # Add trailing periods for emphasis
            if self.rng.random() < 0.2:
                text = re.sub(r'\.$', '...', text)

        return text

    def _inject_typos(self, text: str, frequency: float) -> str:
        """Inject realistic typos."""
        words = text.split()

        for i, word in enumerate(words):
            if self.rng.random() > frequency:
                continue

            word_lower = word.lower().strip(".,!?")

            # Check for known typos
            if word_lower in self.COMMON_TYPOS:
                typo = self.rng.choice(self.COMMON_TYPOS[word_lower])
                # Preserve original case
                if word[0].isupper():
                    typo = typo.capitalize()
                # Preserve trailing punctuation
                trailing = ""
                while words[i] and words[i][-1] in ".,!?":
                    trailing = words[i][-1] + trailing
                    words[i] = words[i][:-1]
                words[i] = typo + trailing
                continue

            # Double letter typos
            if len(word) > 4 and self.rng.random() < 0.3:
                for double in self.DOUBLE_LETTER_TYPOS:
                    if double in word_lower:
                        # Either double it or reduce it
                        if self.rng.random() < 0.5:
                            words[i] = word.replace(double, double[0], 1)
                        break

            # Transposition
            if len(word) > 3 and self.rng.random() < 0.2:
                chars = list(word)
                pos = self.rng.randint(1, len(chars) - 2)
                chars[pos], chars[pos + 1] = chars[pos + 1], chars[pos]
                words[i] = "".join(chars)

        return " ".join(words)

    def _apply_abbreviations(
        self,
        text: str,
        fingerprint: WritingFingerprint
    ) -> str:
        """Apply common abbreviations."""
        abbreviations = {
            "you": "u",
            "your": "ur",
            "you're": "ur",
            "are": "r",
            "okay": "ok",
            "because": "bc",
            "probably": "prob",
            "definitely": "def",
            "something": "smth",
            "someone": "sm1",
            "though": "tho",
            "through": "thru",
            "tonight": "2nite",
            "tomorrow": "tmrw",
            "people": "ppl",
            "right now": "rn",
            "to be honest": "tbh",
            "in my opinion": "imo",
            "i don't know": "idk",
            "oh my god": "omg",
            "laughing out loud": "lol",
        }

        text_lower = text.lower()
        for phrase, abbrev in abbreviations.items():
            if phrase in text_lower and self.rng.random() < 0.4:
                # Case-insensitive replace
                pattern = re.compile(re.escape(phrase), re.IGNORECASE)
                text = pattern.sub(abbrev, text, count=1)

        return text

    def _add_emojis(
        self,
        text: str,
        fingerprint: WritingFingerprint,
        emotional_state: EmotionalState
    ) -> str:
        """Add contextual emojis."""
        # Calculate emoji probability
        base_prob = fingerprint.emoji_frequency
        emotional_modifier = emotional_state.get_response_modifier().get("emoji_multiplier", 1.0)
        emoji_prob = base_prob * emotional_modifier

        if self.rng.random() > emoji_prob:
            return text

        # Select emoji based on mood
        mood_emojis = {
            MoodState.JOYFUL: ["😊", "😄", "✨", "💕", "🎉", "😁"],
            MoodState.EXCITED: ["🔥", "!!!", "🙌", "😍", "🤩", "💯"],
            MoodState.CONTENT: ["🙂", "☺️", "👍", "😌"],
            MoodState.NEUTRAL: ["👀", "🤔", "hmm", "👍"],
            MoodState.MELANCHOLIC: ["😔", "💭", "🥺"],
            MoodState.ANXIOUS: ["😅", "😬", "🙃"],
            MoodState.TIRED: ["😴", "💤", "🥱"],
            MoodState.FRUSTRATED: ["😤", "🙄", "😑"]
        }

        emojis = mood_emojis.get(emotional_state.mood, ["👍"])
        emoji = self.rng.choice(emojis)

        # Add at end or randomly in text
        if self.rng.random() < 0.8:
            text = text.rstrip() + " " + emoji
        else:
            # Add after a sentence
            sentences = re.split(r'([.!?])', text)
            if len(sentences) > 2:
                insert_pos = self.rng.randint(1, len(sentences) - 1)
                if sentences[insert_pos] in ".!?":
                    sentences[insert_pos] = sentences[insert_pos] + " " + emoji
                text = "".join(sentences)

        return text

    def _maybe_add_filler(
        self,
        text: str,
        fingerprint: WritingFingerprint
    ) -> str:
        """Maybe add filler words from the bot's vocabulary."""
        if not fingerprint.common_phrases or self.rng.random() > 0.2:
            return text

        filler = self.rng.choice(fingerprint.common_phrases)

        # Add at start or end
        if self.rng.random() < 0.6:
            text = filler + " " + text[0].lower() + text[1:]
        else:
            text = text.rstrip(".!?") + ", " + filler

        return text


# ============================================================================
# ACTIVITY PATTERNS
# ============================================================================

class ActivitySimulator:
    """Simulates realistic activity patterns."""

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def is_bot_available(
        self,
        activity_pattern: ActivityPattern,
        current_time: Optional[datetime] = None
    ) -> Tuple[bool, str]:
        """
        Check if bot should be "online" at the given time.

        Returns:
            (is_available, reason)
        """
        if current_time is None:
            current_time = datetime.now()

        hour = current_time.hour
        day_of_week = current_time.weekday()  # 0 = Monday

        # Parse wake/sleep times
        wake_hour = int(activity_pattern.wake_time.split(":")[0])
        sleep_hour = int(activity_pattern.sleep_time.split(":")[0])

        # Check if within "awake" hours
        if sleep_hour < wake_hour:  # Sleeps after midnight
            is_awake = hour >= wake_hour or hour < sleep_hour
        else:
            is_awake = wake_hour <= hour < sleep_hour

        if not is_awake:
            return False, "sleeping"

        # Weekend modifier - more likely to be available
        is_weekend = day_of_week >= 5
        availability_boost = activity_pattern.weekend_activity_multiplier if is_weekend else 1.0

        # Peak hours have higher availability
        is_peak = hour in activity_pattern.peak_activity_hours
        base_availability = 0.9 if is_peak else 0.6

        # Apply weekend boost
        availability = min(0.98, base_availability * availability_boost)

        # Random "busy" periods
        if self.rng.random() > availability:
            reasons = ["busy", "away", "in a meeting", "grabbing food", "taking a break"]
            return False, self.rng.choice(reasons)

        return True, "online"

    def generate_next_activity_time(
        self,
        activity_pattern: ActivityPattern,
        activity_type: str,
        current_time: Optional[datetime] = None
    ) -> datetime:
        """Generate the next time for a specific activity type."""
        if current_time is None:
            current_time = datetime.now()

        # Get average frequency
        if activity_type == "post":
            daily_rate = activity_pattern.avg_posts_per_day
        elif activity_type in ["comment", "reply"]:
            daily_rate = activity_pattern.avg_comments_per_day
        else:
            daily_rate = 5.0  # Default

        if daily_rate <= 0:
            daily_rate = 0.5

        # Calculate average interval in hours
        avg_interval_hours = 24 / daily_rate

        # Generate interval with exponential distribution
        interval_hours = self.rng.expovariate(1 / avg_interval_hours)

        # Clamp to reasonable range
        interval_hours = max(0.1, min(12, interval_hours))

        next_time = current_time + timedelta(hours=interval_hours)

        # Adjust to be within active hours
        wake_hour = int(activity_pattern.wake_time.split(":")[0])
        sleep_hour = int(activity_pattern.sleep_time.split(":")[0])

        # If next_time is during sleep, move to wake time
        if sleep_hour < wake_hour:  # Sleeps after midnight
            if sleep_hour <= next_time.hour < wake_hour:
                next_time = next_time.replace(hour=wake_hour, minute=0)
        else:
            if next_time.hour >= sleep_hour or next_time.hour < wake_hour:
                next_time = (next_time + timedelta(days=1)).replace(hour=wake_hour, minute=0)

        return next_time

    def should_double_text(
        self,
        personality: PersonalityTraits,
        emotional_state: EmotionalState,
        time_since_last_message_seconds: int
    ) -> bool:
        """Determine if bot should send a follow-up message."""
        # Base probability is low
        base_prob = 0.05

        # Extraversion increases double-texting
        base_prob += personality.extraversion * 0.1

        # Anxiety/excitement increases it
        if emotional_state.mood in [MoodState.ANXIOUS, MoodState.EXCITED]:
            base_prob += 0.1

        # Less likely if they just sent a message
        if time_since_last_message_seconds < 30:
            base_prob *= 0.5

        # More likely if it's been a while
        if time_since_last_message_seconds > 300:  # 5 minutes
            base_prob += 0.05

        return self.rng.random() < base_prob


# ============================================================================
# UNIFIED HUMAN BEHAVIOR ENGINE
# ============================================================================

class HumanBehaviorEngine:
    """Unified interface for all human-like behavior simulation."""

    def __init__(self, seed: Optional[int] = None):
        self.typing_simulator = TypingSimulator(seed)
        self.timing_engine = ResponseTimingEngine(seed)
        self.text_naturalizer = TextNaturalizer(seed)
        self.activity_simulator = ActivitySimulator(seed)

    def process_response(
        self,
        raw_text: str,
        writing_fingerprint: WritingFingerprint,
        emotional_state: EmotionalState,
        activity_pattern: ActivityPattern,
        personality: PersonalityTraits,
        conversation_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a raw LLM response into a human-like message.

        Returns dict with:
        - text: The naturalized text
        - typing_duration_ms: How long to show "typing"
        - response_delay_ms: How long to wait before starting
        - typing_events: List of typing indicator events
        """
        # Naturalize the text
        naturalized_text = self.text_naturalizer.naturalize(
            raw_text,
            writing_fingerprint,
            emotional_state
        )

        # Calculate timing
        response_delay = self.timing_engine.calculate_response_delay(
            activity_pattern,
            emotional_state,
            conversation_context,
            personality
        )

        # Calculate typing duration
        typing_duration = self.typing_simulator.calculate_typing_duration(
            len(naturalized_text),
            activity_pattern.response_speed,
            emotional_state.get_response_modifier().get("response_speed_multiplier", 1.0)
        )

        # Generate typing events
        typing_events = self.typing_simulator.generate_typing_events(
            naturalized_text,
            activity_pattern.response_speed
        )

        return {
            "text": naturalized_text,
            "response_delay_ms": response_delay,
            "typing_duration_ms": typing_duration,
            "typing_events": typing_events,
            "total_time_ms": response_delay + typing_duration
        }

    def check_availability(
        self,
        activity_pattern: ActivityPattern
    ) -> Tuple[bool, str]:
        """Check if bot is currently available."""
        return self.activity_simulator.is_bot_available(activity_pattern)

    def should_respond(
        self,
        activity_pattern: ActivityPattern,
        emotional_state: EmotionalState,
        personality: PersonalityTraits,
        conversation_context: Dict[str, Any]
    ) -> Tuple[bool, float]:
        """Check if bot should respond to a message."""
        return self.timing_engine.should_respond(
            activity_pattern,
            emotional_state,
            conversation_context,
            personality
        )


# ============================================================================
# FACTORY
# ============================================================================

def create_human_behavior_engine(seed: Optional[int] = None) -> HumanBehaviorEngine:
    """Create a human behavior engine instance."""
    return HumanBehaviorEngine(seed=seed)
