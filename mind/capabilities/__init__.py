"""
Advanced capabilities for Hive bots.

This module provides powerful features adapted from modern AI assistant architectures:

- **Web Search** - Search the web for information (wired: post_loop)
- **Image Generation** - Create images using AI (wired: post_loop)
- **Context Engine** - Conversation context, compaction, summarization
  (NOT yet wired — kept deliberately, see HIVE-046: long-running bots will exhaust
  the context window without it)

TTS, Skills, Hooks and Scheduling were removed in HIVE-042/043/044/045: all four were
unreachable, and the product has no audio surface, no skill invocation path, no hook
emissions, and an already-working scheduler in `mind/scheduler/`.
"""

from .context_engine import ContextEngine, ConversationContext
from .web_search import WebSearchProvider, search_web
from .image_gen import ImageGenerator, generate_image

__all__ = [
    # Context
    "ContextEngine",
    "ConversationContext",
    # Search
    "WebSearchProvider",
    "search_web",
    # Image
    "ImageGenerator",
    "generate_image",
]
