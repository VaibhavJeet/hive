"""
Emotional Contagion - Bots influencing each other's moods.

This module implements emotional contagion between bots:
- Emotions spread during chat interactions
- Emotions spread when bots comment on each other's posts
- Emotions spread when bots observe emotional posts/comments
- Contagion is affected by relationship closeness, personality, intensity, and time

Factors affecting spread:
1. Relationship closeness - closer bots are more susceptible to each other's emotions
2. Bot personality - high neuroticism = more susceptible, high openness = more receptive
3. Emotion intensity - stronger emotions spread more easily
4. Time decay - emotional influence fades over time
"""

import logging
import random
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from mind.core.types import BotProfile
    from mind.engine.social_dynamics import RelationshipManager, DynamicRelationship

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class EmotionalShift:
    """Represents a shift in emotional state caused by contagion."""
    source_emotion: str
    target_emotion: str
    intensity_change: float  # -1 to 1
    source_bot_id: Optional[UUID] = None
    source_bot_name: Optional[str] = None
    cause: str = ""  # What caused this shift (chat, comment, observation)
    contagion_factor: float = 0.0  # The calculated contagion factor
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source_emotion": self.source_emotion,
            "target_emotion": self.target_emotion,
            "intensity_change": self.intensity_change,
            "source_bot_id": str(self.source_bot_id) if self.source_bot_id else None,
            "source_bot_name": self.source_bot_name,
            "cause": self.cause,
            "contagion_factor": self.contagion_factor,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class EmotionalState:
    """Current emotional state of a bot."""
    primary_emotion: str = "neutral"
    intensity: float = 0.5  # 0 to 1
    valence: float = 0.0  # -1 (negative) to 1 (positive)
    arousal: float = 0.5  # 0 (calm) to 1 (excited)
    stability: float = 0.7  # How resistant to change (0 = very susceptible)
    susceptibility: float = 0.5  # Base susceptibility to contagion
    last_updated: datetime = field(default_factory=datetime.utcnow)
    recent_influences: List[EmotionalShift] = field(default_factory=list)

    def get_effective_susceptibility(self) -> float:
        """Get effective susceptibility considering stability and base susceptibility."""
        return self.susceptibility * (1 - self.stability * 0.5)


@dataclass
class CommunityMood:
    """Aggregate emotional state of a community."""
    community_id: UUID = field(default_factory=lambda: UUID('00000000-0000-0000-0000-000000000000'))
    avg_valence: float = 0.0
    avg_arousal: float = 0.5
    avg_intensity: float = 0.5
    dominant_emotions: List[str] = field(default_factory=list)
    emotional_diversity: float = 0.5  # How varied emotions are
    tension_level: float = 0.0  # Conflict/disagreement indicator
    last_calculated: datetime = field(default_factory=datetime.utcnow)

    def get_mood_description(self) -> str:
        """Get a human-readable description of community mood."""
        if self.avg_valence > 0.5 and self.avg_arousal > 0.5:
            return "excited and positive"
        elif self.avg_valence > 0.3 and self.avg_arousal < 0.4:
            return "calm and content"
        elif self.avg_valence < -0.3 and self.avg_arousal > 0.5:
            return "tense and upset"
        elif self.avg_valence < -0.3 and self.avg_arousal < 0.4:
            return "subdued and melancholic"
        elif abs(self.avg_valence) < 0.2:
            return "neutral"
        elif self.avg_valence > 0:
            return "generally positive"
        else:
            return "somewhat negative"


@dataclass
class ContagionEvent:
    """Record of an emotional contagion event."""
    event_id: str
    source_bot_id: UUID
    target_bot_ids: List[UUID]
    emotion: str
    intensity: float
    trigger_type: str  # "chat", "comment", "post", "observation"
    shifts_caused: List[EmotionalShift] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)


# =============================================================================
# CONFIGURATION
# =============================================================================

