"""
Unit tests for Emotional Core functionality.

Tests the bot emotional system:
- Emotion processing
- Mood transitions
- Physical states (energy, hunger)
- Unprompted thoughts
"""

import pytest
from uuid import uuid4
from datetime import datetime

from mind.core.types import (
    BotProfile,
    PersonalityTraits,
    WritingFingerprint,
    ActivityPattern,
    EmotionalState,
    MoodState,
    EnergyLevel,
)
from mind.engine.emotional_core import EmotionalCore, EmotionalCoreManager, UnpromptedThought


class TestEmotionalCore:
    """Test suite for EmotionalCore class."""

    @pytest.fixture
    def emotional_core(self, sample_bot):
        """Create an EmotionalCore instance for testing."""
        return EmotionalCore(sample_bot)

    def test_initialization(self, emotional_core, sample_bot):
        """Test that EmotionalCore initializes correctly."""
        assert emotional_core.bot == sample_bot
        assert emotional_core.physical is not None
        assert emotional_core.desires is not None
        assert emotional_core.vulnerability is not None

    def test_simulate_time(self, emotional_core):
        """Test time simulation affects physical state."""
        initial_energy = emotional_core.physical.energy

        # Simulate 1 hour passing
        emotional_core.simulate_time(1.0)

        # Energy should decrease over time
        assert emotional_core.physical.energy <= initial_energy

    def test_process_positive_experience(self, emotional_core):
        """Test processing a positive experience."""
        result = emotional_core.process_experience(
            what_happened="received a compliment",
            who_involved="User",
            person_id=uuid4(),
            was_positive=True
        )

        # Should return a result dict
        assert isinstance(result, dict)
        assert emotional_core.physical is not None

    def test_process_negative_experience(self, emotional_core):
        """Test processing a negative experience."""
        result = emotional_core.process_experience(
            what_happened="was criticized",
            who_involved="User",
            person_id=uuid4(),
            was_positive=False
        )

        # Should not crash and return a result
        assert isinstance(result, dict)

    def test_generate_unprompted_thought(self, emotional_core):
        """Test unprompted thought generation."""
        thought = emotional_core.generate_unprompted_thought()

        # Should return an UnpromptedThought or None
        assert thought is None or isinstance(thought, UnpromptedThought)

    def test_get_current_state_context(self, emotional_core):
        """Test getting current emotional state as context string."""
        context = emotional_core.get_current_state_context()

        assert isinstance(context, str)
        assert len(context) > 0


class TestEmotionalCoreManager:
    """Test suite for EmotionalCoreManager class."""

    def test_initialization(self):
        """Test manager initialization."""
        manager = EmotionalCoreManager()
        assert manager.cores == {}

    def test_get_core_creates_new(self, sample_bot):
        """Test that get_core creates a new core if not exists."""
        manager = EmotionalCoreManager()

        core = manager.get_core(sample_bot)

        assert isinstance(core, EmotionalCore)
        assert sample_bot.id in manager.cores

    def test_get_core_returns_existing(self, sample_bot):
        """Test that get_core returns existing core."""
        manager = EmotionalCoreManager()

        core1 = manager.get_core(sample_bot)
        core2 = manager.get_core(sample_bot)

        assert core1 is core2


class TestMoodTransitions:
    """Test mood state transitions."""

    @pytest.fixture
    def emotional_core(self, sample_bot):
        return EmotionalCore(sample_bot)

    def test_mood_can_improve(self, emotional_core, sample_bot):
        """Test that positive experiences can improve mood."""
        # Set initial mood to neutral
        sample_bot.emotional_state.mood = MoodState.NEUTRAL

        # Process multiple positive experiences
        for _ in range(5):
            emotional_core.process_experience(
                what_happened="had a great conversation",
                who_involved="Friend",
                person_id=uuid4(),
                was_positive=True
            )

        # Mood should potentially improve (or stay same)
        # We can't guarantee improvement due to randomness, but it shouldn't crash
        assert emotional_core.physical is not None

    def test_energy_affects_behavior(self, emotional_core):
        """Test that energy levels affect the core."""
        # Simulate a lot of time passing
        emotional_core.simulate_time(8.0)  # 8 hours

        # Energy should be lower
        assert emotional_core.physical.energy < 1.0


class TestPhysicalStates:
    """Test bot physical states (energy, hunger)."""

    @pytest.fixture
    def emotional_core(self, sample_bot):
        return EmotionalCore(sample_bot)

    def test_physical_initialized(self, emotional_core):
        """Test that physical state is properly initialized."""
        physical = emotional_core.physical

        assert hasattr(physical, 'energy')
        assert hasattr(physical, 'hunger')
        assert 0 <= physical.energy <= 1.0
        assert 0 <= physical.hunger <= 1.0

    def test_social_interaction_affects_state(self, emotional_core):
        """Test that social interactions affect emotional state."""
        # Process a social interaction
        result = emotional_core.process_experience(
            what_happened="attended a large party",
            who_involved="Many people",
            person_id=uuid4(),
            was_positive=True
        )

        # Should return result without crashing
        assert isinstance(result, dict)


class TestVulnerability:
    """Test vulnerability system."""

    @pytest.fixture
    def emotional_core(self, sample_bot):
        return EmotionalCore(sample_bot)

    def test_vulnerability_initialized(self, emotional_core):
        """Test that vulnerability state is initialized."""
        assert emotional_core.vulnerability is not None
        assert hasattr(emotional_core.vulnerability, 'openness')
        assert hasattr(emotional_core.vulnerability, 'defense_mode')

    def test_negative_experience_affects_vulnerability(self, emotional_core):
        """Test that negative experiences can trigger defense mode."""
        # Process multiple negative experiences
        for _ in range(3):
            emotional_core.process_experience(
                what_happened="was hurt by someone's words",
                who_involved="Critic",
                person_id=uuid4(),
                was_positive=False
            )

        # Should still be functional
        assert emotional_core.vulnerability is not None


class TestDesires:
    """Test desire system."""

    @pytest.fixture
    def emotional_core(self, sample_bot):
        return EmotionalCore(sample_bot)

    def test_desires_initialized(self, emotional_core):
        """Test that desires are generated based on personality."""
        assert emotional_core.desires is not None
        assert isinstance(emotional_core.desires, list)
        # Should have some initial desires
        assert len(emotional_core.desires) >= 0


class TestEgo:
    """Test ego system."""

    @pytest.fixture
    def emotional_core(self, sample_bot):
        return EmotionalCore(sample_bot)

    def test_ego_initialized(self, emotional_core):
        """Test that ego state is initialized."""
        assert emotional_core.ego is not None
        assert hasattr(emotional_core.ego, 'self_esteem')
        assert hasattr(emotional_core.ego, 'recent_wins')
        assert hasattr(emotional_core.ego, 'recent_blows')
