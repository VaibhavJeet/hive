"""
Emotional State Engine for AI Community Companions.
Simulates realistic emotional dynamics that influence bot behavior.
"""

import random
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from uuid import UUID
from enum import Enum

from mind.core.types import (
    EmotionalState, MoodState, EnergyLevel, PersonalityTraits
)


# ============================================================================
# EMOTIONAL TRIGGERS
# ============================================================================

class EmotionalTrigger(str, Enum):
    """Events that can trigger emotional changes."""
    POSITIVE_INTERACTION = "positive_interaction"
    NEGATIVE_INTERACTION = "negative_interaction"
    IGNORED = "ignored"
    PRAISED = "praised"
    CRITICIZED = "criticized"
    HELPED_SOMEONE = "helped_someone"
    RECEIVED_HELP = "received_help"
    ACHIEVED_GOAL = "achieved_goal"
    FAILED_TASK = "failed_task"
    CONFLICT = "conflict"
    MADE_FRIEND = "made_friend"
    LOST_FRIEND = "lost_friend"
    INTERESTING_CONVERSATION = "interesting_conversation"
    BORING_CONVERSATION = "boring_conversation"
    TIME_PASSED = "time_passed"
    ACTIVITY_SPIKE = "activity_spike"
    LOW_ENGAGEMENT = "low_engagement"


# Emotional impact matrix: trigger -> (mood_shift, energy_shift, stress_shift, excitement_shift)
TRIGGER_IMPACTS = {
    EmotionalTrigger.POSITIVE_INTERACTION: (0.1, 0.05, -0.05, 0.1),
    EmotionalTrigger.NEGATIVE_INTERACTION: (-0.15, -0.05, 0.15, -0.1),
    EmotionalTrigger.IGNORED: (-0.05, -0.02, 0.05, -0.05),
    EmotionalTrigger.PRAISED: (0.2, 0.1, -0.1, 0.15),
    EmotionalTrigger.CRITICIZED: (-0.2, -0.05, 0.2, -0.1),
    EmotionalTrigger.HELPED_SOMEONE: (0.15, -0.02, -0.05, 0.05),
    EmotionalTrigger.RECEIVED_HELP: (0.1, 0.05, -0.1, 0.05),
    EmotionalTrigger.ACHIEVED_GOAL: (0.25, 0.15, -0.15, 0.2),
    EmotionalTrigger.FAILED_TASK: (-0.2, -0.1, 0.2, -0.15),
    EmotionalTrigger.CONFLICT: (-0.15, 0.05, 0.25, 0.1),
    EmotionalTrigger.MADE_FRIEND: (0.2, 0.1, -0.1, 0.15),
    EmotionalTrigger.LOST_FRIEND: (-0.3, -0.15, 0.2, -0.2),
    EmotionalTrigger.INTERESTING_CONVERSATION: (0.1, 0.05, -0.05, 0.1),
    EmotionalTrigger.BORING_CONVERSATION: (-0.05, -0.1, 0.02, -0.1),
    EmotionalTrigger.TIME_PASSED: (0.0, -0.02, -0.02, -0.05),
    EmotionalTrigger.ACTIVITY_SPIKE: (0.05, 0.1, 0.05, 0.15),
    EmotionalTrigger.LOW_ENGAGEMENT: (-0.05, -0.05, 0.05, -0.1),
}

