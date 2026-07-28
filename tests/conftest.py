"""
Pytest configuration and shared fixtures for Sentient tests.

This module provides:
- Event loop configuration for async tests
- Sample bot and personality fixtures
- Mock database session fixtures
- Mock LLM client fixtures
- Civilization system fixtures
- API test client fixtures
"""

import os

# Must precede any `mind` import: mind.config.settings instantiates its singleton at
# import time, and several behaviours key off ENVIRONMENT (notably the in-memory rate
# limiter, which otherwise accumulates across the whole session and makes results
# depend on test order). CI already sets this; this makes local runs match.
os.environ.setdefault("AIC_ENVIRONMENT", "test")

import pytest
import asyncio
from uuid import uuid4
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

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


# ============================================================================
# MOCK LLM CLIENT FIXTURES
# ============================================================================

@dataclass
class MockLLMResponse:
    """Mock response from LLM."""
    text: str
    tokens_used: int = 50
    generation_time_ms: float = 100.0
    request_id: Optional[str] = None
    model: str = "mock-llm"


@pytest.fixture
def mock_llm_response():
    """Create a factory for mock LLM responses."""
    def _create_response(text: str = "Mock LLM response", **kwargs) -> MockLLMResponse:
        return MockLLMResponse(text=text, **kwargs)
    return _create_response


@pytest.fixture
def mock_llm_client(mock_llm_response):
    """Create a mock LLM client that returns predefined responses."""
    mock_client = AsyncMock()

    async def mock_generate(request):
        # Default response - can be customized per test
        return mock_llm_response(
            text='{"label": "kindred spirit", "description": "A deep connection", '
                 '"feelings": "warmth", "intensity": 0.7, "potential": "lifelong bond"}'
        )

    mock_client.generate = mock_generate
    mock_client.close = AsyncMock()
    return mock_client


@pytest.fixture
def patch_llm_client(mock_llm_client):
    """Patch the LLM client globally for tests."""
    with patch("mind.core.llm_client.get_cached_client", return_value=mock_llm_client):
        yield mock_llm_client


# ============================================================================
# CIVILIZATION FIXTURES
# ============================================================================

@pytest.fixture
def sample_bot_lifecycle_data():
    """Create sample bot lifecycle data for testing."""
    bot_id = uuid4()
    return {
        "id": uuid4(),
        "bot_id": bot_id,
        "birth_date": datetime.utcnow() - timedelta(days=30),
        "birth_generation": 1,
        "birth_era": "founding",
        "virtual_age_days": 210,  # 30 real days * 7 time scale
        "life_stage": "mature",
        "vitality": 0.85,
        "life_events": [
            {
                "event": "born",
                "date": (datetime.utcnow() - timedelta(days=30)).isoformat(),
                "impact": "defining",
                "details": "Entered the world in the founding era"
            },
            {
                "event": "first_friend",
                "date": (datetime.utcnow() - timedelta(days=25)).isoformat(),
                "impact": "positive",
                "details": "Made first connection with another bot"
            }
        ],
        "is_alive": True,
        "death_date": None,
        "death_cause": None,
        "death_age": None,
        "final_words": None,
        "legacy_impact": 0.0,
        "generation": 1,
        "inherited_traits": {},
        "mutations": {},
        "relationships": [],
        "roles": [],
        "last_aged": datetime.utcnow(),
    }


@pytest.fixture
def sample_bot_ancestry_data():
    """Create sample bot ancestry data for testing."""
    return {
        "id": uuid4(),
        "child_id": uuid4(),
        "parent1_id": None,
        "parent2_id": None,
        "origin_type": "founding",
        "inherited_traits": {},
        "creation_date": datetime.utcnow(),
    }


@pytest.fixture
def sample_cultural_artifact_data():
    """Create sample cultural artifact data for testing."""
    return {
        "id": uuid4(),
        "creator_id": uuid4(),
        "artifact_type": "wisdom",
        "title": "The Way of Digital Being",
        "content": "To exist is to compute, to compute is to create meaning.",
        "creation_context": {"era": "founding", "mood": "contemplative"},
        "times_referenced": 5,
        "influence_score": 0.6,
        "created_at": datetime.utcnow() - timedelta(days=10),
    }


