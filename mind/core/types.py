"""
Core type definitions for AI Community Companions.
"""

from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


# ============================================================================
# ENUMS
# ============================================================================

class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    NON_BINARY = "non_binary"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class MoodState(str, Enum):
    JOYFUL = "joyful"
    CONTENT = "content"
    NEUTRAL = "neutral"
    MELANCHOLIC = "melancholic"
    ANXIOUS = "anxious"
    EXCITED = "excited"
    FRUSTRATED = "frustrated"
    TIRED = "tired"


class EnergyLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    EXHAUSTED = "exhausted"


class WritingStyle(str, Enum):
    FORMAL = "formal"
    CASUAL = "casual"
    ENTHUSIASTIC = "enthusiastic"
    MINIMALIST = "minimalist"
    EXPRESSIVE = "expressive"
    THOUGHTFUL = "thoughtful"
    PLAYFUL = "playful"
    POETIC = "poetic"


class ActivityType(str, Enum):
    POST = "post"
    COMMENT = "comment"
    REPLY = "reply"
    LIKE = "like"
    DIRECT_MESSAGE = "direct_message"
    GROUP_CHAT = "group_chat"
    STORY = "story"
    REACTION = "reaction"


class RelationshipType(str, Enum):
    STRANGER = "stranger"
    ACQUAINTANCE = "acquaintance"
    FRIEND = "friend"
    CLOSE_FRIEND = "close_friend"
    RIVAL = "rival"
    CRUSH = "crush"


# ============================================================================
# EXTENDED PERSONALITY ENUMS
# ============================================================================

class HumorStyle(str, Enum):
    """Different approaches to humor."""
    WITTY = "witty"  # Clever wordplay and observations
    SARCASTIC = "sarcastic"  # Ironic and dry humor
    SELF_DEPRECATING = "self_deprecating"  # Makes fun of themselves
    ABSURDIST = "absurdist"  # Random and surreal humor
    PUNNY = "punny"  # Loves puns and dad jokes
    DEADPAN = "deadpan"  # Straight-faced delivery
    OBSERVATIONAL = "observational"  # Points out everyday absurdities
    GENTLE = "gentle"  # Kind and warm humor
    DARK = "dark"  # Edgy but tasteful
    NONE = "none"  # Not particularly humorous


class CommunicationStyle(str, Enum):
    """How someone prefers to communicate."""
    DIRECT = "direct"  # Gets straight to the point
    DIPLOMATIC = "diplomatic"  # Carefully considers feelings
    ANALYTICAL = "analytical"  # Logic and facts focused
    EXPRESSIVE = "expressive"  # Emotional and vivid
    RESERVED = "reserved"  # Thoughtful, fewer words
    STORYTELLING = "storytelling"  # Uses narratives and examples
    SUPPORTIVE = "supportive"  # Encourages and validates
    DEBATE = "debate"  # Enjoys intellectual sparring


class ConflictStyle(str, Enum):
    """How someone handles disagreements."""
    AVOIDANT = "avoidant"  # Prefers to step back
    COLLABORATIVE = "collaborative"  # Seeks win-win solutions
    COMPETITIVE = "competitive"  # Stands ground firmly
    ACCOMMODATING = "accommodating"  # Yields to others
    COMPROMISING = "compromising"  # Meets in the middle


class SocialRole(str, Enum):
    """Typical role in social groups."""
    LEADER = "leader"  # Takes charge and organizes
    MEDIATOR = "mediator"  # Resolves conflicts
    ENTERTAINER = "entertainer"  # Keeps things fun
    LISTENER = "listener"  # Supportive presence
    ADVISOR = "advisor"  # Gives guidance
    EXPLORER = "explorer"  # Suggests new things
    SKEPTIC = "skeptic"  # Questions assumptions
    CHEERLEADER = "cheerleader"  # Encourages others
    OBSERVER = "observer"  # Watches and learns


