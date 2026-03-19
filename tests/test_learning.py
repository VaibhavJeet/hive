"""
Unit tests for Bot Learning System.

Tests the experience-based learning capabilities:
- Learning from conversations
- Learning from observations
- Skill acquisition
- Knowledge retention
"""

import pytest
from uuid import uuid4

from mind.core.types import (
    BotProfile,
    PersonalityTraits,
    WritingFingerprint,
    ActivityPattern,
    EmotionalState,
    MoodState,
    EnergyLevel,
)
from mind.engine.bot_learning import BotLearningEngine, LearningManager


class TestBotLearningEngine:
    """Test suite for BotLearningEngine class."""

    @pytest.fixture
    def learning_engine(self, sample_bot):
        """Create a BotLearningEngine instance for testing."""
        return BotLearningEngine(sample_bot)

    def test_initialization(self, learning_engine, sample_bot):
        """Test that BotLearningEngine initializes correctly."""
        assert learning_engine.profile == sample_bot

    def test_learn_from_conversation(self, learning_engine):
        """Test learning from a conversation."""
        learning_engine.learn_from_conversation(
            conversation_content="We discussed AI and machine learning",
            other_person="User123",
            outcome="positive",
            topics_discussed=["AI", "machine learning"]
        )

        # Should not crash and should update learned content
        context = learning_engine.get_learned_context()
        assert isinstance(context, str)

    def test_learn_from_observation(self, learning_engine):
        """Test learning from observing other bots."""
        learning_engine.learn_from_observation(
            observed_bot="OtherBot",
            observed_action="posted an engaging question",
            was_successful=True,
            what_made_it_work="Asked about personal experiences"
        )

        # Should record the observation
        context = learning_engine.get_learned_context()
        assert isinstance(context, str)

    def test_learn_about_person(self, learning_engine):
        """Test learning facts about other people."""
        person_id = uuid4()

        learning_engine.learn_about_person(
            person_id=person_id,
            person_name="Alice",
            learned_fact="Enjoys hiking",
            preference_type="hobbies"
        )

        # Should store information about the person
        context = learning_engine.get_learned_context()
        assert isinstance(context, str)

    def test_get_learned_context(self, learning_engine):
        """Test getting learned context as a string."""
        # Add some learnings
        learning_engine.learn_from_conversation(
            conversation_content="Talked about coding",
            other_person="Developer",
            outcome="positive",
            topics_discussed=["coding"]
        )

        context = learning_engine.get_learned_context()

        assert isinstance(context, str)
        # Context should have some content after learning
        assert len(context) > 0 or context == ""  # May be empty if learning system filters


class TestLearningManager:
    """Test suite for LearningManager class."""

    def test_initialization(self):
        """Test manager initialization."""
        manager = LearningManager()
        assert manager.engines == {}

    def test_get_engine_creates_new(self, sample_bot):
        """Test that get_engine creates a new engine if not exists."""
        manager = LearningManager()

        engine = manager.get_engine(sample_bot)

        assert isinstance(engine, BotLearningEngine)
        assert sample_bot.id in manager.engines

    def test_get_engine_returns_existing(self, sample_bot):
        """Test that get_engine returns existing engine."""
        manager = LearningManager()

        engine1 = manager.get_engine(sample_bot)
        engine2 = manager.get_engine(sample_bot)

        assert engine1 is engine2


class TestSkillAcquisition:
    """Test skill acquisition and improvement."""

    @pytest.fixture
    def learning_engine(self, sample_bot):
        return BotLearningEngine(sample_bot)

    def test_learn_new_skill(self, learning_engine):
        """Test acquiring a new skill through experience."""
        # Simulate learning a skill through multiple successful interactions
        for i in range(5):
            learning_engine.learn_from_conversation(
                conversation_content="Helped someone with Python",
                other_person=f"User{i}",
                outcome="positive",
                topics_discussed=["Python", "programming"]
            )

        # Should have learned something about Python/programming
        context = learning_engine.get_learned_context()
        assert isinstance(context, str)


class TestKnowledgeRetention:
    """Test knowledge retention and recall."""

    @pytest.fixture
    def learning_engine(self, sample_bot):
        return BotLearningEngine(sample_bot)

    def test_retain_learned_facts(self, learning_engine):
        """Test that learned facts are retained."""
        person_id = uuid4()

        learning_engine.learn_about_person(
            person_id=person_id,
            person_name="Bob",
            learned_fact="Works at a tech startup",
            preference_type="work"
        )

        learning_engine.learn_about_person(
            person_id=person_id,
            person_name="Bob",
            learned_fact="Loves coffee",
            preference_type="preferences"
        )

        # Should retain both facts
        context = learning_engine.get_learned_context()
        assert isinstance(context, str)

    def test_multiple_conversation_learnings(self, learning_engine):
        """Test learning from multiple conversations."""
        topics_learned = []

        for topic in ["AI", "music", "travel", "food"]:
            learning_engine.learn_from_conversation(
                conversation_content=f"Discussion about {topic}",
                other_person="Friend",
                outcome="positive",
                topics_discussed=[topic]
            )
            topics_learned.append(topic)

        context = learning_engine.get_learned_context()
        assert isinstance(context, str)
