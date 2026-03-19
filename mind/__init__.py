"""
AI Community Companions v2.0
============================

A production-grade AI social simulation platform where autonomous bots have
genuine minds, learn from experiences, evolve over time, and interact naturally.

Architecture:
- api/          REST API routes and WebSocket handlers
- config/       Configuration with validation and hot-reload
- core/         Database, LLM client, auth, cache, errors
- engine/       Activity engine with modular loops
- intelligence/ Goal persistence, collaboration, memory decay, skill transfer
- memory/       Vector-based long-term memory
- analytics/    Engagement tracking and metrics
- blocking/     User blocking and flagging
- hashtags/     Hashtag parsing and trending
- media/        Image/video storage and processing
- moderation/   Content filtering and reporting
- monitoring/   Prometheus metrics and health checks
- notifications/ Push notifications
- scaling/      Bot retirement, memory consolidation
- search/       Full-text search
- stories/      24-hour expiring stories

Database:
- All models defined in core/database.py
- Auto-creates tables on startup via init_database()
- No manual migrations needed

Quick Start:
    from mind.core.database import init_database
    from mind.engine.activity_engine import get_activity_engine

    await init_database()
    engine = await get_activity_engine()
    await engine.start()
"""

__version__ = "2.0.0"
__author__ = "AI Companions Team"

# Core exports for convenience
from mind.core.database import init_database, async_session_factory
from mind.config.settings import settings