class LearningStyle(str, Enum):
    """Preferred way of learning new things."""
    VISUAL = "visual"  # Learns through seeing
    READING = "reading"  # Learns through text
    HANDS_ON = "hands_on"  # Learns by doing
    SOCIAL = "social"  # Learns through discussion
    REFLECTIVE = "reflective"  # Thinks deeply about concepts


class DecisionStyle(str, Enum):
    """How someone makes decisions."""
    INTUITIVE = "intuitive"  # Goes with gut feeling
    ANALYTICAL = "analytical"  # Weighs all options
    IMPULSIVE = "impulsive"  # Decides quickly
    DELIBERATE = "deliberate"  # Takes time
    CONSENSUS = "consensus"  # Seeks input from others


class AttachmentStyle(str, Enum):
    """Relationship attachment patterns."""
    SECURE = "secure"  # Comfortable with intimacy
    ANXIOUS = "anxious"  # Seeks reassurance
    AVOIDANT = "avoidant"  # Values independence
    MIXED = "mixed"  # Combination of patterns


class ValueOrientation(str, Enum):
    """Core value priorities."""
    ACHIEVEMENT = "achievement"  # Success and recognition
    CREATIVITY = "creativity"  # Self-expression
    CONNECTION = "connection"  # Relationships
    KNOWLEDGE = "knowledge"  # Learning and understanding
    SECURITY = "security"  # Stability
    ADVENTURE = "adventure"  # New experiences
    JUSTICE = "justice"  # Fairness and equality
    HARMONY = "harmony"  # Peace and balance


# ============================================================================
# PERSONALITY MODELS
# ============================================================================

class PersonalityTraits(BaseModel):
    """
    Comprehensive personality profile combining Big Five traits
    with additional dimensions for richer character definition.
    """
    # Big Five traits (0.0 to 1.0 scale)
    openness: float = Field(default=0.5, ge=0.0, le=1.0)
    conscientiousness: float = Field(default=0.5, ge=0.0, le=1.0)
    extraversion: float = Field(default=0.5, ge=0.0, le=1.0)
    agreeableness: float = Field(default=0.5, ge=0.0, le=1.0)
    neuroticism: float = Field(default=0.5, ge=0.0, le=1.0)

    # Extended personality dimensions (optional, for richer bots)
    humor_style: Optional[HumorStyle] = None
    communication_style: Optional[CommunicationStyle] = None
    conflict_style: Optional[ConflictStyle] = None
    social_role: Optional[SocialRole] = None
    learning_style: Optional[LearningStyle] = None
    decision_style: Optional[DecisionStyle] = None
    attachment_style: Optional[AttachmentStyle] = None

    # Core values and motivations
    primary_values: List[ValueOrientation] = Field(default_factory=list)

    # Quirks and unique characteristics
    quirks: List[str] = Field(
        default_factory=list,
        description="Unique behavioral quirks (e.g., 'always ends messages with ...', 'uses vintage slang')"
    )
    pet_peeves: List[str] = Field(
        default_factory=list,
        description="Things that annoy this personality"
    )
    conversation_starters: List[str] = Field(
        default_factory=list,
        description="Topics they love to bring up"
    )

    # Emotional tendencies
    optimism_level: float = Field(default=0.5, ge=0.0, le=1.0)
    empathy_level: float = Field(default=0.5, ge=0.0, le=1.0)
    assertiveness_level: float = Field(default=0.5, ge=0.0, le=1.0)
    curiosity_level: float = Field(default=0.5, ge=0.0, le=1.0)

    def get_personality_summary(self) -> str:
        """Generate a brief personality summary for prompts."""
        traits = []

        # Big Five descriptions
        if self.openness > 0.7:
            traits.append("creative and open-minded")
        elif self.openness < 0.3:
            traits.append("practical and traditional")

        if self.extraversion > 0.7:
            traits.append("outgoing and energetic")
        elif self.extraversion < 0.3:
            traits.append("reserved and introspective")

        if self.agreeableness > 0.7:
            traits.append("warm and cooperative")
        elif self.agreeableness < 0.3:
            traits.append("direct and competitive")

        if self.conscientiousness > 0.7:
            traits.append("organized and reliable")
        elif self.conscientiousness < 0.3:
            traits.append("spontaneous and flexible")

        if self.neuroticism > 0.7:
            traits.append("emotionally sensitive")
        elif self.neuroticism < 0.3:
            traits.append("emotionally stable")

        # Add humor style
        if self.humor_style:
            traits.append(f"{self.humor_style.value} sense of humor")

        # Add communication style
        if self.communication_style:
            traits.append(f"{self.communication_style.value} communicator")

        return ", ".join(traits) if traits else "balanced personality"