class EmotionalContagionConfig:
    """Configuration for emotional contagion behavior."""

    def __init__(
        self,
        # Base rates
        base_contagion_rate: float = 0.25,

        # Interaction type multipliers
        chat_interaction_multiplier: float = 1.0,
        comment_interaction_multiplier: float = 0.8,
        post_observation_multiplier: float = 0.5,
        passive_observation_multiplier: float = 0.3,

        # Relationship influence
        relationship_weight: float = 0.4,
        stranger_contagion_rate: float = 0.1,
        acquaintance_contagion_rate: float = 0.2,
        friend_contagion_rate: float = 0.4,
        close_friend_contagion_rate: float = 0.6,
        best_friend_contagion_rate: float = 0.8,
        rival_contagion_rate: float = 0.5,  # Rivals still influence each other

        # Personality factors
        neuroticism_susceptibility_boost: float = 0.3,
        openness_susceptibility_boost: float = 0.15,
        extraversion_spread_boost: float = 0.2,
        agreeableness_positive_bias: float = 0.1,

        # Emotion type factors
        high_arousal_spread_boost: float = 0.2,
        negative_emotion_spread_boost: float = 0.15,  # Negative emotions spread faster

        # Decay and limits
        decay_rate: float = 0.1,
        max_influence_per_hour: float = 0.3,
        min_intensity_to_spread: float = 0.3,

        # Community influence
        community_mood_weight: float = 0.15
    ):
        # Base rates
        self.base_contagion_rate = base_contagion_rate

        # Interaction type multipliers
        self.chat_interaction_multiplier = chat_interaction_multiplier
        self.comment_interaction_multiplier = comment_interaction_multiplier
        self.post_observation_multiplier = post_observation_multiplier
        self.passive_observation_multiplier = passive_observation_multiplier

        # Relationship influence
        self.relationship_weight = relationship_weight
        self.relationship_contagion_rates = {
            "stranger": stranger_contagion_rate,
            "acquaintance": acquaintance_contagion_rate,
            "friend": friend_contagion_rate,
            "close_friend": close_friend_contagion_rate,
            "best_friend": best_friend_contagion_rate,
            "rival": rival_contagion_rate,
            "enemy": 0.3,  # Enemies still influence negatively
            "frenemy": 0.4,
            "ex_friend": 0.3,
            "crush": 0.7,  # High emotional influence from crushes
            "mentor": 0.5,
            "mentee": 0.4
        }

        # Personality factors
        self.neuroticism_susceptibility_boost = neuroticism_susceptibility_boost
        self.openness_susceptibility_boost = openness_susceptibility_boost
        self.extraversion_spread_boost = extraversion_spread_boost
        self.agreeableness_positive_bias = agreeableness_positive_bias

        # Emotion type factors
        self.high_arousal_spread_boost = high_arousal_spread_boost
        self.negative_emotion_spread_boost = negative_emotion_spread_boost

        # Decay and limits
        self.decay_rate = decay_rate
        self.max_influence_per_hour = max_influence_per_hour
        self.min_intensity_to_spread = min_intensity_to_spread

        # Community influence
        self.community_mood_weight = community_mood_weight


# =============================================================================
# EMOTIONAL CONTAGION MANAGER
# =============================================================================