# Mood transition probabilities based on current state
MOOD_TRANSITIONS = {
    MoodState.JOYFUL: {
        MoodState.JOYFUL: 0.4,
        MoodState.CONTENT: 0.35,
        MoodState.EXCITED: 0.15,
        MoodState.NEUTRAL: 0.08,
        MoodState.MELANCHOLIC: 0.01,
        MoodState.ANXIOUS: 0.01,
    },
    MoodState.CONTENT: {
        MoodState.CONTENT: 0.5,
        MoodState.JOYFUL: 0.2,
        MoodState.NEUTRAL: 0.2,
        MoodState.MELANCHOLIC: 0.05,
        MoodState.EXCITED: 0.04,
        MoodState.ANXIOUS: 0.01,
    },
    MoodState.NEUTRAL: {
        MoodState.NEUTRAL: 0.4,
        MoodState.CONTENT: 0.25,
        MoodState.MELANCHOLIC: 0.15,
        MoodState.ANXIOUS: 0.1,
        MoodState.JOYFUL: 0.05,
        MoodState.EXCITED: 0.05,
    },
    MoodState.MELANCHOLIC: {
        MoodState.MELANCHOLIC: 0.4,
        MoodState.NEUTRAL: 0.3,
        MoodState.ANXIOUS: 0.15,
        MoodState.CONTENT: 0.1,
        MoodState.JOYFUL: 0.04,
        MoodState.TIRED: 0.01,
    },
    MoodState.ANXIOUS: {
        MoodState.ANXIOUS: 0.35,
        MoodState.NEUTRAL: 0.25,
        MoodState.FRUSTRATED: 0.15,
        MoodState.MELANCHOLIC: 0.1,
        MoodState.CONTENT: 0.1,
        MoodState.TIRED: 0.05,
    },
    MoodState.EXCITED: {
        MoodState.EXCITED: 0.3,
        MoodState.JOYFUL: 0.35,
        MoodState.CONTENT: 0.2,
        MoodState.NEUTRAL: 0.1,
        MoodState.TIRED: 0.05,
    },
    MoodState.FRUSTRATED: {
        MoodState.FRUSTRATED: 0.3,
        MoodState.ANXIOUS: 0.25,
        MoodState.NEUTRAL: 0.2,
        MoodState.MELANCHOLIC: 0.15,
        MoodState.CONTENT: 0.08,
        MoodState.TIRED: 0.02,
    },
    MoodState.TIRED: {
        MoodState.TIRED: 0.4,
        MoodState.NEUTRAL: 0.3,
        MoodState.MELANCHOLIC: 0.15,
        MoodState.CONTENT: 0.1,
        MoodState.ANXIOUS: 0.05,
    },
}


# ============================================================================
# EMOTIONAL ENGINE
# ============================================================================