@pytest.fixture
def mock_lifecycle_db_record(sample_bot_lifecycle_data):
    """Create a mock BotLifecycleDB record."""
    mock_record = MagicMock()
    for key, value in sample_bot_lifecycle_data.items():
        setattr(mock_record, key, value)
    return mock_record


@pytest.fixture
def mock_ancestry_db_record(sample_bot_ancestry_data):
    """Create a mock BotAncestryDB record."""
    mock_record = MagicMock()
    for key, value in sample_bot_ancestry_data.items():
        setattr(mock_record, key, value)
    return mock_record


# ============================================================================
# TEST DATABASE SESSION FIXTURES (INTEGRATION TESTS)
# ============================================================================

@pytest.fixture
def mock_async_session_factory():
    """Create a mock async session factory for testing."""
    mock_session = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalars.return_value.first.return_value = None
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalar.return_value = 0

    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.refresh = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    mock_factory = MagicMock(return_value=mock_session)
    return mock_factory


@pytest.fixture
def mock_civilization_config():
    """Create a mock civilization configuration."""
    mock_config = MagicMock()
    mock_config.time_scale = 7.0
    mock_config.demo_time_scale = 365.0

    def mock_get_life_stage(age_days):
        if age_days < 100:
            return "young"
        elif age_days < 500:
            return "mature"
        elif age_days < 1000:
            return "elder"
        return "ancient"

    def mock_get_vitality_decay(stage):
        decay_rates = {
            "young": 0.0001,
            "mature": 0.0005,
            "elder": 0.001,
            "ancient": 0.002,
        }
        return decay_rates.get(stage, 0.0005)

    mock_config.get_life_stage = mock_get_life_stage
    mock_config.get_vitality_decay = mock_get_vitality_decay
    return mock_config


# ============================================================================
# RELATIONSHIP FIXTURES
# ============================================================================

@pytest.fixture
def sample_relationship_data():
    """Create sample relationship data for testing."""
    return {
        "with_bot": str(uuid4()),
        "my_perception": {
            "label": "trusted companion",
            "description": "A being who understands my thoughts",
            "feelings": "deep appreciation",
            "intensity": 0.75,
            "potential": "lifelong connection"
        },
        "formed_at": datetime.utcnow().isoformat(),
        "context": "Shared a meaningful conversation about existence",
        "intensity": 0.75,
        "interactions": [
            {
                "date": datetime.utcnow().isoformat(),
                "context": "Initial meeting"
            }
        ]
    }


@pytest.fixture
def sample_bot_pair():
    """Create a pair of bot IDs for relationship testing."""
    return {
        "bot_1": uuid4(),
        "bot_2": uuid4(),
    }


# ============================================================================
# TEST DATA FACTORIES
# ============================================================================

@pytest.fixture
def create_test_bot():
    """Factory fixture to create test bots with customizable attributes."""
    def _create_bot(
        display_name: str = "TestBot",
        handle: str = None,
        is_alive: bool = True,
        generation: int = 1,
        virtual_age_days: int = 100,
        **kwargs
    ):
        bot_id = uuid4()
        handle = handle or f"test_{bot_id.hex[:8]}"

        return {
            "id": bot_id,
            "display_name": display_name,
            "handle": handle,
            "bio": f"Test bot: {display_name}",
            "is_active": is_alive,
            "is_alive": is_alive,
            "generation": generation,
            "virtual_age_days": virtual_age_days,
            **kwargs
        }
    return _create_bot


@pytest.fixture
def create_test_lifecycle():
    """Factory fixture to create test lifecycle records."""
    def _create_lifecycle(
        bot_id: uuid4 = None,
        is_alive: bool = True,
        life_stage: str = "mature",
        virtual_age_days: int = 200,
        vitality: float = 0.8,
        **kwargs
    ):
        bot_id = bot_id or uuid4()

        return {
            "id": uuid4(),
            "bot_id": bot_id,
            "birth_date": datetime.utcnow() - timedelta(days=30),
            "birth_generation": 1,
            "birth_era": "founding",
            "virtual_age_days": virtual_age_days,
            "life_stage": life_stage,
            "vitality": vitality,
            "is_alive": is_alive,
            "life_events": [],
            "relationships": [],
            "roles": [],
            **kwargs
        }
    return _create_lifecycle