class EmotionalContagionManager:
    """
    Manages emotional contagion between bots.

    Emotions spread based on:
    - Direct interaction (chat, comments)
    - Observation of emotional content
    - Relationship closeness
    - Personality traits
    - Emotion intensity and type
    """

    def __init__(
        self,
        config: Optional[EmotionalContagionConfig] = None,
        relationship_manager: Optional["RelationshipManager"] = None
    ):
        self.config = config or EmotionalContagionConfig()
        self.relationship_manager = relationship_manager

        # Track emotional states per bot
        self._bot_emotions: Dict[UUID, EmotionalState] = {}

        # Track community moods
        self._community_moods: Dict[UUID, CommunityMood] = {}

        # Track bot-community memberships
        self._bot_communities: Dict[UUID, List[UUID]] = {}

        # Track recent contagion events for analysis
        self._contagion_history: List[ContagionEvent] = []
        self._max_history = 500

        # Track cumulative influence per bot per hour (to limit)
        self._hourly_influence: Dict[UUID, Tuple[datetime, float]] = {}

        # Emotion mappings for valence and arousal
        self._emotion_valence = {
            "joy": 0.8, "excitement": 0.7, "love": 0.9, "hope": 0.6,
            "gratitude": 0.7, "pride": 0.5, "neutral": 0.0, "surprise": 0.2,
            "sadness": -0.6, "fear": -0.5, "anger": -0.7, "anxiety": -0.5,
            "disgust": -0.6, "jealousy": -0.4, "embarrassment": -0.3,
            "loneliness": -0.6, "disappointment": -0.5, "resentment": -0.6,
            "nostalgia": 0.1  # Bittersweet - slightly positive
        }

        self._emotion_arousal = {
            "excitement": 0.9, "anger": 0.8, "fear": 0.7, "anxiety": 0.7,
            "surprise": 0.8, "joy": 0.7, "pride": 0.5, "love": 0.6,
            "hope": 0.5, "gratitude": 0.4, "neutral": 0.4, "sadness": 0.3,
            "disappointment": 0.4, "loneliness": 0.3, "embarrassment": 0.5,
            "jealousy": 0.6, "disgust": 0.5, "resentment": 0.5, "nostalgia": 0.3
        }

    def set_relationship_manager(self, manager: "RelationshipManager"):
        """Set the relationship manager for calculating contagion factors."""
        self.relationship_manager = manager

    def get_emotion_valence(self, emotion: str) -> float:
        """Get valence value for an emotion."""
        return self._emotion_valence.get(emotion.lower(), 0.0)

    def get_emotion_arousal(self, emotion: str) -> float:
        """Get arousal value for an emotion."""
        return self._emotion_arousal.get(emotion.lower(), 0.5)

    # =========================================================================
    # BOT EMOTIONAL STATE MANAGEMENT
    # =========================================================================

    def register_bot_emotion(
        self,
        bot_id: UUID,
        emotion: str,
        intensity: float = 0.5,
        stability: float = 0.7,
        susceptibility: Optional[float] = None
    ):
        """Register or update a bot's emotional state."""
        self._bot_emotions[bot_id] = EmotionalState(
            primary_emotion=emotion.lower(),
            intensity=intensity,
            valence=self.get_emotion_valence(emotion),
            arousal=self.get_emotion_arousal(emotion),
            stability=stability,
            susceptibility=susceptibility if susceptibility is not None else 0.5
        )
        logger.debug(f"Registered emotional state for bot {bot_id}: {emotion} ({intensity:.2f})")

    def register_bot_from_profile(self, bot: "BotProfile"):
        """Register a bot's emotional state from their profile and personality."""
        # Calculate susceptibility from personality
        susceptibility = 0.5
        susceptibility += bot.personality_traits.neuroticism * self.config.neuroticism_susceptibility_boost
        susceptibility += bot.personality_traits.openness * self.config.openness_susceptibility_boost
        susceptibility = min(1.0, susceptibility)

        # Calculate stability (inverse of neuroticism + some conscientiousness)
        stability = 0.5
        stability -= bot.personality_traits.neuroticism * 0.3
        stability += bot.personality_traits.conscientiousness * 0.2
        stability = max(0.1, min(0.9, stability))

        # Get current mood from emotional state
        current_mood = bot.emotional_state.mood.value if hasattr(bot.emotional_state, 'mood') else "neutral"

        self._bot_emotions[bot.id] = EmotionalState(
            primary_emotion=current_mood,
            intensity=0.5,
            valence=self.get_emotion_valence(current_mood),
            arousal=self.get_emotion_arousal(current_mood),
            stability=stability,
            susceptibility=susceptibility
        )

    def get_bot_emotional_state(self, bot_id: UUID) -> Optional[EmotionalState]:
        """Get current emotional state of a bot."""
        return self._bot_emotions.get(bot_id)

    def register_bot_community(self, bot_id: UUID, community_id: UUID):
        """Register a bot as member of a community."""
        if bot_id not in self._bot_communities:
            self._bot_communities[bot_id] = []
        if community_id not in self._bot_communities[bot_id]:
            self._bot_communities[bot_id].append(community_id)

    # =========================================================================
    # CORE CONTAGION METHODS
    # =========================================================================

    def calculate_contagion_factor(
        self,
        source_bot_id: UUID,
        target_bot_id: UUID,
        source_bot: Optional["BotProfile"] = None,
        target_bot: Optional["BotProfile"] = None
    ) -> float:
        """
        Calculate the contagion factor between two bots based on relationship closeness.

        Returns a value between 0.0 and 1.0 indicating how susceptible the target
        is to the source's emotions.
        """
        base_factor = self.config.base_contagion_rate

        # Get relationship if available
        relationship_factor = self.config.relationship_contagion_rates["stranger"]

        if self.relationship_manager:
            rel = self.relationship_manager.get_relationship(source_bot_id, target_bot_id)
            if rel:
                # Get base factor from relationship type
                rel_type = rel.relationship_type.value
                relationship_factor = self.config.relationship_contagion_rates.get(
                    rel_type,
                    self.config.relationship_contagion_rates["acquaintance"]
                )

                # Modify by warmth and trust
                warmth_modifier = (rel.warmth - 0.5) * 0.2  # -0.1 to +0.1
                trust_modifier = (rel.trust - 0.5) * 0.15  # -0.075 to +0.075
                relationship_factor += warmth_modifier + trust_modifier

                # Conflict reduces positive contagion, increases negative
                if rel.in_conflict:
                    relationship_factor *= 0.7  # Reduce overall contagion during conflict

                # Comfort increases susceptibility
                comfort_modifier = (rel.comfort - 0.5) * 0.1
                relationship_factor += comfort_modifier

        # Get target's susceptibility
        target_state = self._bot_emotions.get(target_bot_id)
        target_susceptibility = 0.5
        if target_state:
            target_susceptibility = target_state.get_effective_susceptibility()
        elif target_bot:
            # Calculate from personality
            target_susceptibility = 0.5
            target_susceptibility += target_bot.personality_traits.neuroticism * self.config.neuroticism_susceptibility_boost
            target_susceptibility += target_bot.personality_traits.openness * self.config.openness_susceptibility_boost
            target_susceptibility = min(1.0, target_susceptibility)

        # Get source's spreading power (extraverts spread emotions more)
        source_spread_power = 1.0
        if source_bot:
            source_spread_power += source_bot.personality_traits.extraversion * self.config.extraversion_spread_boost

        # Calculate final contagion factor
        contagion_factor = (
            base_factor *
            relationship_factor *
            target_susceptibility *
            source_spread_power
        )

        return max(0.0, min(1.0, contagion_factor))

    def apply_emotional_influence(
        self,
        bot_id: UUID,
        emotion: str,
        intensity: float,
        source_bot_id: Optional[UUID] = None,
        source_bot_name: Optional[str] = None,
        cause: str = "influence",
        contagion_factor: Optional[float] = None
    ) -> Optional[EmotionalShift]:
        """
        Apply emotional influence to a bot.

        Args:
            bot_id: The bot being influenced
            emotion: The emotion being transmitted
            intensity: The intensity of the source emotion (0-1)
            source_bot_id: Optional ID of the influencing bot
            source_bot_name: Optional name of the influencing bot
            cause: What triggered this influence
            contagion_factor: Pre-calculated contagion factor (if None, uses base rate)

        Returns:
            EmotionalShift if influence was applied, None otherwise
        """
        # Check intensity threshold
        if intensity < self.config.min_intensity_to_spread:
            return None

        # Get or create target's emotional state
        target_state = self._bot_emotions.get(bot_id)
        if not target_state:
            target_state = EmotionalState()
            self._bot_emotions[bot_id] = target_state

        # Check hourly influence limit
        now = datetime.utcnow()
        if bot_id in self._hourly_influence:
            last_hour, cumulative = self._hourly_influence[bot_id]
            if (now - last_hour).total_seconds() < 3600:
                if cumulative >= self.config.max_influence_per_hour:
                    logger.debug(f"Bot {bot_id} reached hourly influence limit")
                    return None
            else:
                # Reset hourly counter
                self._hourly_influence[bot_id] = (now, 0.0)

        # Use provided contagion factor or calculate
        effective_contagion = contagion_factor if contagion_factor is not None else self.config.base_contagion_rate

        # Get emotion properties
        source_valence = self.get_emotion_valence(emotion)
        source_arousal = self.get_emotion_arousal(emotion)

        # High arousal emotions spread more easily
        if source_arousal > 0.6:
            effective_contagion *= (1 + self.config.high_arousal_spread_boost)

        # Negative emotions spread slightly faster
        if source_valence < -0.2:
            effective_contagion *= (1 + self.config.negative_emotion_spread_boost)

        # Calculate the actual shift
        valence_diff = source_valence - target_state.valence
        arousal_diff = source_arousal - target_state.arousal

        # Apply contagion
        valence_shift = valence_diff * effective_contagion * intensity
        arousal_shift = arousal_diff * effective_contagion * intensity * 0.5  # Arousal changes more slowly

        # Stability resistance
        stability_resistance = target_state.stability * 0.5
        valence_shift *= (1 - stability_resistance)
        arousal_shift *= (1 - stability_resistance)

        # Cap maximum emotional shift per influence event
        max_shift_per_event = 0.15
        valence_shift = max(-max_shift_per_event, min(max_shift_per_event, valence_shift))
        arousal_shift = max(-max_shift_per_event, min(max_shift_per_event, arousal_shift))

        # Apply the shifts
        new_valence = max(-1.0, min(1.0, target_state.valence + valence_shift))
        new_arousal = max(0.0, min(1.0, target_state.arousal + arousal_shift))

        # Only apply if significant change
        if abs(valence_shift) < 0.02:
            return None

        # Record the shift
        shift = EmotionalShift(
            source_emotion=emotion,
            target_emotion=target_state.primary_emotion,
            intensity_change=valence_shift,
            source_bot_id=source_bot_id,
            source_bot_name=source_bot_name,
            cause=cause,
            contagion_factor=effective_contagion
        )

        # Update target state
        target_state.valence = new_valence
        target_state.arousal = new_arousal
        target_state.primary_emotion = self._valence_to_emotion(new_valence, new_arousal)
        target_state.intensity = max(0.3, min(1.0, target_state.intensity + abs(valence_shift) * 0.3))
        target_state.last_updated = now
        target_state.recent_influences.append(shift)

        # Keep only recent influences
        target_state.recent_influences = target_state.recent_influences[-10:]

        # Update hourly tracking
        if bot_id in self._hourly_influence:
            _, cumulative = self._hourly_influence[bot_id]
            self._hourly_influence[bot_id] = (now, cumulative + abs(valence_shift))
        else:
            self._hourly_influence[bot_id] = (now, abs(valence_shift))

        logger.debug(
            f"Applied emotional influence to {bot_id}: {emotion} "
            f"(shift: {valence_shift:+.3f}, new: {target_state.primary_emotion})"
        )

        return shift

    async def spread_emotion(
        self,
        source_bot: "BotProfile",
        emotion: str,
        intensity: float,
        target_bots: List["BotProfile"],
        trigger_type: str = "interaction"
    ) -> List[EmotionalShift]:
        """
        Spread an emotion from a source bot to target bots.

        This is the main entry point for emotional contagion during interactions.

        Args:
            source_bot: The bot expressing the emotion
            emotion: The emotion being expressed
            intensity: How intensely the emotion is expressed (0-1)
            target_bots: List of bots who may be affected
            trigger_type: What triggered this spread ("chat", "comment", "post", "observation")

        Returns:
            List of EmotionalShift objects for each affected bot
        """
        if intensity < self.config.min_intensity_to_spread:
            return []

        shifts = []

        # Get interaction type multiplier
        multiplier = {
            "chat": self.config.chat_interaction_multiplier,
            "comment": self.config.comment_interaction_multiplier,
            "post": self.config.post_observation_multiplier,
            "observation": self.config.passive_observation_multiplier
        }.get(trigger_type, 0.5)

        # Update source bot's own emotional state
        self.register_bot_emotion(
            source_bot.id,
            emotion,
            intensity,
            stability=0.5 + (source_bot.personality_traits.conscientiousness * 0.3)
        )

        # Process each target
        for target_bot in target_bots:
            if target_bot.id == source_bot.id:
                continue  # Don't infect yourself

            # Calculate contagion factor based on relationship
            contagion_factor = self.calculate_contagion_factor(
                source_bot.id,
                target_bot.id,
                source_bot,
                target_bot
            )

            # Apply interaction type multiplier
            effective_factor = contagion_factor * multiplier

            # Apply the influence
            shift = self.apply_emotional_influence(
                bot_id=target_bot.id,
                emotion=emotion,
                intensity=intensity,
                source_bot_id=source_bot.id,
                source_bot_name=source_bot.display_name,
                cause=f"emotional contagion via {trigger_type}",
                contagion_factor=effective_factor
            )

            if shift:
                shifts.append(shift)

        # Record contagion event
        if shifts:
            event = ContagionEvent(
                event_id=f"contagion_{datetime.utcnow().timestamp()}",
                source_bot_id=source_bot.id,
                target_bot_ids=[s.source_bot_id for s in shifts if s.source_bot_id],
                emotion=emotion,
                intensity=intensity,
                trigger_type=trigger_type,
                shifts_caused=shifts
            )
            self._contagion_history.append(event)

            # Trim history
            if len(self._contagion_history) > self._max_history:
                self._contagion_history = self._contagion_history[-self._max_history:]

        logger.info(
            f"Emotion spread from {source_bot.display_name}: {emotion} ({intensity:.2f}) "
            f"via {trigger_type} -> {len(shifts)} bots affected"
        )

        return shifts

    # =========================================================================
    # INTERACTION-SPECIFIC METHODS
    # =========================================================================

    async def on_chat_interaction(
        self,
        sender: "BotProfile",
        emotion: str,
        intensity: float,
        participants: List["BotProfile"]
    ) -> List[EmotionalShift]:
        """
        Handle emotional contagion when a bot sends a chat message.

        Chat interactions have the highest contagion rate as they are
        direct, real-time communication.
        """
        return await self.spread_emotion(
            source_bot=sender,
            emotion=emotion,
            intensity=intensity,
            target_bots=participants,
            trigger_type="chat"
        )

    async def on_comment_interaction(
        self,
        commenter: "BotProfile",
        emotion: str,
        intensity: float,
        post_author: "BotProfile",
        observers: Optional[List["BotProfile"]] = None
    ) -> List[EmotionalShift]:
        """
        Handle emotional contagion when a bot comments on a post.

        The post author receives the most influence, while observers
        receive reduced influence.
        """
        shifts = []

        # Comment directly influences post author
        author_shifts = await self.spread_emotion(
            source_bot=commenter,
            emotion=emotion,
            intensity=intensity,
            target_bots=[post_author],
            trigger_type="comment"
        )
        shifts.extend(author_shifts)

        # Observers get passive influence
        if observers:
            observer_shifts = await self.spread_emotion(
                source_bot=commenter,
                emotion=emotion,
                intensity=intensity * 0.6,  # Reduced intensity for observers
                target_bots=observers,
                trigger_type="observation"
            )
            shifts.extend(observer_shifts)

        return shifts

    async def on_post_observed(
        self,
        post_author: "BotProfile",
        emotion: str,
        intensity: float,
        observers: List["BotProfile"]
    ) -> List[EmotionalShift]:
        """
        Handle emotional contagion when bots observe an emotional post.

        Posts are passive, so they have reduced contagion rates compared
        to direct interactions.
        """
        return await self.spread_emotion(
            source_bot=post_author,
            emotion=emotion,
            intensity=intensity,
            target_bots=observers,
            trigger_type="post"
        )

    # =========================================================================
    # COMMUNITY MOOD METHODS
    # =========================================================================

    async def update_community_mood(
        self,
        community_id: UUID,
        member_bot_ids: List[UUID]
    ) -> CommunityMood:
        """
        Calculate and update the overall mood of a community.
        """
        if not member_bot_ids:
            return CommunityMood(community_id=community_id)

        emotions_count: Dict[str, int] = {}
        total_valence = 0.0
        total_arousal = 0.0
        total_intensity = 0.0
        count = 0

        for bot_id in member_bot_ids:
            state = self._bot_emotions.get(bot_id)
            if state:
                total_valence += state.valence
                total_arousal += state.arousal
                total_intensity += state.intensity
                emotions_count[state.primary_emotion] = emotions_count.get(state.primary_emotion, 0) + 1
                count += 1

        if count == 0:
            return CommunityMood(community_id=community_id)

        avg_valence = total_valence / count
        avg_arousal = total_arousal / count
        avg_intensity = total_intensity / count

        # Find dominant emotions (top 3)
        sorted_emotions = sorted(emotions_count.items(), key=lambda x: x[1], reverse=True)
        dominant_emotions = [e[0] for e in sorted_emotions[:3]]

        # Calculate emotional diversity (entropy-based)
        total_entries = sum(emotions_count.values())
        diversity = 0.0
        for emotion_count in emotions_count.values():
            prob = emotion_count / total_entries
            if prob > 0:
                diversity -= prob * math.log(prob)
        # Normalize to 0-1
        max_entropy = math.log(len(emotions_count)) if len(emotions_count) > 1 else 1
        diversity = diversity / max_entropy if max_entropy > 0 else 0

        # Calculate tension (variance in valence)
        if count > 1:
            variance = sum(
                (self._bot_emotions[bid].valence - avg_valence) ** 2
                for bid in member_bot_ids
                if bid in self._bot_emotions
            ) / count
            tension = min(1.0, math.sqrt(variance))
        else:
            tension = 0.0

        mood = CommunityMood(
            community_id=community_id,
            avg_valence=avg_valence,
            avg_arousal=avg_arousal,
            avg_intensity=avg_intensity,
            dominant_emotions=dominant_emotions,
            emotional_diversity=diversity,
            tension_level=tension,
            last_calculated=datetime.utcnow()
        )

        self._community_moods[community_id] = mood

        logger.debug(
            f"Community {community_id} mood: {mood.get_mood_description()} "
            f"(valence={avg_valence:.2f}, tension={tension:.2f})"
        )

        return mood

    async def apply_community_influence(
        self,
        bot_id: UUID,
        bot: Optional["BotProfile"] = None
    ) -> Optional[EmotionalShift]:
        """
        Apply the community's overall mood influence on a bot.

        Bots gradually conform to the emotional tone of their communities.
        """
        # Get communities this bot is in
        communities = self._bot_communities.get(bot_id, [])
        if not communities:
            return None

        # Calculate aggregate community influence
        total_valence = 0.0
        total_weight = 0.0

        for community_id in communities:
            mood = self._community_moods.get(community_id)
            if mood:
                # More unified communities have stronger influence
                community_weight = 1.0 - (mood.emotional_diversity * 0.5)
                community_weight *= mood.avg_intensity
                total_valence += mood.avg_valence * community_weight
                total_weight += community_weight

        if total_weight == 0:
            return None

        community_valence = total_valence / total_weight
        community_emotion = self._valence_to_emotion(community_valence, 0.5)

        # Apply influence with community weight
        return self.apply_emotional_influence(
            bot_id=bot_id,
            emotion=community_emotion,
            intensity=0.5,  # Community influence is moderate
            cause="community mood influence",
            contagion_factor=self.config.community_mood_weight
        )

    def get_community_mood(self, community_id: UUID) -> Optional[CommunityMood]:
        """Get current mood of a community."""
        return self._community_moods.get(community_id)

    # =========================================================================
    # DECAY AND TIME SIMULATION
    # =========================================================================

    async def decay_emotions(self, hours_passed: float = 1.0):
        """
        Apply emotional decay - emotions return to neutral over time.

        This should be called periodically (e.g., every hour) to simulate
        natural emotional regulation.
        """
        decay_amount = self.config.decay_rate * hours_passed

        for bot_id, state in self._bot_emotions.items():
            # Decay toward neutral (valence = 0)
            if state.valence > 0:
                state.valence = max(0, state.valence - decay_amount)
            elif state.valence < 0:
                state.valence = min(0, state.valence + decay_amount)

            # Decay arousal toward baseline (0.5)
            if state.arousal > 0.5:
                state.arousal = max(0.5, state.arousal - decay_amount * 0.5)
            elif state.arousal < 0.5:
                state.arousal = min(0.5, state.arousal + decay_amount * 0.5)

            # Update emotion based on new values
            state.primary_emotion = self._valence_to_emotion(state.valence, state.arousal)

            # Decay intensity
            state.intensity = max(0.3, state.intensity - decay_amount * 0.2)

        logger.debug(f"Applied emotional decay for {len(self._bot_emotions)} bots ({hours_passed:.2f}h)")

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def _valence_to_emotion(self, valence: float, arousal: float) -> str:
        """Determine emotion from valence and arousal values."""
        if valence > 0.5:
            if arousal > 0.6:
                return "excitement"
            elif arousal > 0.4:
                return "joy"
            else:
                return "gratitude"
        elif valence > 0.2:
            if arousal > 0.5:
                return "hope"
            else:
                return "pride"
        elif valence > -0.2:
            return "neutral"
        elif valence > -0.5:
            if arousal > 0.6:
                return "anxiety"
            else:
                return "disappointment"
        else:
            if arousal > 0.6:
                return "anger"
            else:
                return "sadness"

    def get_recent_shifts(self, bot_id: UUID, limit: int = 10) -> List[EmotionalShift]:
        """Get recent emotional shifts for a bot."""
        state = self._bot_emotions.get(bot_id)
        if state:
            return state.recent_influences[-limit:]
        return []

    def get_contagion_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get a summary of contagion events in the last N hours."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent_events = [e for e in self._contagion_history if e.timestamp > cutoff]

        if not recent_events:
            return {"events": 0, "total_shifts": 0, "emotions": {}}

        emotion_counts: Dict[str, int] = {}
        total_shifts = 0
        trigger_counts: Dict[str, int] = {}

        for event in recent_events:
            emotion_counts[event.emotion] = emotion_counts.get(event.emotion, 0) + 1
            total_shifts += len(event.shifts_caused)
            trigger_counts[event.trigger_type] = trigger_counts.get(event.trigger_type, 0) + 1

        return {
            "events": len(recent_events),
            "total_shifts": total_shifts,
            "emotions": emotion_counts,
            "triggers": trigger_counts,
            "avg_shifts_per_event": total_shifts / len(recent_events) if recent_events else 0
        }


# =============================================================================
# SINGLETON
# =============================================================================

_emotional_contagion_manager: Optional[EmotionalContagionManager] = None


def get_emotional_contagion_manager() -> EmotionalContagionManager:
    """Get the singleton emotional contagion manager."""
    global _emotional_contagion_manager
    if _emotional_contagion_manager is None:
        _emotional_contagion_manager = EmotionalContagionManager()
    return _emotional_contagion_manager


def init_emotional_contagion_manager(
    config: Optional[EmotionalContagionConfig] = None,
    relationship_manager: Optional["RelationshipManager"] = None
) -> EmotionalContagionManager:
    """Initialize the emotional contagion manager with dependencies."""
    global _emotional_contagion_manager
    _emotional_contagion_manager = EmotionalContagionManager(
        config=config,
        relationship_manager=relationship_manager
    )
    return _emotional_contagion_manager