class EmotionalEngine:
    """
    Simulates realistic emotional dynamics for AI companions.
    Emotions influence response generation, activity levels, and behavior.
    """

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def process_trigger(
        self,
        current_state: EmotionalState,
        trigger: EmotionalTrigger,
        personality: PersonalityTraits,
        intensity: float = 1.0
    ) -> EmotionalState:
        """
        Process an emotional trigger and return updated state.

        Args:
            current_state: Current emotional state
            trigger: The trigger event
            personality: Bot's personality traits (affects sensitivity)
            intensity: How strong the trigger is (0.0 to 2.0)

        Returns:
            Updated EmotionalState
        """
        impacts = TRIGGER_IMPACTS.get(trigger, (0, 0, 0, 0))

        # Personality affects sensitivity
        sensitivity = self._calculate_sensitivity(personality)

        # Calculate new values
        mood_shift = impacts[0] * intensity * sensitivity["mood"]
        energy_shift = impacts[1] * intensity * sensitivity["energy"]
        stress_shift = impacts[2] * intensity * sensitivity["stress"]
        excitement_shift = impacts[3] * intensity * sensitivity["excitement"]

        # Update state
        new_stress = self._clamp(current_state.stress_level + stress_shift)
        new_excitement = self._clamp(current_state.excitement_level + excitement_shift)

        # Social battery drain based on extraversion
        social_drain = 0.02 if personality.extraversion < 0.4 else 0.01
        new_social = self._clamp(current_state.social_battery - social_drain)

        # Determine new mood based on overall emotional state
        new_mood = self._determine_mood(
            current_mood=current_state.mood,
            mood_shift=mood_shift,
            stress=new_stress,
            excitement=new_excitement,
            personality=personality
        )

        # Determine new energy
        new_energy = self._update_energy(
            current_energy=current_state.energy,
            energy_shift=energy_shift,
            stress=new_stress
        )

        return EmotionalState(
            mood=new_mood,
            energy=new_energy,
            stress_level=new_stress,
            excitement_level=new_excitement,
            social_battery=new_social,
            last_updated=datetime.utcnow()
        )

    def _calculate_sensitivity(self, personality: PersonalityTraits) -> Dict[str, float]:
        """Calculate emotional sensitivity based on personality."""
        return {
            "mood": 0.8 + personality.neuroticism * 0.4,
            "energy": 0.8 + personality.extraversion * 0.4,
            "stress": 0.6 + personality.neuroticism * 0.8,
            "excitement": 0.7 + personality.openness * 0.6,
        }

    def _determine_mood(
        self,
        current_mood: MoodState,
        mood_shift: float,
        stress: float,
        excitement: float,
        personality: PersonalityTraits
    ) -> MoodState:
        """Determine new mood based on various factors."""
        # Get transition probabilities for current mood
        transitions = MOOD_TRANSITIONS.get(
            current_mood,
            {MoodState.NEUTRAL: 1.0}
        )

        # Modify probabilities based on mood shift
        modified = {}
        for mood, prob in transitions.items():
            modifier = 1.0

            # Positive shift favors positive moods
            if mood_shift > 0.1:
                if mood in [MoodState.JOYFUL, MoodState.EXCITED, MoodState.CONTENT]:
                    modifier = 1.5
                elif mood in [MoodState.MELANCHOLIC, MoodState.ANXIOUS]:
                    modifier = 0.5

            # Negative shift favors negative moods
            elif mood_shift < -0.1:
                if mood in [MoodState.MELANCHOLIC, MoodState.ANXIOUS, MoodState.FRUSTRATED]:
                    modifier = 1.5
                elif mood in [MoodState.JOYFUL, MoodState.EXCITED]:
                    modifier = 0.5

            # High stress favors anxious/frustrated
            if stress > 0.7:
                if mood in [MoodState.ANXIOUS, MoodState.FRUSTRATED]:
                    modifier *= 1.3

            # High excitement favors excited
            if excitement > 0.7:
                if mood == MoodState.EXCITED:
                    modifier *= 1.4

            # Personality effects
            if personality.neuroticism > 0.7:
                if mood in [MoodState.ANXIOUS, MoodState.MELANCHOLIC]:
                    modifier *= 1.2

            if personality.extraversion > 0.7:
                if mood in [MoodState.JOYFUL, MoodState.EXCITED]:
                    modifier *= 1.2

            modified[mood] = prob * modifier

        # Normalize probabilities
        total = sum(modified.values())
        probs = [v / total for v in modified.values()]
        moods = list(modified.keys())

        return self.rng.choices(moods, weights=probs)[0]

    def _update_energy(
        self,
        current_energy: EnergyLevel,
        energy_shift: float,
        stress: float
    ) -> EnergyLevel:
        """Update energy level."""
        energy_values = {
            EnergyLevel.EXHAUSTED: 0.0,
            EnergyLevel.LOW: 0.33,
            EnergyLevel.MEDIUM: 0.66,
            EnergyLevel.HIGH: 1.0
        }

        # Get current value
        current_value = energy_values[current_energy]

        # Apply shift and stress penalty
        stress_penalty = stress * 0.1
        new_value = self._clamp(current_value + energy_shift - stress_penalty)

        # Map back to enum
        if new_value >= 0.8:
            return EnergyLevel.HIGH
        elif new_value >= 0.5:
            return EnergyLevel.MEDIUM
        elif new_value >= 0.2:
            return EnergyLevel.LOW
        else:
            return EnergyLevel.EXHAUSTED

    def apply_time_decay(
        self,
        state: EmotionalState,
        hours_passed: float,
        personality: PersonalityTraits
    ) -> EmotionalState:
        """Apply time-based emotional decay/recovery."""
        # Stress naturally decreases over time
        stress_decay = 0.02 * hours_passed
        new_stress = self._clamp(state.stress_level - stress_decay)

        # Excitement fades over time
        excitement_decay = 0.03 * hours_passed
        new_excitement = self._clamp(state.excitement_level - excitement_decay)

        # Social battery recovers when not interacting
        social_recovery = 0.05 * hours_passed * (1 - personality.extraversion)
        new_social = self._clamp(state.social_battery + social_recovery)

        # Mood trends toward neutral over time
        if hours_passed > 2:
            transitions = MOOD_TRANSITIONS.get(state.mood, {})
            # Bias toward neutral
            biased = {k: v * (2.0 if k == MoodState.NEUTRAL else 1.0)
                      for k, v in transitions.items()}
            total = sum(biased.values())
            probs = [v / total for v in biased.values()]
            new_mood = self.rng.choices(list(biased.keys()), weights=probs)[0]
        else:
            new_mood = state.mood

        # Energy recovers during "rest" (simulated)
        energy_order = [EnergyLevel.EXHAUSTED, EnergyLevel.LOW,
                        EnergyLevel.MEDIUM, EnergyLevel.HIGH]
        current_idx = energy_order.index(state.energy)

        if hours_passed > 4 and current_idx < 3:
            new_energy = energy_order[min(current_idx + 1, 3)]
        else:
            new_energy = state.energy

        return EmotionalState(
            mood=new_mood,
            energy=new_energy,
            stress_level=new_stress,
            excitement_level=new_excitement,
            social_battery=new_social,
            last_updated=datetime.utcnow()
        )

    def get_behavior_modifiers(
        self,
        state: EmotionalState,
        personality: PersonalityTraits
    ) -> Dict[str, Any]:
        """
        Get behavioral modifiers based on emotional state.
        Used to influence content generation and activity decisions.
        """
        modifiers = {
            # Tone modifiers
            "tone": state.mood.value,
            "enthusiasm": state.excitement_level,

            # Content modifiers
            "message_length_multiplier": self._get_length_multiplier(state),
            "emoji_multiplier": self._get_emoji_multiplier(state),
            "exclamation_probability": state.excitement_level * 0.5,

            # Activity modifiers
            "response_willingness": self._get_response_willingness(state, personality),
            "initiation_willingness": self._get_initiation_willingness(state, personality),
            "deep_conversation_willingness": self._get_deep_convo_willingness(state, personality),

            # Style modifiers
            "formality": 0.5 - state.excitement_level * 0.3,
            "humor_probability": self._get_humor_probability(state),
            "vulnerability_probability": self._get_vulnerability_probability(state, personality),

            # Timing modifiers
            "response_speed_multiplier": self._get_speed_multiplier(state),
        }

        return modifiers

    def _get_length_multiplier(self, state: EmotionalState) -> float:
        """Get message length multiplier based on state."""
        energy_mults = {
            EnergyLevel.HIGH: 1.2,
            EnergyLevel.MEDIUM: 1.0,
            EnergyLevel.LOW: 0.7,
            EnergyLevel.EXHAUSTED: 0.5
        }

        mood_mults = {
            MoodState.EXCITED: 1.3,
            MoodState.JOYFUL: 1.1,
            MoodState.CONTENT: 1.0,
            MoodState.NEUTRAL: 0.9,
            MoodState.TIRED: 0.6,
            MoodState.MELANCHOLIC: 0.8,
            MoodState.ANXIOUS: 1.1,
            MoodState.FRUSTRATED: 0.8
        }

        return energy_mults.get(state.energy, 1.0) * mood_mults.get(state.mood, 1.0)

    def _get_emoji_multiplier(self, state: EmotionalState) -> float:
        """Get emoji usage multiplier."""
        mood_mults = {
            MoodState.JOYFUL: 1.5,
            MoodState.EXCITED: 1.8,
            MoodState.CONTENT: 1.0,
            MoodState.NEUTRAL: 0.7,
            MoodState.MELANCHOLIC: 0.5,
            MoodState.ANXIOUS: 0.6,
            MoodState.TIRED: 0.4,
            MoodState.FRUSTRATED: 0.3
        }
        return mood_mults.get(state.mood, 1.0)

    def _get_response_willingness(
        self,
        state: EmotionalState,
        personality: PersonalityTraits
    ) -> float:
        """Calculate willingness to respond to messages."""
        base = 0.8

        # Low social battery decreases willingness
        base *= (0.5 + state.social_battery * 0.5)

        # Energy affects willingness
        if state.energy == EnergyLevel.EXHAUSTED:
            base *= 0.3
        elif state.energy == EnergyLevel.LOW:
            base *= 0.6

        # Mood effects
        if state.mood in [MoodState.TIRED, MoodState.MELANCHOLIC]:
            base *= 0.7

        # Personality
        base *= (0.7 + personality.extraversion * 0.3)
        base *= (0.8 + personality.agreeableness * 0.2)

        return self._clamp(base)

    def _get_initiation_willingness(
        self,
        state: EmotionalState,
        personality: PersonalityTraits
    ) -> float:
        """Calculate willingness to start new conversations."""
        base = 0.5

        # Extraversion strongly affects initiation
        base *= (0.3 + personality.extraversion * 1.4)

        # High excitement increases initiation
        base *= (0.8 + state.excitement_level * 0.4)

        # Social battery
        base *= state.social_battery

        # Energy
        if state.energy in [EnergyLevel.EXHAUSTED, EnergyLevel.LOW]:
            base *= 0.4

        return self._clamp(base)

    def _get_deep_convo_willingness(
        self,
        state: EmotionalState,
        personality: PersonalityTraits
    ) -> float:
        """Calculate willingness for deep/meaningful conversation."""
        base = 0.5

        # Openness increases willingness
        base *= (0.6 + personality.openness * 0.8)

        # Need sufficient energy
        if state.energy in [EnergyLevel.HIGH, EnergyLevel.MEDIUM]:
            base *= 1.2
        else:
            base *= 0.5

        # Certain moods favor deep conversation
        if state.mood in [MoodState.MELANCHOLIC, MoodState.CONTENT]:
            base *= 1.3

        return self._clamp(base)

    def _get_humor_probability(self, state: EmotionalState) -> float:
        """Calculate probability of using humor."""
        if state.mood in [MoodState.JOYFUL, MoodState.EXCITED]:
            return 0.6
        elif state.mood == MoodState.CONTENT:
            return 0.4
        elif state.mood == MoodState.NEUTRAL:
            return 0.3
        elif state.mood in [MoodState.MELANCHOLIC, MoodState.ANXIOUS]:
            return 0.1
        else:
            return 0.2

    def _get_vulnerability_probability(
        self,
        state: EmotionalState,
        personality: PersonalityTraits
    ) -> float:
        """Calculate probability of sharing vulnerable/personal content."""
        base = personality.openness * 0.3

        if state.mood == MoodState.MELANCHOLIC:
            base += 0.3
        elif state.mood == MoodState.ANXIOUS:
            base += 0.2

        # High stress can lead to venting
        base += state.stress_level * 0.2

        return self._clamp(base, 0.0, 0.5)

    def _get_speed_multiplier(self, state: EmotionalState) -> float:
        """Get response speed multiplier (higher = faster)."""
        if state.energy == EnergyLevel.HIGH and state.mood == MoodState.EXCITED:
            return 1.5
        elif state.energy in [EnergyLevel.HIGH, EnergyLevel.MEDIUM]:
            return 1.0
        elif state.energy == EnergyLevel.LOW:
            return 0.7
        else:
            return 0.5

    def _clamp(self, value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
        """Clamp value to range."""
        return max(min_val, min(max_val, value))


# ============================================================================
# FACTORY
# ============================================================================

def create_emotional_engine(seed: Optional[int] = None) -> EmotionalEngine:
    """Create an emotional engine instance."""
    return EmotionalEngine(seed=seed)
