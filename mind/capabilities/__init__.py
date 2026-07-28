"""
Advanced capabilities for Hive bots.

This module provides powerful features adapted from modern AI assistant architectures:

- **Context Engine** - Manage conversation context, compaction, summarization
- **Web Search** - Search the web for information
- **Image Generation** - Create images using AI
- **Text-to-Speech** - Give bots unique voices
- **Skills** - Modular, pluggable capabilities
- **Hooks** - Event-driven extensibility
- **Scheduling** - Cron-like task scheduling
"""

from .context_engine import ContextEngine, ConversationContext
from .web_search import WebSearchProvider, search_web
from .image_gen import ImageGenerator, generate_image
from .tts import TTSProvider, synthesize_speech
from .skills import Skill, SkillRegistry
from .hooks import HookManager, Hook
from .scheduler import TaskScheduler, ScheduledTask

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
    # TTS
    "TTSProvider",
    "synthesize_speech",
    # Skills
    "Skill",
    "SkillRegistry",
    # Hooks
    "HookManager",
    "Hook",
    # Scheduling
    "TaskScheduler",
    "ScheduledTask",
]
