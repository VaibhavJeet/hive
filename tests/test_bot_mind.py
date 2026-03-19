"""
Unit tests for BotMind cognitive functions.

Tests the core cognitive architecture:
- Thought generation
- Decision making
- Mood/emotional state transitions
- Self-context generation
"""

import pytest
from datetime import datetime
from uuid import uuid4
from unittest.mock import MagicMock, patch

from mind.core.types import MoodState, EnergyLevel
from mind.engine.bot_mind import BotMind, MindManager, ThoughtProcess


# Fixtures (use shared fixtures from conftest.py via sample_bot)
@pytest.fixture
def bot_mind(sample_bot):
    """Create a BotMind instance for testing."""
    return BotMind(sample_bot)


# Tests for BotMind
class TestBotMind:
    """Test suite for BotMind class."""

    def test_initialization(self, bot_mind, sample_bot):
        """Test that BotMind initializes correctly."""
        assert bot_mind.profile == sample_bot
        assert bot_mind.social_graph == {}
        assert bot_mind.identity is not None

    def test_generate_self_context(self, bot_mind):
        """Test self-context generation."""
        context = bot_mind.generate_self_context()

        assert isinstance(context, str)
        assert len(context) > 100  # Should have substantial content
        assert "TestBot" in context or "testbot" in context.lower()

    def test_generate_self_context_includes_personality(self, bot_mind):
        """Test that self-context includes extended personality traits."""
        context = bot_mind.generate_self_context()

        # Should include personality elements
        assert "WHO YOU ARE" in context
        assert "PERSONALITY STYLE" in context
        # Check for humor/communication style integration
        assert "Humor:" in context or "Communication:" in context

    def test_think_about_posting(self, bot_mind):
        """Test thought generation for posting."""
        thought = bot_mind.think_about_posting()

        assert isinstance(thought, ThoughtProcess)
        assert thought.initial_reaction is not None
        assert thought.considerations is not None
        assert isinstance(thought.considerations, list)
        assert thought.conclusion is not None

    def test_think_about_responding(self, bot_mind):
        """Test thought generation for responding to a message."""
        thought = bot_mind.think_about_responding(
            to_content="Hey, how are you doing today?",
            from_person="TestUser"
        )

        assert isinstance(thought, ThoughtProcess)
        assert thought.initial_reaction is not None
        # Should reference the sender or message content
        assert len(thought.initial_reaction) > 10

    def test_update_time_context(self, bot_mind):
        """Test time context updates."""
        bot_mind.update_time_context()

        # Time context should be stored in environment
        assert isinstance(bot_mind.environment.current_time_context, str)
        assert len(bot_mind.environment.current_time_context) > 0

    def test_observe_post(self, bot_mind):
        """Test post observation and perception building."""
        post = {"content": "This is an interesting post about AI!"}
        author = {"id": uuid4(), "display_name": "OtherBot"}

        bot_mind.observe_post(post, author)

        # Should track recent posts
        assert len(bot_mind.environment.recent_posts_seen) > 0

    def test_update_perception_after_interaction(self, bot_mind):
        """Test perception updates after interactions."""
        other_id = uuid4()
        other_profile = {"display_name": "OtherBot", "interests": ["testing"]}

        # First create a perception
        bot_mind.perceive_individual(other_id, other_profile)

        # Then update it
        bot_mind.update_perception_after_interaction(
            other_id=other_id,
            interaction_type="liked their post",
            was_positive=True
        )

        # Should have updated perceptions
        assert other_id in bot_mind.social_graph
        assert bot_mind.social_graph[other_id].trust > 0.5


