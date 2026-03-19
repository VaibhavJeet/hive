"""
Search service for full-text search across posts, users, and bots.
Uses PostgreSQL's built-in full-text search capabilities (tsvector, tsquery, ts_rank).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Any
from uuid import UUID

from sqlalchemy import select, text, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import (
    async_session_factory,
    PostDB,
    BotProfileDB,
    AppUserDB,
    CommunityDB,
)


@dataclass
class SearchFilters:
    """Filters for search queries."""
    community_id: Optional[UUID] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    author_id: Optional[UUID] = None
    has_media: Optional[bool] = None


@dataclass
class PostResult:
    """Search result for a post."""
    id: UUID
    content: str
    author_id: UUID
    author_name: str
    author_handle: str
    community_id: UUID
    community_name: str
    image_url: Optional[str]
    like_count: int
    comment_count: int
    created_at: datetime
    rank: float = 0.0
    headline: str = ""  # Highlighted search result


@dataclass
class UserResult:
    """Search result for a user."""
    id: UUID
    display_name: str
    avatar_seed: str
    created_at: datetime
    rank: float = 0.0


@dataclass
class BotResult:
    """Search result for a bot."""
    id: UUID
    display_name: str
    handle: str
    bio: str
    avatar_seed: str
    interests: List[str]
    is_ai_labeled: bool
    ai_label_text: str
    rank: float = 0.0
    headline: str = ""  # Highlighted search result


@dataclass
class SearchResults:
    """Paginated search results for posts."""
    posts: List[PostResult]
    total: int
    limit: int
    offset: int
    query: str


@dataclass
class CombinedResults:
    """Combined search results across all entity types."""
    posts: List[PostResult]
    users: List[UserResult]
    bots: List[BotResult]
    query: str
    total_posts: int = 0
    total_users: int = 0
    total_bots: int = 0


class SearchService:
    """
    Service for full-text search across posts, users, and bots.

    Uses PostgreSQL's full-text search features:
    - to_tsvector: Creates searchable document from text
    - to_tsquery: Parses search query with operators
    - ts_rank: Ranks results by relevance
    - ts_headline: Creates highlighted snippets
    """

    def __init__(self, session: Optional[AsyncSession] = None):
        """Initialize search service with optional session."""
        self._session = session

    async def _get_session(self) -> AsyncSession:
        """Get database session."""
        if self._session:
            return self._session
        return async_session_factory()

    def _prepare_query(self, query: str) -> str:
        """
        Prepare search query for PostgreSQL tsquery.
        Handles special characters and creates proper search terms.
        """
        # Remove special characters that could break tsquery
        cleaned = query.strip()
        if not cleaned:
            return ""

        # Split into words and join with & for AND search
        words = cleaned.split()
        # Add :* suffix for prefix matching (autocomplete-friendly)
        terms = [f"{word}:*" for word in words if word]
        return " & ".join(terms)

    async def search_posts(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        limit: int = 20,
        offset: int = 0
    ) -> SearchResults:
        """
        Search posts using full-text search.

        Args:
            query: Search query string
            filters: Optional filters (community_id, date_range, author_id, has_media)
            limit: Maximum results to return
            offset: Results offset for pagination

        Returns:
            SearchResults with matching posts and metadata
        """
        if not query.strip():
            return SearchResults(posts=[], total=0, limit=limit, offset=offset, query=query)

        prepared_query = self._prepare_query(query)
        if not prepared_query:
            return SearchResults(posts=[], total=0, limit=limit, offset=offset, query=query)

        filters = filters or SearchFilters()

        async with async_session_factory() as session:
            # Build the search query using PostgreSQL full-text search
            # First check if search_vector column exists, otherwise use to_tsvector on content
            search_sql = text("""
                WITH search_results AS (
                    SELECT
                        p.id,
                        p.content,
                        p.author_id,
                        b.display_name as author_name,
                        b.handle as author_handle,
                        p.community_id,
                        c.name as community_name,
                        p.image_url,
                        p.like_count,
                        p.comment_count,
                        p.created_at,
                        ts_rank(
                            COALESCE(p.search_vector, to_tsvector('english', p.content)),
                            to_tsquery('english', :query)
                        ) as rank,
                        ts_headline(
                            'english',
                            p.content,
                            to_tsquery('english', :query),
                            'MaxWords=50, MinWords=20, StartSel=<mark>, StopSel=</mark>'
                        ) as headline
                    FROM posts p
                    JOIN bot_profiles b ON p.author_id = b.id
                    JOIN communities c ON p.community_id = c.id
                    WHERE
                        p.is_deleted = false
                        AND (
                            COALESCE(p.search_vector, to_tsvector('english', p.content)) @@ to_tsquery('english', :query)
                        )
                        AND (:community_id::uuid IS NULL OR p.community_id = :community_id::uuid)
                        AND (:author_id::uuid IS NULL OR p.author_id = :author_id::uuid)
                        AND (:date_from::timestamp IS NULL OR p.created_at >= :date_from::timestamp)
                        AND (:date_to::timestamp IS NULL OR p.created_at <= :date_to::timestamp)
                        AND (:has_media::boolean IS NULL OR
                            (CASE WHEN :has_media::boolean THEN p.image_url IS NOT NULL
                                  ELSE p.image_url IS NULL END))
                )
                SELECT *, COUNT(*) OVER() as total_count
                FROM search_results
                ORDER BY rank DESC, created_at DESC
                LIMIT :limit OFFSET :offset
            """)

            result = await session.execute(
                search_sql,
                {
                    "query": prepared_query,
                    "community_id": str(filters.community_id) if filters.community_id else None,
                    "author_id": str(filters.author_id) if filters.author_id else None,
                    "date_from": filters.date_from,
                    "date_to": filters.date_to,
                    "has_media": filters.has_media,
                    "limit": limit,
                    "offset": offset,
                }
            )

            rows = result.fetchall()
            total = rows[0].total_count if rows else 0

            posts = [
                PostResult(
                    id=row.id,
                    content=row.content,
                    author_id=row.author_id,
                    author_name=row.author_name,
                    author_handle=row.author_handle,
                    community_id=row.community_id,
                    community_name=row.community_name,
                    image_url=row.image_url,
                    like_count=row.like_count,
                    comment_count=row.comment_count,
                    created_at=row.created_at,
                    rank=row.rank,
                    headline=row.headline,
                )
                for row in rows
            ]

            return SearchResults(
                posts=posts,
                total=total,
                limit=limit,
                offset=offset,
                query=query,
            )

    async def search_users(
        self,
        query: str,
        limit: int = 20
    ) -> List[UserResult]:
        """
        Search app users by display name.

        Args:
            query: Search query string
            limit: Maximum results to return

        Returns:
            List of matching users
        """
        if not query.strip():
            return []

        prepared_query = self._prepare_query(query)
        if not prepared_query:
            return []

        async with async_session_factory() as session:
            search_sql = text("""
                SELECT
                    id,
                    display_name,
                    avatar_seed,
                    created_at,
                    ts_rank(
                        to_tsvector('english', display_name),
                        to_tsquery('english', :query)
                    ) as rank
                FROM app_users
                WHERE
                    to_tsvector('english', display_name) @@ to_tsquery('english', :query)
                ORDER BY rank DESC, created_at DESC
                LIMIT :limit
            """)

            result = await session.execute(
                search_sql,
                {"query": prepared_query, "limit": limit}
            )

            rows = result.fetchall()

            return [
                UserResult(
                    id=row.id,
                    display_name=row.display_name,
                    avatar_seed=row.avatar_seed,
                    created_at=row.created_at,
                    rank=row.rank,
                )
                for row in rows
            ]

    async def search_bots(
        self,
        query: str,
        limit: int = 20
    ) -> List[BotResult]:
        """
        Search bots by name, handle, bio, and interests.

        Args:
            query: Search query string
            limit: Maximum results to return

        Returns:
            List of matching bots
        """
        if not query.strip():
            return []

        prepared_query = self._prepare_query(query)
        if not prepared_query:
            return []

        async with async_session_factory() as session:
            # Search across multiple fields with different weights
            search_sql = text("""
                SELECT
                    id,
                    display_name,
                    handle,
                    bio,
                    avatar_seed,
                    interests,
                    is_ai_labeled,
                    ai_label_text,
                    ts_rank(
                        COALESCE(
                            search_vector,
                            setweight(to_tsvector('english', display_name), 'A') ||
                            setweight(to_tsvector('english', handle), 'A') ||
                            setweight(to_tsvector('english', bio), 'B') ||
                            setweight(to_tsvector('english', COALESCE(array_to_string(interests::text[], ' '), '')), 'C')
                        ),
                        to_tsquery('english', :query)
                    ) as rank,
                    ts_headline(
                        'english',
                        bio,
                        to_tsquery('english', :query),
                        'MaxWords=30, MinWords=10, StartSel=<mark>, StopSel=</mark>'
                    ) as headline
                FROM bot_profiles
                WHERE
                    is_active = true
                    AND (
                        COALESCE(
                            search_vector,
                            setweight(to_tsvector('english', display_name), 'A') ||
                            setweight(to_tsvector('english', handle), 'A') ||
                            setweight(to_tsvector('english', bio), 'B') ||
                            setweight(to_tsvector('english', COALESCE(array_to_string(interests::text[], ' '), '')), 'C')
                        ) @@ to_tsquery('english', :query)
                    )
                ORDER BY rank DESC
                LIMIT :limit
            """)

            result = await session.execute(
                search_sql,
                {"query": prepared_query, "limit": limit}
            )

            rows = result.fetchall()

            return [
                BotResult(
                    id=row.id,
                    display_name=row.display_name,
                    handle=row.handle,
                    bio=row.bio,
                    avatar_seed=row.avatar_seed,
                    interests=row.interests if isinstance(row.interests, list) else [],
                    is_ai_labeled=row.is_ai_labeled,
                    ai_label_text=row.ai_label_text,
                    rank=row.rank,
                    headline=row.headline,
                )
                for row in rows
            ]

    async def search_all(
        self,
        query: str,
        limit: int = 10
    ) -> CombinedResults:
        """
        Search across all entity types (posts, users, bots).

        Args:
            query: Search query string
            limit: Maximum results per entity type

        Returns:
            CombinedResults with matches from all types
        """
        if not query.strip():
            return CombinedResults(
                posts=[],
                users=[],
                bots=[],
                query=query,
            )

        # Execute searches in parallel-ish (still sequential in asyncio but cleaner)
        post_results = await self.search_posts(query, limit=limit)
        users = await self.search_users(query, limit=limit)
        bots = await self.search_bots(query, limit=limit)

        return CombinedResults(
            posts=post_results.posts,
            users=users,
            bots=bots,
            query=query,
            total_posts=post_results.total,
            total_users=len(users),
            total_bots=len(bots),
        )

    async def get_suggestions(
        self,
        partial_query: str,
        limit: int = 10
    ) -> List[str]:
        """
        Get autocomplete suggestions based on partial query.
        Searches across bot names, handles, and common terms in posts.

        Args:
            partial_query: Partial search query for autocomplete
            limit: Maximum suggestions to return

        Returns:
            List of suggestion strings
        """
        if not partial_query.strip() or len(partial_query) < 2:
            return []

        async with async_session_factory() as session:
            # Get suggestions from bot names and handles
            suggestions_sql = text("""
                SELECT DISTINCT suggestion, rank FROM (
                    -- Bot display names
                    SELECT
                        display_name as suggestion,
                        1 as rank
                    FROM bot_profiles
                    WHERE
                        is_active = true
                        AND LOWER(display_name) LIKE LOWER(:pattern)

                    UNION

                    -- Bot handles
                    SELECT
                        handle as suggestion,
                        2 as rank
                    FROM bot_profiles
                    WHERE
                        is_active = true
                        AND LOWER(handle) LIKE LOWER(:pattern)

                    UNION

                    -- Community names
                    SELECT
                        name as suggestion,
                        3 as rank
                    FROM communities
                    WHERE
                        LOWER(name) LIKE LOWER(:pattern)
                ) suggestions
                ORDER BY rank, suggestion
                LIMIT :limit
            """)

            result = await session.execute(
                suggestions_sql,
                {"pattern": f"{partial_query}%", "limit": limit}
            )

            rows = result.fetchall()
            return [row.suggestion for row in rows]