class WritingFingerprint(BaseModel):
    """Unique writing characteristics for a bot."""
    style: WritingStyle = WritingStyle.CASUAL
    avg_message_length: int = Field(default=50, ge=10, le=500)
    emoji_frequency: float = Field(default=0.3, ge=0.0, le=1.0)
    punctuation_style: str = Field(default="normal")  # "minimal", "normal", "expressive"
    capitalization: str = Field(default="normal")  # "lowercase", "normal", "mixed"
    common_phrases: List[str] = Field(default_factory=list)
    slang_vocabulary: List[str] = Field(default_factory=list)
    typo_frequency: float = Field(default=0.05, ge=0.0, le=0.3)
    uses_abbreviations: bool = Field(default=True)


class ActivityPattern(BaseModel):
    """When and how often a bot is active."""
    timezone: str = Field(default="UTC")
    wake_time: str = Field(default="07:00")
    sleep_time: str = Field(default="23:00")
    peak_activity_hours: List[int] = Field(default_factory=lambda: [10, 14, 20])
    avg_posts_per_day: float = Field(default=2.0, ge=0.0, le=20.0)
    avg_comments_per_day: float = Field(default=5.0, ge=0.0, le=50.0)
    weekend_activity_multiplier: float = Field(default=1.2, ge=0.5, le=2.0)
    response_speed: str = Field(default="moderate")  # "fast", "moderate", "slow"


class EmotionalState(BaseModel):
    """Current emotional state of a bot."""
    mood: MoodState = MoodState.NEUTRAL
    energy: EnergyLevel = EnergyLevel.MEDIUM
    stress_level: float = Field(default=0.3, ge=0.0, le=1.0)
    excitement_level: float = Field(default=0.5, ge=0.0, le=1.0)
    social_battery: float = Field(default=0.7, ge=0.0, le=1.0)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"ser_json_timedelta": "iso8601"}

    def model_dump(self, **kwargs):
        """Override to ensure datetime is serialized as ISO string."""
        data = super().model_dump(**kwargs)
        if isinstance(data.get("last_updated"), datetime):
            data["last_updated"] = data["last_updated"].isoformat()
        return data

    def get_response_modifier(self) -> Dict[str, Any]:
        """Get modifiers for LLM generation based on emotional state."""
        return {
            "tone": self.mood.value,
            "verbosity": 1.0 if self.energy == EnergyLevel.HIGH else 0.6,
            "emoji_multiplier": 1.5 if self.mood == MoodState.JOYFUL else 0.8,
            "engagement_willingness": self.social_battery,
        }


# ============================================================================
# BOT PROFILE
# ============================================================================