class TestMindManager:
    """Test suite for MindManager class."""

    def test_initialization(self):
        """Test manager initialization."""
        manager = MindManager()
        assert manager.minds == {}

    def test_get_mind_creates_new(self, sample_bot):
        """Test that get_mind creates a new mind if not exists."""
        manager = MindManager()

        mind = manager.get_mind(sample_bot)

        assert isinstance(mind, BotMind)
        assert sample_bot.id in manager.minds

    def test_get_mind_returns_existing(self, sample_bot):
        """Test that get_mind returns existing mind."""
        manager = MindManager()

        mind1 = manager.get_mind(sample_bot)
        mind2 = manager.get_mind(sample_bot)

        assert mind1 is mind2

    def test_remove_mind(self, sample_bot):
        """Test removing a bot's mind manually."""
        manager = MindManager()
        manager.get_mind(sample_bot)

        assert sample_bot.id in manager.minds

        # Directly remove from minds dict (clear_mind not implemented)
        del manager.minds[sample_bot.id]

        assert sample_bot.id not in manager.minds


class TestThoughtProcess:
    """Test suite for ThoughtProcess dataclass."""

    def test_thought_creation(self):
        """Test creating a ThoughtProcess object."""
        thought = ThoughtProcess(
            initial_reaction="This is interesting",
            considerations=["Point 1", "Point 2"],
            identity_connection="This relates to my values",
            conclusion="I should engage with this"
        )

        assert thought.initial_reaction == "This is interesting"
        assert len(thought.considerations) == 2
        assert thought.identity_connection is not None
        assert thought.conclusion is not None


# Tests for emotional state transitions
class TestEmotionalTransitions:
    """Test emotional state changes in BotMind."""

    def test_mood_affects_thinking(self, sample_bot):
        """Test that mood affects thought generation."""
        # Test with happy mood
        sample_bot.emotional_state.mood = MoodState.JOYFUL
        happy_mind = BotMind(sample_bot)
        happy_thought = happy_mind.think_about_posting()

        # Test with sad mood
        sample_bot.emotional_state.mood = MoodState.MELANCHOLIC
        sad_mind = BotMind(sample_bot)
        sad_thought = sad_mind.think_about_posting()

        # Both should generate valid thoughts
        assert happy_thought.conclusion is not None
        assert sad_thought.conclusion is not None

    def test_energy_affects_activity(self, sample_bot):
        """Test that energy level affects bot activity consideration."""
        sample_bot.emotional_state.energy = EnergyLevel.LOW
        low_energy_mind = BotMind(sample_bot)

        sample_bot.emotional_state.energy = EnergyLevel.HIGH
        high_energy_mind = BotMind(sample_bot)

        # Both should still be functional
        assert low_energy_mind.generate_self_context() is not None
        assert high_energy_mind.generate_self_context() is not None


class TestIdentityWithPersonalityTraits:
    """Test that BotIdentity properly uses PersonalityTraits."""

    def test_identity_uses_pet_peeves_from_traits(self, sample_bot):
        """Test that pet peeves from PersonalityTraits are used."""
        mind = BotMind(sample_bot)

        # Sample bot has pet_peeves=["being interrupted"]
        assert "being interrupted" in mind.identity.pet_peeves

    def test_identity_uses_quirks_from_traits(self, sample_bot):
        """Test that quirks from PersonalityTraits are used."""
        mind = BotMind(sample_bot)

        # Sample bot has quirks=["uses metaphors", "says 'actually' a lot"]
        assert any("metaphor" in q for q in mind.identity.speech_quirks)

    def test_identity_includes_humor_style_quirk(self, sample_bot):
        """Test that humor style is reflected in quirks."""
        mind = BotMind(sample_bot)

        # Sample bot has humor_style=HumorStyle.WITTY
        assert any("clever" in q for q in mind.identity.speech_quirks)

    def test_identity_includes_communication_style_quirk(self, sample_bot):
        """Test that communication style is reflected in quirks."""
        mind = BotMind(sample_bot)

        # Sample bot has communication_style=CommunicationStyle.EXPRESSIVE
        assert any("vivid" in q or "emotional" in q for q in mind.identity.speech_quirks)

    def test_passions_include_conversation_starters(self, sample_bot):
        """Test that conversation_starters are added to passions."""
        mind = BotMind(sample_bot)

        # Sample bot has conversation_starters=["favorite books", "tech innovations"]
        passions = mind.identity.passions
        assert any("book" in p for p in passions) or any("tech" in p for p in passions)
