"""
Base Loop - Abstract base class for all activity loops.

Provides shared utilities for:
- Content deduplication
- LLM semaphore access
- Event broadcasting
- Bot management helpers
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Set, TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from mind.core.types import BotProfile

logger = logging.getLogger(__name__)


class BaseLoop(ABC):
    """
    Abstract base class for all activity loops.

    Provides shared functionality that all loops need:
    - Content deduplication tracking
    - Access to LLM semaphore for rate limiting
    - Event broadcasting to connected clients
    - Bot management helpers
    """

    def __init__(
        self,
        active_bots: Dict[UUID, "BotProfile"],
        llm_semaphore: asyncio.Semaphore,
        event_broadcast: Optional[asyncio.Queue] = None,
        recent_content: Optional[Dict[UUID, List[str]]] = None,
        max_recent_content: int = 20
    ):
        """
        Initialize the base loop.

        Args:
            active_bots: Dictionary of active bot profiles by ID
            llm_semaphore: Semaphore for rate limiting LLM calls
            event_broadcast: Queue for broadcasting events to clients
            recent_content: Shared content tracking dict for deduplication
            max_recent_content: Maximum recent content items to track per bot
        """
        self.active_bots = active_bots
        self.llm_semaphore = llm_semaphore
        self.event_broadcast = event_broadcast
        self.recent_content = recent_content if recent_content is not None else {}
        self.max_recent_content = max_recent_content
        self.is_running = False

    def set_running(self, running: bool):
        """Set the running state."""
        self.is_running = running

    # ========================================================================
    # CONTENT DEDUPLICATION
    # ========================================================================

    def _normalize_content(self, content: str) -> str:
        """Normalize content for comparison (lowercase, strip, remove extra spaces)."""
        return " ".join(content.lower().strip().split())

    def _content_similarity(self, content1: str, content2: str) -> float:
        """Calculate similarity between two content strings (0-1)."""
        norm1 = self._normalize_content(content1)
        norm2 = self._normalize_content(content2)

        # Exact match
        if norm1 == norm2:
            return 1.0

        # Check if one is substring of other
        if norm1 in norm2 or norm2 in norm1:
            return 0.9

        # Jaccard similarity on words
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        if not words1 or not words2:
            return 0.0
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union if union > 0 else 0.0

    def _is_duplicate_content(self, bot_id: UUID, new_content: str, threshold: float = 0.5) -> bool:
        """Check if content is too similar to recent content from this bot."""
        if bot_id not in self.recent_content:
            return False

        for old_content in self.recent_content[bot_id]:
            similarity = self._content_similarity(new_content, old_content)
            if similarity >= threshold:
                logger.debug(f"[DEDUP] Content similarity {similarity:.2f} >= {threshold}")
                return True
        return False

    def _get_variation_prompt(self, attempt: int) -> str:
        """Get variation prompts for regeneration attempts."""
        variations = [
            "",  # First attempt - normal
            "\n\nIMPORTANT: Your last attempt was too similar to recent posts. Try a COMPLETELY different topic or angle.",
            "\n\nIMPORTANT: Be MORE CREATIVE this time. Talk about something you haven't mentioned recently. Change your perspective.",
            "\n\nIMPORTANT: FINAL ATTEMPT - write about something totally unexpected. Surprise yourself. Be spontaneous.",
        ]
        return variations[min(attempt, len(variations) - 1)]

    def _track_content(self, bot_id: UUID, content: str):
        """Track content for deduplication."""
        if bot_id not in self.recent_content:
            self.recent_content[bot_id] = []

        self.recent_content[bot_id].append(content)

        # Keep only last N items
        if len(self.recent_content[bot_id]) > self.max_recent_content:
            self.recent_content[bot_id] = self.recent_content[bot_id][-self.max_recent_content:]

    def _get_recent_content_for_prompt(self, bot_id: UUID, limit: int = 5) -> str:
        """Get recent content from this bot to include in prompt to avoid repetition."""
        if bot_id not in self.recent_content or not self.recent_content[bot_id]:
            return ""

        recent = self.recent_content[bot_id][-limit:]
        return """## CRITICAL - DO NOT REPEAT
You MUST write something COMPLETELY DIFFERENT from these recent posts:
""" + "\n".join(f"- \"{c[:80]}\"" for c in recent) + """

Use DIFFERENT topics, DIFFERENT phrasing, DIFFERENT emotions."""

    # ========================================================================
    # EVENT BROADCASTING
    # ========================================================================

    async def _broadcast_event(self, event_type: str, data: dict):
        """Broadcast an event to connected clients."""
        if self.event_broadcast:
            await self.event_broadcast.put({
                "type": event_type,
                "data": data,
                "timestamp": datetime.utcnow().isoformat()
            })

    # ========================================================================
    # BOT MANAGEMENT HELPERS
    # ========================================================================

    def get_bot(self, bot_id: UUID) -> Optional["BotProfile"]:
        """Get a bot profile by ID."""
        return self.active_bots.get(bot_id)

    def get_all_bots(self) -> List["BotProfile"]:
        """Get all active bot profiles."""
        return list(self.active_bots.values())

    def get_random_bot(self) -> Optional["BotProfile"]:
        """Get a random active bot."""
        import random
        if not self.active_bots:
            return None
        return random.choice(list(self.active_bots.values()))

    # ========================================================================
    # ABSTRACT METHOD - Must be implemented by subclasses
    # ========================================================================

    @abstractmethod
    async def run(self):
        """Run the loop. Must be implemented by subclasses."""
        pass
