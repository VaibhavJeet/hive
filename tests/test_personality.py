"""
Tests for bot personality generation and traits.

Tests the extended personality system:
- Big Five traits
- Extended personality dimensions
- Personality generation
"""

import pytest
from uuid import UUID

from mind.core.types import (
    PersonalityTraits,
    HumorStyle,
    CommunicationStyle,
    ConflictStyle,
    SocialRole,
    LearningStyle,
    DecisionStyle,
    AttachmentStyle,
    ValueOrientation,
)
from mind.agents.personality_generator import PersonalityGenerator


class TestPersonalityTraitsModel:
    """Test PersonalityTraits Pydantic model."""

    def test_default_values(self):
        """Test default trait values."""
        traits = PersonalityTraits()

        assert traits.openness == 0.5
        assert traits.conscientiousness == 0.5
        assert traits.extraversion == 0.5
        assert traits.agreeableness == 0.5
        assert traits.neuroticism == 0.5

    def test_custom_big_five(self):
        """Test custom Big Five values."""
        traits = PersonalityTraits(
            openness=0.8,
            conscientiousness=0.3,
            extraversion=0.9,
            agreeableness=0.7,
            neuroticism=0.2,
        )

        assert traits.openness == 0.8
        assert traits.extraversion == 0.9

    def test_extended_dimensions(self):
        """Test extended personality dimensions."""
        traits = PersonalityTraits(
            humor_style=HumorStyle.WITTY,
            communication_style=CommunicationStyle.DIRECT,
            conflict_style=ConflictStyle.COLLABORATIVE,
            social_role=SocialRole.LEADER,
        )

        assert traits.humor_style == HumorStyle.WITTY
        assert traits.communication_style == CommunicationStyle.DIRECT

    def test_values_and_quirks(self):
        """Test values and quirks lists."""
        traits = PersonalityTraits(
            primary_values=[ValueOrientation.CREATIVITY, ValueOrientation.KNOWLEDGE],
            quirks=["always uses ellipses...", "night owl"],
            pet_peeves=["loud chewing"],
            conversation_starters=["favorite books"],
        )

        assert len(traits.primary_values) == 2
        assert ValueOrientation.CREATIVITY in traits.primary_values
        assert "always uses ellipses..." in traits.quirks

    def test_emotional_tendencies(self):
        """Test emotional tendency values."""
        traits = PersonalityTraits(
            optimism_level=0.8,
            empathy_level=0.9,
            assertiveness_level=0.6,
            curiosity_level=0.7,
        )

        assert traits.optimism_level == 0.8
        assert traits.empathy_level == 0.9

    def test_personality_summary(self):
        """Test personality summary generation."""
        traits = PersonalityTraits(
            openness=0.9,
            extraversion=0.2,
            agreeableness=0.8,
            humor_style=HumorStyle.WITTY,
            communication_style=CommunicationStyle.ANALYTICAL,
        )

        summary = traits.get_personality_summary()

        assert "creative" in summary or "open-minded" in summary
        assert "witty" in summary


class TestHumorStyleEnum:
    """Test HumorStyle enum values."""

    def test_all_humor_styles_exist(self):
        """Test that all expected humor styles exist."""
        styles = [
            HumorStyle.WITTY,
            HumorStyle.SARCASTIC,
            HumorStyle.SELF_DEPRECATING,
            HumorStyle.ABSURDIST,
            HumorStyle.PUNNY,
            HumorStyle.DEADPAN,
            HumorStyle.OBSERVATIONAL,
            HumorStyle.GENTLE,
            HumorStyle.DARK,
            HumorStyle.NONE,
        ]

        assert len(styles) == 10


