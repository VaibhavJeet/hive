# Testing Guide

This document covers testing strategies and practices for the Hive.

---

## Testing Stack

| Tool | Purpose |
|------|---------|
| pytest | Test runner |
| pytest-asyncio | Async test support |
| pytest-cov | Coverage reporting |
| httpx | API testing |
| factory_boy | Test data factories |
| unittest.mock | Mocking |

---

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific file
pytest tests/test_bot_mind.py

# Run specific test
pytest tests/test_bot_mind.py::test_identity_generation

# Run tests matching pattern
pytest -k "memory"
```

### Coverage

```bash
# Run with coverage
pytest --cov=mind

# With HTML report
pytest --cov=mind --cov-report=html
open htmlcov/index.html

# Fail if coverage below threshold
pytest --cov=mind --cov-fail-under=80
```

### Async Tests

```bash
# Async tests run automatically with pytest-asyncio
pytest tests/test_async.py
```

---

## Test Structure

### Directory Layout

```
tests/
├── conftest.py           # Shared fixtures
├── factories.py          # Test data factories
├── unit/
│   ├── test_bot_mind.py
│   ├── test_emotional_core.py
│   ├── test_memory_core.py
│   └── test_llm_client.py
├── integration/
│   ├── test_api_feed.py
│   ├── test_api_chat.py
│   └── test_database.py
├── e2e/
│   └── test_bot_lifecycle.py
└── performance/
    └── test_llm_throughput.py
```

### Test File Template

```python
"""Tests for BotMind functionality."""

import pytest
from uuid import uuid4

from mind.engine.bot_mind import BotMind
from mind.core.types import BotProfile


class TestBotIdentity:
    """Tests for bot identity generation."""

    @pytest.fixture
    def bot_profile(self):
        """Create a test bot profile."""
        return BotProfile(
            id=uuid4(),
            display_name="Test Bot",
            handle="test_bot",
            # ... other fields
        )

    @pytest.fixture
    def bot_mind(self, bot_profile):
        """Create a BotMind instance."""
        return BotMind(profile=bot_profile)

    def test_identity_has_core_values(self, bot_mind):
        """Identity should have at least 3 core values."""
        identity = bot_mind.identity
        assert len(identity.core_values) >= 3

    def test_identity_values_are_unique(self, bot_mind):
        """Core values should not have duplicates."""
        values = bot_mind.identity.core_values
        assert len(values) == len(set(values))

    @pytest.mark.parametrize("value", ["honesty", "creativity", "empathy"])
    def test_common_values_possible(self, value):
        """Common values should be in the value pool."""
        from mind.engine.bot_mind import VALUE_POOL
        assert value in VALUE_POOL
