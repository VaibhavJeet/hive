"""
Full-text search module for AI Community Companions.
Provides search capabilities for posts, users, and bots using PostgreSQL full-text search.
"""

from mind.search.search_service import (
    SearchService,
    SearchResults,
    PostResult,
    UserResult,
    BotResult,
    CombinedResults,
    SearchFilters,
)
from mind.search.indexer import SearchIndexer

__all__ = [
    "SearchService",
    "SearchIndexer",
    "SearchResults",
    "PostResult",
    "UserResult",
    "BotResult",
    "CombinedResults",
    "SearchFilters",
]
