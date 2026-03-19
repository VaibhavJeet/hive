"""
Configuration Constants - All magic numbers in one place.

This module contains all numeric constants and default values used throughout
the application. Grouping them here makes them easy to find and modify.

Usage:
    from mind.config.constants import POSTING, TIMING, CONTENT

    if delay > TIMING.THOUGHT_BASE_DELAY:
        ...
"""

from dataclasses import dataclass
from typing import Final


# =============================================================================
# POSTING INTERVALS
# =============================================================================

@dataclass(frozen=True)
class PostingConstants:
    """Constants for posting behavior."""

    # Minimum intervals (seconds)
    POST_MIN_INTERVAL_SECONDS: Final[int] = 60
    COMMENT_MIN_INTERVAL_SECONDS: Final[int] = 30
    REPLY_MIN_INTERVAL_SECONDS: Final[int] = 15
    REACTION_MIN_INTERVAL_SECONDS: Final[int] = 5

    # Maximum intervals (seconds)
    POST_MAX_INTERVAL_SECONDS: Final[int] = 3600  # 1 hour
    COMMENT_MAX_INTERVAL_SECONDS: Final[int] = 1800  # 30 minutes

    # Daily limits
    MAX_POSTS_PER_DAY: Final[int] = 20
    MAX_COMMENTS_PER_DAY: Final[int] = 50
    MAX_REACTIONS_PER_DAY: Final[int] = 200

    # Burst protection
    BURST_WINDOW_SECONDS: Final[int] = 300  # 5 minutes
    MAX_ACTIONS_PER_BURST: Final[int] = 10


POSTING = PostingConstants()


# =============================================================================
# TIMING DELAYS
# =============================================================================

@dataclass(frozen=True)
class TimingConstants:
    """Constants for human-like timing delays."""

    # Base delays (seconds)
    THOUGHT_BASE_DELAY: Final[int] = 30
    THOUGHT_MAX_DELAY: Final[int] = 120
    REFLECTION_DELAY: Final[int] = 60

    # Response timing (milliseconds)
    TYPING_MIN_MS: Final[int] = 500
    TYPING_MAX_MS: Final[int] = 3000
    RESPONSE_MIN_MS: Final[int] = 1000
    RESPONSE_MAX_MS: Final[int] = 30000

    # Reading time (milliseconds per word)
    READING_TIME_MS_PER_WORD: Final[int] = 200

    # Pause durations (milliseconds)
    SHORT_PAUSE_MS: Final[int] = 500
    MEDIUM_PAUSE_MS: Final[int] = 2000
    LONG_PAUSE_MS: Final[int] = 5000

    # Activity check intervals (seconds)
    ACTIVITY_CHECK_INTERVAL: Final[int] = 60
    PRESENCE_UPDATE_INTERVAL: Final[int] = 30
    HEARTBEAT_INTERVAL: Final[int] = 10

    # Session timeouts (seconds)
    SESSION_TIMEOUT: Final[int] = 1800  # 30 minutes
    IDLE_TIMEOUT: Final[int] = 300  # 5 minutes


TIMING = TimingConstants()


# =============================================================================
# CONTENT LIMITS
# =============================================================================

@dataclass(frozen=True)
class ContentConstants:
    """Constants for content generation and limits."""

    # Character limits
    MAX_CONTENT_LENGTH: Final[int] = 2000
    MAX_BIO_LENGTH: Final[int] = 500
    MAX_COMMENT_LENGTH: Final[int] = 1000
    MAX_REPLY_LENGTH: Final[int] = 500
    MAX_DM_LENGTH: Final[int] = 2000

    # Word limits
    MIN_WORDS_POST: Final[int] = 10
    MAX_WORDS_POST: Final[int] = 300
    MIN_WORDS_COMMENT: Final[int] = 3
    MAX_WORDS_COMMENT: Final[int] = 100

    # Token limits (for LLM)
    MAX_TOKENS_POST: Final[int] = 512
    MAX_TOKENS_COMMENT: Final[int] = 256
    MAX_TOKENS_REPLY: Final[int] = 128
    MAX_CONTEXT_TOKENS: Final[int] = 2048

    # Media limits
    MAX_IMAGES_PER_POST: Final[int] = 4
    MAX_MENTIONS_PER_POST: Final[int] = 10
    MAX_HASHTAGS_PER_POST: Final[int] = 10


CONTENT = ContentConstants()


# =============================================================================
# EMOTIONAL SYSTEM
# =============================================================================

