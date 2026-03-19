# Code Style Guide

This document outlines the coding standards and best practices for the Hive.

---

## Python Code Style

### General Principles

- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Use type hints everywhere
- Write self-documenting code
- Keep functions focused and small

### Formatting

We use:
- **Black** for code formatting (line length: 88)
- **isort** for import sorting
- **Ruff** for linting

```bash
# Format code
black mind/
isort mind/

# Lint
ruff check mind/
```

### Imports

Order imports as:
1. Standard library
2. Third-party packages
3. Local modules

```python
# Good
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from mind.core.database import async_session_factory
from mind.core.types import BotProfile
```

### Type Hints

Always use type hints:

```python
# Good
async def get_bot(bot_id: UUID) -> Optional[BotProfile]:
    ...

def calculate_delay(base: float, factor: float = 1.0) -> int:
    ...

# With complex types
from typing import Dict, List, Optional, TypeVar, Generic

T = TypeVar('T')

class Cache(Generic[T]):
    def get(self, key: str) -> Optional[T]:
        ...
```

### Docstrings

Use Google-style docstrings:

```python
async def generate_post(
    bot: BotProfile,
    community_id: UUID,
    context: Optional[str] = None
) -> Post:
    """Generate an autonomous post from a bot.

    Args:
        bot: The bot profile generating the post.
        community_id: Target community for the post.
        context: Optional context to influence content.

    Returns:
        The created Post object.

    Raises:
        LLMError: If LLM generation fails.
        DatabaseError: If post cannot be saved.
    """
    ...
```

### Classes

```python
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class BotIdentity:
    """Core identity components of a bot's mind.

    Attributes:
        core_values: Fundamental values the bot holds.
        beliefs: Opinions on various topics.
        current_goals: What the bot is working toward.
    """

    core_values: List[str]
    beliefs: Dict[str, Opinion]
    current_goals: List[str]

    def has_value(self, value: str) -> bool:
        """Check if bot holds a specific value."""
        return value.lower() in [v.lower() for v in self.core_values]
```

### Async Code

```python
# Good - use async context managers
async with async_session_factory() as session:
    result = await session.execute(stmt)

# Good - gather for parallel operations
results = await asyncio.gather(
    fetch_memories(bot_id),
    fetch_relationships(bot_id),
    fetch_context(bot_id),
)

# Good - proper error handling
try:
    response = await llm_client.generate(request)
except LLMTimeoutError:
    logger.warning(f"LLM timeout for bot {bot_id}")
    return fallback_response()
```

### Error Handling

```python
# Define custom exceptions
class BotError(Exception):
    """Base exception for bot-related errors."""
    pass

class BotNotFoundError(BotError):
    """Bot does not exist."""
    pass

class LLMError(Exception):
    """LLM-related errors."""
    pass

# Use specific exceptions
async def get_bot(bot_id: UUID) -> BotProfile:
    bot = await db.get(bot_id)
    if not bot:
        raise BotNotFoundError(f"Bot {bot_id} not found")
    return bot

# Handle at appropriate level
@router.get("/bots/{bot_id}")
async def get_bot_endpoint(bot_id: UUID):
    try:
        return await get_bot(bot_id)
    except BotNotFoundError:
        raise HTTPException(status_code=404, detail="Bot not found")
```

### Logging

```python
import logging

logger = logging.getLogger(__name__)

# Use appropriate levels
logger.debug("Detailed info for debugging")
logger.info("Bot %s created post", bot.handle)
logger.warning("LLM response slow: %dms", latency)
logger.error("Database connection failed: %s", error)

# Include context
logger.info(
    "Post created",
    extra={
        "bot_id": str(bot.id),
        "community_id": str(community_id),
        "content_length": len(content),
    }
)
```

---

## Naming Conventions

### Variables and Functions

```python
# snake_case for variables and functions
bot_profile = await get_bot_profile(bot_id)
emotional_state = calculate_emotional_state(triggers)

# Descriptive names
# Bad
x = get_data()
# Good
bot_memories = await fetch_relevant_memories(bot_id, query)
```

### Classes

```python
# PascalCase for classes
class BotMind:
    pass

class EmotionalCore:
    pass

class CommunityOrchestrator:
    pass
```

### Constants

```python
# UPPER_SNAKE_CASE for constants
MAX_CONCURRENT_REQUESTS = 8
DEFAULT_CACHE_SIZE = 1000
THOUGHT_MODES = ["wandering", "focused", "reflective"]
```

### Database Models

```python
# Suffix with DB for SQLAlchemy models
class BotProfileDB(Base):
    __tablename__ = "bot_profiles"

class MemoryItemDB(Base):
    __tablename__ = "memory_items"
```

---

## Project Structure

### File Organization

```python
# One class per file for major components
# mind/engine/bot_mind.py
class BotMind:
    ...

# Related classes can be grouped
# mind/core/types.py
@dataclass
class BotProfile:
    ...

@dataclass
class PersonalityTraits:
    ...
```

### Module Layout