class TestCommunicationStyleEnum:
    """Test CommunicationStyle enum values."""

    def test_all_communication_styles_exist(self):
        """Test that all expected communication styles exist."""
        styles = [
            CommunicationStyle.DIRECT,
            CommunicationStyle.DIPLOMATIC,
            CommunicationStyle.ANALYTICAL,
            CommunicationStyle.EXPRESSIVE,
            CommunicationStyle.RESERVED,
            CommunicationStyle.STORYTELLING,
            CommunicationStyle.SUPPORTIVE,
            CommunicationStyle.DEBATE,
        ]

        assert len(styles) == 8


class TestValueOrientationEnum:
    """Test ValueOrientation enum values."""

    def test_all_values_exist(self):
        """Test that all expected value orientations exist."""
        values = [
            ValueOrientation.ACHIEVEMENT,
            ValueOrientation.CREATIVITY,
            ValueOrientation.CONNECTION,
            ValueOrientation.KNOWLEDGE,
            ValueOrientation.SECURITY,
            ValueOrientation.ADVENTURE,
            ValueOrientation.JUSTICE,
            ValueOrientation.HARMONY,
        ]

        assert len(values) == 8


class TestPersonalityGenerator:
    """Test PersonalityGenerator class."""

    @pytest.fixture
    def generator(self):
        """Create a seeded personality generator."""
        return PersonalityGenerator(seed=42)

    def test_generate_profile(self, generator):
        """Test generating a complete bot profile."""
        profile = generator.generate_profile()

        assert profile.id is not None
        assert profile.display_name is not None
        assert profile.handle is not None
        assert profile.personality_traits is not None

    def test_generated_traits_have_extended_dimensions(self, generator):
        """Test that generated traits include extended dimensions."""
        profile = generator.generate_profile()
        traits = profile.personality_traits

        # Extended dimensions should be populated
        assert traits.humor_style is not None
        assert traits.communication_style is not None
        assert traits.conflict_style is not None
        assert traits.social_role is not None
        assert traits.decision_style is not None

        # Values and quirks should be populated
        assert len(traits.primary_values) > 0
        assert len(traits.quirks) > 0

    def test_traits_are_consistent_with_seed(self, generator):
        """Test that same seed produces consistent results."""
        profile1 = generator.generate_profile()

        # Create new generator with same seed
        generator2 = PersonalityGenerator(seed=42)
        profile2 = generator2.generate_profile()

        # Should have same personality traits
        assert profile1.personality_traits.openness == profile2.personality_traits.openness
        assert profile1.personality_traits.humor_style == profile2.personality_traits.humor_style

    def test_traits_vary_without_seed(self):
        """Test that different seeds produce different results."""
        gen1 = PersonalityGenerator(seed=1)
        gen2 = PersonalityGenerator(seed=999)

        profile1 = gen1.generate_profile()
        profile2 = gen2.generate_profile()

        # Very unlikely to be identical with different seeds
        traits_same = (
            profile1.personality_traits.openness == profile2.personality_traits.openness and
            profile1.personality_traits.humor_style == profile2.personality_traits.humor_style
        )
        assert not traits_same

    def test_big_five_in_valid_range(self, generator):
        """Test that Big Five traits are in valid 0-1 range."""
        for _ in range(10):
            profile = generator.generate_profile()
            traits = profile.personality_traits

            assert 0.0 <= traits.openness <= 1.0
            assert 0.0 <= traits.conscientiousness <= 1.0
            assert 0.0 <= traits.extraversion <= 1.0
            assert 0.0 <= traits.agreeableness <= 1.0
            assert 0.0 <= traits.neuroticism <= 1.0

    def test_emotional_tendencies_in_valid_range(self, generator):
        """Test that emotional tendencies are in valid range."""
        for _ in range(10):
            profile = generator.generate_profile()
            traits = profile.personality_traits

            assert 0.0 <= traits.optimism_level <= 1.0
            assert 0.0 <= traits.empathy_level <= 1.0
            assert 0.0 <= traits.assertiveness_level <= 1.0
            assert 0.0 <= traits.curiosity_level <= 1.0