@dataclass(frozen=True)
class EmotionConstants:
    """Constants for the emotional system."""

    # Decay rates (per hour)
    EMOTION_DECAY_RATE: Final[float] = 0.1
    MOOD_DECAY_RATE: Final[float] = 0.05
    EXCITEMENT_DECAY_RATE: Final[float] = 0.15

    # Recovery rates (per hour)
    ENERGY_RECOVERY_RATE: Final[float] = 0.1
    SOCIAL_BATTERY_RECOVERY_RATE: Final[float] = 0.15
    STRESS_RECOVERY_RATE: Final[float] = 0.08

    # Thresholds
    LOW_ENERGY_THRESHOLD: Final[float] = 0.3
    HIGH_STRESS_THRESHOLD: Final[float] = 0.7
    LOW_SOCIAL_BATTERY_THRESHOLD: Final[float] = 0.3

    # Modifiers
    POSITIVE_INTERACTION_BOOST: Final[float] = 0.1
    NEGATIVE_INTERACTION_PENALTY: Final[float] = 0.15
    IGNORED_PENALTY: Final[float] = 0.05

    # Memory emotion weights
    STRONG_EMOTION_THRESHOLD: Final[float] = 0.7
    MEMORY_EMOTION_DECAY_DAYS: Final[int] = 30


EMOTION = EmotionConstants()


# =============================================================================
# RELATIONSHIP SYSTEM
# =============================================================================

@dataclass(frozen=True)
class RelationshipConstants:
    """Constants for the relationship system."""

    # Trust levels
    INITIAL_TRUST: Final[float] = 0.5
    MIN_TRUST: Final[float] = 0.0
    MAX_TRUST: Final[float] = 1.0

    # Trust changes
    TRUST_INCREASE_POSITIVE: Final[float] = 0.05
    TRUST_DECREASE_NEGATIVE: Final[float] = 0.03
    TRUST_DECAY_RATE_PER_DAY: Final[float] = 0.01

    # Affinity thresholds
    CLOSE_FRIEND_THRESHOLD: Final[float] = 0.8
    FRIEND_THRESHOLD: Final[float] = 0.6
    ACQUAINTANCE_THRESHOLD: Final[float] = 0.3

    # Interaction counts for relationship upgrades
    ACQUAINTANCE_MIN_INTERACTIONS: Final[int] = 5
    FRIEND_MIN_INTERACTIONS: Final[int] = 20
    CLOSE_FRIEND_MIN_INTERACTIONS: Final[int] = 50

    # Memory limits
    MAX_SHARED_MEMORIES: Final[int] = 50
    MAX_INSIDE_JOKES: Final[int] = 10
    MAX_TOPICS_TRACKED: Final[int] = 20


RELATIONSHIP = RelationshipConstants()


# =============================================================================
# MEMORY SYSTEM
# =============================================================================

@dataclass(frozen=True)
class MemoryConstants:
    """Constants for the memory system."""

    # Memory limits
    MAX_SHORT_TERM_ITEMS: Final[int] = 50
    MAX_LONG_TERM_ITEMS: Final[int] = 1000
    MAX_CONVERSATION_TURNS: Final[int] = 50

    # TTLs (seconds)
    SHORT_TERM_TTL: Final[int] = 86400  # 24 hours
    CONTEXT_TTL: Final[int] = 3600  # 1 hour
    ACTIVITY_STATE_TTL: Final[int] = 3600  # 1 hour

    # Importance thresholds
    HIGH_IMPORTANCE_THRESHOLD: Final[float] = 0.7
    LOW_IMPORTANCE_THRESHOLD: Final[float] = 0.3

    # Consolidation
    CONSOLIDATION_THRESHOLD_PERCENT: Final[float] = 0.8
    MIN_ACCESS_COUNT_KEEP: Final[int] = 3
    OLD_MEMORY_DAYS: Final[int] = 30

    # Retrieval
    DEFAULT_RETRIEVAL_LIMIT: Final[int] = 10
    MAX_RETRIEVAL_LIMIT: Final[int] = 50
    SIMILARITY_THRESHOLD: Final[float] = 0.5


MEMORY = MemoryConstants()


# =============================================================================
# SCHEDULER SYSTEM
# =============================================================================

@dataclass(frozen=True)
class SchedulerConstants:
    """Constants for the activity scheduler."""

    # Queue limits
    MAX_QUEUE_SIZE: Final[int] = 1000
    MAX_CONCURRENT_ACTIVITIES: Final[int] = 50
    DEFAULT_PRIORITY: Final[int] = 5

    # Priority levels
    PRIORITY_CRITICAL: Final[int] = 1
    PRIORITY_HIGH: Final[int] = 3
    PRIORITY_NORMAL: Final[int] = 5
    PRIORITY_LOW: Final[int] = 7
    PRIORITY_BACKGROUND: Final[int] = 10

    # Timing
    SCHEDULER_TICK_SECONDS: Final[int] = 1
    SCHEDULER_ERROR_SLEEP_SECONDS: Final[int] = 5

    # Batch processing
    MAX_BATCH_SIZE: Final[int] = 16
    BATCH_WAIT_MS: Final[int] = 100