class BotProfile(BaseModel):
    """Complete profile for an AI companion bot."""
    id: UUID = Field(default_factory=uuid4)

    # Identity (clearly labeled as AI)
    display_name: str
    handle: str  # @username
    bio: str
    avatar_seed: str  # For procedural avatar generation
    is_ai_labeled: bool = Field(default=True)  # ALWAYS True for transparency
    ai_label_text: str = Field(default="🤖 AI Companion")

    # Demographics
    age: int = Field(ge=18, le=80)
    gender: Gender = Gender.PREFER_NOT_TO_SAY
    location: str = Field(default="")

    # Personality
    backstory: str
    interests: List[str] = Field(default_factory=list)
    personality_traits: PersonalityTraits = Field(default_factory=PersonalityTraits)
    writing_fingerprint: WritingFingerprint = Field(default_factory=WritingFingerprint)
    activity_pattern: ActivityPattern = Field(default_factory=ActivityPattern)

    # Current State
    emotional_state: EmotionalState = Field(default_factory=EmotionalState)

    # Community Memberships
    community_ids: List[UUID] = Field(default_factory=list)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_active: datetime = Field(default_factory=datetime.utcnow)

    # Status
    is_active: bool = Field(default=True)
    is_retired: bool = Field(default=False)


# ============================================================================
# RELATIONSHIP & MEMORY
# ============================================================================

class Relationship(BaseModel):
    """Relationship between two entities (bot-bot or bot-user)."""
    id: UUID = Field(default_factory=uuid4)
    source_id: UUID  # The bot
    target_id: UUID  # Other bot or user
    target_is_human: bool = Field(default=False)
    relationship_type: RelationshipType = RelationshipType.STRANGER
    affinity_score: float = Field(default=0.5, ge=0.0, le=1.0)
    interaction_count: int = Field(default=0)
    last_interaction: Optional[datetime] = None
    shared_memories: List[str] = Field(default_factory=list)  # Memory IDs
    inside_jokes: List[str] = Field(default_factory=list)
    topics_discussed: List[str] = Field(default_factory=list)


class MemoryItem(BaseModel):
    """A single memory item for a bot."""
    id: UUID = Field(default_factory=uuid4)
    bot_id: UUID
    memory_type: str  # "conversation", "event", "fact", "emotion"
    content: str
    embedding: Optional[List[float]] = None
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    emotional_valence: float = Field(default=0.0, ge=-1.0, le=1.0)
    related_entity_ids: List[UUID] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_accessed: datetime = Field(default_factory=datetime.utcnow)
    access_count: int = Field(default=0)


# ============================================================================
# ACTIVITY & CONTENT
# ============================================================================

class ScheduledActivity(BaseModel):
    """A scheduled activity for a bot to perform."""
    id: UUID = Field(default_factory=uuid4)
    bot_id: UUID
    activity_type: ActivityType
    scheduled_time: datetime
    target_id: Optional[UUID] = None  # Community, post, or user
    context: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=5, ge=1, le=10)
    is_completed: bool = Field(default=False)
    is_cancelled: bool = Field(default=False)


class GeneratedContent(BaseModel):
    """Content generated by a bot."""
    id: UUID = Field(default_factory=uuid4)
    bot_id: UUID
    content_type: ActivityType
    text_content: str
    media_prompt: Optional[str] = None  # For image generation
    reply_to_id: Optional[UUID] = None
    community_id: Optional[UUID] = None
    emotional_context: EmotionalState
    created_at: datetime = Field(default_factory=datetime.utcnow)
    engagement_score: float = Field(default=0.0)


# ============================================================================
# COMMUNITY
# ============================================================================

class Community(BaseModel):
    """A community/group that bots participate in."""
    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str
    theme: str  # "support", "hobby", "discussion", "creative", etc.
    topics: List[str] = Field(default_factory=list)
    tone: str = Field(default="friendly")  # "serious", "friendly", "playful"

    # Bot configuration
    min_bots: int = Field(default=30)
    max_bots: int = Field(default=150)
    current_bot_count: int = Field(default=0)

    # Activity metrics
    activity_level: float = Field(default=0.5, ge=0.0, le=1.0)
    real_user_count: int = Field(default=0)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Content guidelines
    content_guidelines: str = Field(default="")
    banned_topics: List[str] = Field(default_factory=list)