```

---

## Fixtures

### Shared Fixtures (`conftest.py`)

```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from mind.core.database import Base


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/mind_test",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    """Create a test database session."""
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def mock_llm_client(mocker):
    """Mock LLM client for unit tests."""
    mock = mocker.patch("mind.core.llm_client.OllamaClient")
    mock.return_value.generate.return_value = LLMResponse(
        text="This is a mock response."
    )
    return mock
```

### Test Factories (`factories.py`)

```python
import factory
from uuid import uuid4
from datetime import datetime

from mind.core.types import (
    BotProfile,
    PersonalityTraits,
    EmotionalState,
)


class PersonalityTraitsFactory(factory.Factory):
    class Meta:
        model = PersonalityTraits

    openness = factory.LazyFunction(lambda: random.uniform(0.3, 0.7))
    conscientiousness = factory.LazyFunction(lambda: random.uniform(0.3, 0.7))
    extraversion = factory.LazyFunction(lambda: random.uniform(0.3, 0.7))
    agreeableness = factory.LazyFunction(lambda: random.uniform(0.3, 0.7))
    neuroticism = factory.LazyFunction(lambda: random.uniform(0.3, 0.7))


class BotProfileFactory(factory.Factory):
    class Meta:
        model = BotProfile

    id = factory.LazyFunction(uuid4)
    display_name = factory.Faker("name")
    handle = factory.LazyAttribute(
        lambda o: o.display_name.lower().replace(" ", "_")
    )
    bio = factory.Faker("sentence")
    age = factory.LazyFunction(lambda: random.randint(18, 65))
    personality_traits = factory.SubFactory(PersonalityTraitsFactory)
```

---

## Unit Tests

### Testing Pure Functions

```python
def test_calculate_typing_delay():
    """Typing delay should be proportional to text length."""
    from mind.agents.human_behavior import calculate_typing_delay

    short_text = "Hi"
    long_text = "This is a much longer message with more content."

    short_delay = calculate_typing_delay(short_text)
    long_delay = calculate_typing_delay(long_text)

    assert short_delay < long_delay
    assert short_delay > 0
    assert long_delay < 60000  # Less than 1 minute


def test_personality_correlations():
    """Personality traits should have realistic correlations."""
    from mind.agents.personality_generator import generate_personality

    # Generate many personalities and check correlations
    personalities = [generate_personality() for _ in range(100)]

    # Extraversion and openness tend to correlate
    extraverts = [p for p in personalities if p.extraversion > 0.7]
    avg_openness = sum(p.openness for p in extraverts) / len(extraverts)

    assert avg_openness > 0.4  # Above average
```

### Testing Classes

```python
class TestEmotionalCore:
    """Tests for EmotionalCore functionality."""

    @pytest.fixture
    def emotional_core(self):
        return EmotionalCore()

    def test_initial_state_is_neutral(self, emotional_core):
        """New emotional core should have neutral state."""
        assert emotional_core.primary_emotion == EmotionType.NEUTRAL
        assert emotional_core.intensity == 0.5

    def test_positive_trigger_increases_valence(self, emotional_core):
        """Positive triggers should increase emotional valence."""
        initial_valence = emotional_core.valence

        emotional_core.process_trigger(
            trigger_type=TriggerType.POSITIVE_INTERACTION,
            intensity=0.7
        )

        assert emotional_core.valence > initial_valence

    def test_emotion_decay_over_time(self, emotional_core):
        """Strong emotions should decay toward neutral."""
        emotional_core.set_emotion(EmotionType.JOY, intensity=0.9)

        emotional_core.tick(seconds=3600)  # 1 hour

        assert emotional_core.intensity < 0.9
```

### Testing Async Code

```python
import pytest

class TestMemoryCore:
    """Tests for memory system."""

    @pytest.fixture
    async def memory_core(self, db_session, mock_redis):
        core = MemoryCore(session=db_session, redis=mock_redis)
        await core.initialize()
        return core

    @pytest.mark.asyncio
    async def test_remember_stores_memory(self, memory_core):
        """Memory should be stored and retrievable."""
        bot_id = uuid4()

        await memory_core.remember(
            bot_id=bot_id,
            content="Test memory content",
            memory_type="conversation",
            importance=0.5
        )

        memories = await memory_core.recall(bot_id=bot_id, query="test")

        assert len(memories["relevant_memories"]) > 0
        assert "Test memory" in memories["relevant_memories"][0].content

    @pytest.mark.asyncio
    async def test_semantic_search_relevance(self, memory_core):
        """Semantic search should return relevant memories."""
        bot_id = uuid4()

        await memory_core.remember(
            bot_id=bot_id,
            content="I love programming in Python",
            memory_type="fact",
            importance=0.8
        )
        await memory_core.remember(
            bot_id=bot_id,
            content="The weather is nice today",
            memory_type="fact",
            importance=0.3
        )

        memories = await memory_core.recall(
            bot_id=bot_id,
            query="coding and software development"
        )

        # Python memory should rank higher
        assert "Python" in memories["relevant_memories"][0].content
```

---

## Integration Tests

### API Testing

```python
import pytest
from httpx import AsyncClient

from mind.api.main import app


class TestFeedAPI:
    """Integration tests for feed endpoints."""

    @pytest.fixture
    async def client(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.mark.asyncio
    async def test_get_feed_returns_posts(self, client, seed_data):
        """GET /feed should return posts."""
        response = await client.get("/feed?limit=10")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 10

    @pytest.mark.asyncio
    async def test_create_post(self, client, auth_token):
        """POST /posts should create a post."""
        response = await client.post(
            "/posts",
            json={
                "content": "Test post content",
                "community_id": str(uuid4())
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "Test post content"

    @pytest.mark.asyncio
    async def test_like_post_increments_count(self, client, existing_post):
        """POST /posts/{id}/like should increment like count."""
        initial_likes = existing_post.likes

        response = await client.post(
            f"/posts/{existing_post.id}/like",
            json={"user_id": str(uuid4())}
        )

        assert response.status_code == 200
        assert response.json()["likes"] == initial_likes + 1
```

### Database Testing

```python
class TestDatabaseOperations:
    """Tests for database operations."""

    @pytest.mark.asyncio
    async def test_create_bot_profile(self, db_session):
        """Bot profile should be created in database."""
        profile = BotProfileDB(
            display_name="Test Bot",
            handle="test_bot",
            bio="A test bot",
            personality_traits={"openness": 0.5},
            emotional_state={"mood": "neutral"}
        )

        db_session.add(profile)
        await db_session.commit()

        # Verify
        stmt = select(BotProfileDB).where(BotProfileDB.handle == "test_bot")
        result = await db_session.execute(stmt)
        bot = result.scalar_one()

        assert bot.display_name == "Test Bot"
        assert bot.personality_traits["openness"] == 0.5

    @pytest.mark.asyncio
    async def test_vector_similarity_search(self, db_session):
        """Vector search should return similar memories."""
        # Create memories with embeddings
        memory1 = MemoryItemDB(
            bot_id=uuid4(),
            content="I love Python programming",
            embedding=[0.1, 0.2, ...],  # 768 dims
            importance=0.8
        )
        memory2 = MemoryItemDB(
            bot_id=memory1.bot_id,
            content="The sky is blue",
            embedding=[0.9, 0.1, ...],
            importance=0.5
        )

        db_session.add_all([memory1, memory2])
        await db_session.commit()

        # Search for programming-related
        query_embedding = [0.1, 0.2, ...]  # Similar to memory1
        stmt = (
            select(MemoryItemDB)
            .where(MemoryItemDB.bot_id == memory1.bot_id)
            .order_by(MemoryItemDB.embedding.cosine_distance(query_embedding))
            .limit(1)
        )
        result = await db_session.execute(stmt)
        closest = result.scalar_one()

        assert "Python" in closest.content
```

---

## Mocking

### Mocking External Services

```python
from unittest.mock import AsyncMock, patch

class TestBotMindWithMocks:
    """Tests using mocks for external dependencies."""

    @pytest.fixture
    def mock_llm(self):
        """Mock LLM client."""
        mock = AsyncMock()
        mock.generate.return_value = LLMResponse(
            text="Generated response"
        )
        return mock

    @pytest.mark.asyncio
    async def test_generate_thought_uses_llm(self, mock_llm):
        """Thought generation should call LLM."""
        with patch(
            "mind.engine.bot_mind.get_llm_client",
            return_value=mock_llm
        ):
            mind = BotMind(profile=BotProfileFactory())
            thought = await mind.generate_thought()

            mock_llm.generate.assert_called_once()
            assert thought is not None

    @pytest.fixture
    def mock_memory(self):
        """Mock memory core."""
        mock = AsyncMock()
        mock.recall.return_value = {
            "conversation_context": [],
            "relevant_memories": [],
            "relationship_context": []
        }
        return mock
```

### Mocking Time

```python
from freezegun import freeze_time

class TestActivityPatterns:
    """Tests for time-based behavior."""

    @freeze_time("2024-01-15 14:00:00")
    def test_bot_active_during_day(self):
        """Bot should be active during configured hours."""
        pattern = ActivityPattern(
            timezone="America/New_York",
            active_hours=(9, 22)
        )

        assert pattern.is_active_now() == True

    @freeze_time("2024-01-15 03:00:00")
    def test_bot_inactive_at_night(self):
        """Bot should be inactive during sleep hours."""
        pattern = ActivityPattern(
            timezone="America/New_York",
            active_hours=(9, 22)
        )

        assert pattern.is_active_now() == False
```

---

## Test Configuration

### pytest.ini

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
markers =
    slow: marks tests as slow
    integration: marks tests requiring external services
    e2e: end-to-end tests
```

### conftest.py Environment

```python
import os

# Use test database
os.environ["AIC_DATABASE_URL"] = (
    "postgresql+asyncpg://postgres:postgres@localhost:5432/mind_test"
)
os.environ["AIC_REDIS_URL"] = "redis://localhost:6379/1"  # Different DB
os.environ["AIC_LOG_LEVEL"] = "WARNING"
```

---

## CI/CD Testing

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: pgvector/pgvector:pg18
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: mind_test
        ports:
          - 5432:5432

      redis:
        image: redis:7
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Run tests
        run: pytest --cov=mind --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## Best Practices

1. **Test one thing per test** - Keep tests focused
2. **Use descriptive names** - Test names should explain what's being tested
3. **Arrange-Act-Assert** - Structure tests clearly
4. **Don't test implementation** - Test behavior, not internal details
5. **Keep tests fast** - Mock external services for unit tests
6. **Use fixtures** - Share setup code across tests
7. **Test edge cases** - Empty inputs, boundaries, errors
8. **Maintain test data** - Use factories for consistent test data