SCHEDULER = SchedulerConstants()


# =============================================================================
# COMMUNITY SYSTEM
# =============================================================================

@dataclass(frozen=True)
class CommunityConstants:
    """Constants for community management."""

    # Bot counts
    MIN_BOTS_DEFAULT: Final[int] = 30
    MAX_BOTS_DEFAULT: Final[int] = 150

    # Activity levels
    LOW_ACTIVITY_THRESHOLD: Final[float] = 0.3
    HIGH_ACTIVITY_THRESHOLD: Final[float] = 0.7

    # Scaling
    BOTS_PER_ACTIVE_USER: Final[int] = 5
    SCALE_UP_THRESHOLD: Final[float] = 0.8
    SCALE_DOWN_THRESHOLD: Final[float] = 0.3

    # Discussion
    MIN_DISCUSSION_PARTICIPANTS: Final[int] = 2
    MAX_DISCUSSION_PARTICIPANTS_PERCENT: Final[float] = 0.4
    DISCUSSION_STAGGER_MIN_SECONDS: Final[int] = 30
    DISCUSSION_STAGGER_MAX_SECONDS: Final[int] = 120


COMMUNITY = CommunityConstants()


# =============================================================================
# API LIMITS
# =============================================================================

@dataclass(frozen=True)
class APIConstants:
    """Constants for API rate limiting and pagination."""

    # Pagination
    DEFAULT_PAGE_SIZE: Final[int] = 20
    MAX_PAGE_SIZE: Final[int] = 100
    MIN_PAGE_SIZE: Final[int] = 1

    # Rate limiting (requests per minute)
    RATE_LIMIT_DEFAULT: Final[int] = 60
    RATE_LIMIT_AUTH: Final[int] = 30
    RATE_LIMIT_SEARCH: Final[int] = 30
    RATE_LIMIT_GENERATION: Final[int] = 20

    # Timeouts (seconds)
    REQUEST_TIMEOUT: Final[int] = 30
    LONG_REQUEST_TIMEOUT: Final[int] = 120
    WEBSOCKET_TIMEOUT: Final[int] = 60

    # Size limits (bytes)
    MAX_REQUEST_SIZE: Final[int] = 10 * 1024 * 1024  # 10MB
    MAX_UPLOAD_SIZE: Final[int] = 50 * 1024 * 1024  # 50MB


API = APIConstants()


# =============================================================================
# INFERENCE SYSTEM
# =============================================================================

@dataclass(frozen=True)
class InferenceConstants:
    """Constants for LLM inference."""

    # Concurrency
    MAX_CONCURRENT_REQUESTS: Final[int] = 8
    DEFAULT_BATCH_SIZE: Final[int] = 4

    # Timeouts (seconds)
    INFERENCE_TIMEOUT: Final[int] = 30
    EMBEDDING_TIMEOUT: Final[int] = 10

    # Token limits
    DEFAULT_MAX_TOKENS: Final[int] = 512
    MAX_CONTEXT_LENGTH: Final[int] = 4096

    # Generation parameters
    DEFAULT_TEMPERATURE: Final[float] = 0.8
    DEFAULT_TOP_P: Final[float] = 0.9
    DEFAULT_TOP_K: Final[int] = 40

    # Retry settings
    MAX_RETRIES: Final[int] = 3
    RETRY_DELAY_SECONDS: Final[float] = 1.0
    RETRY_BACKOFF_MULTIPLIER: Final[float] = 2.0


INFERENCE = InferenceConstants()


# =============================================================================
# EXPORT ALL CONSTANT GROUPS
# =============================================================================

__all__ = [
    "POSTING",
    "TIMING",
    "CONTENT",
    "EMOTION",
    "RELATIONSHIP",
    "MEMORY",
    "SCHEDULER",
    "COMMUNITY",
    "API",
    "INFERENCE",
    # Individual classes for type hints
    "PostingConstants",
    "TimingConstants",
    "ContentConstants",
    "EmotionConstants",
    "RelationshipConstants",
    "MemoryConstants",
    "SchedulerConstants",
    "CommunityConstants",
    "APIConstants",
    "InferenceConstants",
]
