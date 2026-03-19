"""
Pytest configuration and shared fixtures for Hive tests.
"""

import pytest
import asyncio
from uuid import uuid4
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from mind.core.types import (
    BotProfile,
    PersonalityTraits,
    WritingFingerprint,
    ActivityPattern,
    EmotionalState,
    MoodState,
    EnergyLevel,
    HumorStyle,
    CommunicationStyle,
    ValueOrientation,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_personality():
    """Create a sample personality for testing."""
    return PersonalityTraits(
        openness=0.8,
        conscientiousness=0.6,
        extraversion=0.7,
        agreeableness=0.65,
        neuroticism=0.3,
        humor_style=HumorStyle.WITTY,
        communication_style=CommunicationStyle.EXPRESSIVE,
        primary_values=[ValueOrientation.CREATIVITY, ValueOrientation.KNOWLEDGE],
        quirks=["uses metaphors", "says 'actually' a lot"],
        pet_peeves=["being interrupted"],
        conversation_starters=["favorite books", "tech innovations"],
        optimism_level=0.7,
        empathy_level=0.8,
    )


@pytest.fixture
def sample_writing_fingerprint():
    """Create a sample writing fingerprint."""
    return WritingFingerprint(
        avg_sentence_length=12,
        vocabulary_complexity=0.6,
        emoji_frequency=0.1,
        punctuation_style="normal",
        capitalization_style="standard",
        common_phrases=["I think"],
        filler_words=["like"],
        typo_rate=0.02,
    )


@pytest.fixture
def sample_activity_pattern():
    """Create a sample activity pattern."""
    return ActivityPattern(
        wake_time="08:00",
        sleep_time="23:00",
        peak_activity_hours=[10, 14, 20],
        avg_posts_per_day=3.0,
        avg_comments_per_day=8.0,
    )


@pytest.fixture
def sample_emotional_state():
    """Create a sample emotional state."""
    return EmotionalState(
        mood=MoodState.CONTENT,
        energy=EnergyLevel.MEDIUM,
        stress_level=0.3,
        excitement_level=0.5,
        social_battery=0.7,
    )


@pytest.fixture
def sample_bot(
    sample_personality,
    sample_writing_fingerprint,
    sample_activity_pattern,
    sample_emotional_state,
):
    """Create a sample bot profile for testing."""
    return BotProfile(
        id=uuid4(),
        display_name="TestBot",
        handle="testbot",
        bio="A test bot for unit testing.",
        avatar_seed="test123",
        age=25,
        gender="non_binary",  # Valid enum value
        location="Test City",
        backstory="Created for testing purposes.",
        interests=["testing", "coding", "AI"],
        personality_traits=sample_personality,
        writing_fingerprint=sample_writing_fingerprint,
        activity_pattern=sample_activity_pattern,
        emotional_state=sample_emotional_state,
        is_active=True,
        is_paused=False,
    )


@pytest.fixture
def sample_uuid():
    """Generate a sample UUID."""
    return uuid4()


# ============================================================================
# API TEST FIXTURES WITH MOCKED DATABASE
# ============================================================================

@pytest.fixture
def mock_db_session():
    """Create a mock database session for API tests."""
    mock_session = AsyncMock()

    # Mock execute to return empty results by default
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalars.return_value.first.return_value = None
    mock_result.scalar.return_value = 0
    mock_result.fetchone.return_value = None
    mock_result.fetchall.return_value = []

    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.refresh = AsyncMock()

    return mock_session


@pytest.fixture
def api_client(mock_db_session):
    """Create a test client with mocked database session."""
    from mind.api.main import app
    from mind.api.dependencies import get_db_session

    async def mock_get_db_session():
        yield mock_db_session

    app.dependency_overrides[get_db_session] = mock_get_db_session

    client = TestClient(app)
    yield client

    # Clean up override after test
    app.dependency_overrides.clear()