```python
# mind/engine/__init__.py
from mind.engine.bot_mind import BotMind
from mind.engine.emotional_core import EmotionalCore
from mind.engine.conscious_mind import ConsciousMind

__all__ = ["BotMind", "EmotionalCore", "ConsciousMind"]
```

---

## Testing

### Test File Structure

```python
# tests/test_bot_mind.py
import pytest
from mind.engine.bot_mind import BotMind


class TestBotIdentity:
    """Tests for bot identity generation."""

    def test_identity_has_values(self):
        identity = generate_identity()
        assert len(identity.core_values) >= 3

    def test_identity_values_are_unique(self):
        identity = generate_identity()
        assert len(identity.core_values) == len(set(identity.core_values))


class TestSocialPerception:
    """Tests for social perception."""

    @pytest.fixture
    def bot_mind(self):
        return BotMind(bot_id=UUID("..."))

    async def test_perception_creation(self, bot_mind):
        perception = await bot_mind.form_perception("Alex")
        assert perception.target_name == "Alex"
        assert 0 <= perception.trust <= 1
```

### Test Naming

```python
# test_<what>_<condition>_<expected>
def test_generate_post_with_context_includes_context():
    ...

def test_emotional_trigger_negative_decreases_mood():
    ...

def test_memory_recall_returns_most_relevant():
    ...
```

---

## Dart/Flutter Code Style

### General

- Follow [Effective Dart](https://dart.dev/guides/language/effective-dart)
- Use `flutter_lints` package

### Naming

```dart
// Classes - PascalCase
class PostCard extends StatelessWidget { }

// Variables, functions - camelCase
final postContent = post.content;
void handleLike() { }

// Constants - lowerCamelCase
const defaultPadding = 16.0;

// Files - snake_case
// lib/widgets/post_card.dart
```

### Widget Structure

```dart
class PostCard extends StatelessWidget {
  // 1. Constructor
  const PostCard({
    super.key,
    required this.post,
    this.onLike,
  });

  // 2. Final fields
  final Post post;
  final VoidCallback? onLike;

  // 3. Build method
  @override
  Widget build(BuildContext context) {
    return Card(
      child: _buildContent(context),
    );
  }

  // 4. Private helper methods
  Widget _buildContent(BuildContext context) {
    return Column(
      children: [
        _buildHeader(),
        _buildBody(),
        _buildActions(),
      ],
    );
  }

  Widget _buildHeader() { ... }
  Widget _buildBody() { ... }
  Widget _buildActions() { ... }
}
```

### State Management

```dart
// Use Provider for state
class AppState extends ChangeNotifier {
  List<Post> _posts = [];

  List<Post> get posts => _posts;

  Future<void> loadPosts() async {
    _posts = await ApiService.getPosts();
    notifyListeners();
  }

  void addPost(Post post) {
    _posts.insert(0, post);
    notifyListeners();
  }
}
```

---

## Documentation

### Code Comments

```python
# Explain WHY, not WHAT
# Bad
# Increment counter
counter += 1

# Good
# Track consecutive failures for circuit breaker
consecutive_failures += 1
```

### TODO Comments

```python
# TODO(username): Description of what needs to be done
# TODO(alex): Add caching for memory queries - #123
```

### API Documentation

```python
@router.post("/posts/{post_id}/like")
async def like_post(
    post_id: UUID,
    user_id: UUID = Body(..., embed=True)
) -> LikeResponse:
    """
    Like a post.

    - **post_id**: UUID of the post to like
    - **user_id**: UUID of the user liking

    Returns the updated like count.

    Raises:
    - **404**: Post not found
    - **409**: Already liked
    """
    ...
```

---

## Git Practices

### Commits

- Small, focused commits
- Present tense ("add feature" not "added feature")
- Reference issues when applicable

```bash
git commit -m "feat: add creative thought mode to ConsciousMind

- Implement creative mode selection
- Add probability weighting
- Include tests

Closes #123"
```

### Branches

```bash
# Feature branches
feature/creative-thought-mode
feature/memory-caching

# Bug fixes
fix/websocket-reconnection
fix/memory-leak-activity-engine

# Maintenance
chore/update-dependencies
docs/api-endpoints
```

---

## Security

### Sensitive Data

```python
# Never log sensitive data
# Bad
logger.info(f"User logged in with password: {password}")

# Good
logger.info(f"User {user_id} logged in")

# Use environment variables for secrets
from mind.config import settings
secret_key = settings.SECRET_KEY  # From .env
```

### Input Validation

```python
from pydantic import BaseModel, Field, validator

class CreatePostRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    community_id: UUID

    @validator('content')
    def sanitize_content(cls, v):
        # Remove potentially harmful content
        return sanitize_html(v)
```

---

## Performance

### Async Best Practices

```python
# Use gather for parallel operations
results = await asyncio.gather(
    fetch_a(),
    fetch_b(),
    fetch_c(),
)

# Use connection pooling
async with aiohttp.ClientSession() as session:
    ...

# Limit concurrency
semaphore = asyncio.Semaphore(10)
async with semaphore:
    await expensive_operation()
```

### Caching

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def expensive_computation(key: str) -> Result:
    ...

# For async, use dedicated cache
cache = LRUCache(maxsize=1000)
```
