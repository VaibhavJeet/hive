"""
Search API routes - Full-text search for posts, users, and bots.
"""

from datetime import datetime
from typing import List, Optional, Literal
from uuid import UUID

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

from mind.search import (
    SearchService,
    SearchFilters,
    PostResult,
    UserResult,
    BotResult,
)


router = APIRouter(prefix="/search", tags=["search"])


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class PostSearchResult(BaseModel):
    """API response model for a post search result."""
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
    rank: float
    headline: str


class UserSearchResult(BaseModel):
    """API response model for a user search result."""
    id: UUID
    display_name: str
    avatar_seed: str
    created_at: datetime
    rank: float


class BotSearchResult(BaseModel):
    """API response model for a bot search result."""
    id: UUID
    display_name: str
    handle: str
    bio: str
    avatar_seed: str
    interests: List[str]
    is_ai_labeled: bool
    ai_label_text: str
    rank: float
    headline: str


class PostSearchResponse(BaseModel):
    """Paginated post search response."""
    posts: List[PostSearchResult]
    total: int
    limit: int
    offset: int
    query: str


class CombinedSearchResponse(BaseModel):
    """Combined search response across all entity types."""
    posts: List[PostSearchResult]
    users: List[UserSearchResult]
    bots: List[BotSearchResult]
    query: str
    total_posts: int
    total_users: int
    total_bots: int


class SuggestionsResponse(BaseModel):
    """Autocomplete suggestions response."""
    suggestions: List[str]
    query: str


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def post_result_to_response(result: PostResult) -> PostSearchResult:
    """Convert internal PostResult to API response."""
    return PostSearchResult(
        id=result.id,
        content=result.content,
        author_id=result.author_id,
        author_name=result.author_name,
        author_handle=result.author_handle,
        community_id=result.community_id,
        community_name=result.community_name,
        image_url=result.image_url,
        like_count=result.like_count,
        comment_count=result.comment_count,
        created_at=result.created_at,
        rank=result.rank,
        headline=result.headline,
    )


def user_result_to_response(result: UserResult) -> UserSearchResult:
    """Convert internal UserResult to API response."""
    return UserSearchResult(
        id=result.id,
        display_name=result.display_name,
        avatar_seed=result.avatar_seed,
        created_at=result.created_at,
        rank=result.rank,
    )


def bot_result_to_response(result: BotResult) -> BotSearchResult:
    """Convert internal BotResult to API response."""
    return BotSearchResult(
        id=result.id,
        display_name=result.display_name,
        handle=result.handle,
        bio=result.bio,
        avatar_seed=result.avatar_seed,
        interests=result.interests,
        is_ai_labeled=result.is_ai_labeled,
        ai_label_text=result.ai_label_text,
        rank=result.rank,
        headline=result.headline,
    )


# ============================================================================
# SEARCH ENDPOINTS
# ============================================================================

@router.get("", response_model=CombinedSearchResponse)
async def search_all(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    type: Literal["all", "posts", "users", "bots"] = Query(
        default="all",
        description="Type of entities to search"
    ),
    limit: int = Query(default=10, ge=1, le=50, description="Maximum results per type")
):
    """
    Search across posts, users, and bots.

    Returns combined results from all entity types, ranked by relevance.
    Use the `type` parameter to filter results to a specific entity type.
    """
    search_service = SearchService()

    if type == "posts":
        results = await search_service.search_posts(q, limit=limit)
        return CombinedSearchResponse(
            posts=[post_result_to_response(p) for p in results.posts],
            users=[],
            bots=[],
            query=q,
            total_posts=results.total,
            total_users=0,
            total_bots=0,
        )

    if type == "users":
        users = await search_service.search_users(q, limit=limit)
        return CombinedSearchResponse(
            posts=[],
            users=[user_result_to_response(u) for u in users],
            bots=[],
            query=q,
            total_posts=0,
            total_users=len(users),
            total_bots=0,
        )

    if type == "bots":
        bots = await search_service.search_bots(q, limit=limit)
        return CombinedSearchResponse(
            posts=[],
            users=[],
            bots=[bot_result_to_response(b) for b in bots],
            query=q,
            total_posts=0,
            total_users=0,
            total_bots=len(bots),
        )

    # type == "all"
    combined = await search_service.search_all(q, limit=limit)
    return CombinedSearchResponse(
        posts=[post_result_to_response(p) for p in combined.posts],
        users=[user_result_to_response(u) for u in combined.users],
        bots=[bot_result_to_response(b) for b in combined.bots],
        query=q,
        total_posts=combined.total_posts,
        total_users=combined.total_users,
        total_bots=combined.total_bots,
    )


@router.get("/posts", response_model=PostSearchResponse)
async def search_posts(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    community_id: Optional[UUID] = Query(default=None, description="Filter by community"),
    author_id: Optional[UUID] = Query(default=None, description="Filter by author"),
    date_from: Optional[datetime] = Query(default=None, description="Filter posts from this date"),
    date_to: Optional[datetime] = Query(default=None, description="Filter posts until this date"),
    has_media: Optional[bool] = Query(default=None, description="Filter by media presence"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum results"),
    offset: int = Query(default=0, ge=0, description="Results offset for pagination")
):
    """
    Search posts with filters.

    Supports filtering by community, author, date range, and media presence.
    Results are paginated and ranked by relevance.
    """
    search_service = SearchService()

    filters = SearchFilters(
        community_id=community_id,
        date_from=date_from,
        date_to=date_to,
        author_id=author_id,
        has_media=has_media,
    )

    results = await search_service.search_posts(
        query=q,
        filters=filters,
        limit=limit,
        offset=offset,
    )

    return PostSearchResponse(
        posts=[post_result_to_response(p) for p in results.posts],
        total=results.total,
        limit=results.limit,
        offset=results.offset,
        query=q,
    )


@router.get("/suggestions", response_model=SuggestionsResponse)
async def get_suggestions(
    q: str = Query(..., min_length=2, max_length=100, description="Partial search query"),
    limit: int = Query(default=10, ge=1, le=20, description="Maximum suggestions")
):
    """
    Get autocomplete suggestions based on partial query.

    Returns suggested search terms based on bot names, handles, and community names.
    Useful for implementing search autocomplete in the UI.
    """
    search_service = SearchService()

    suggestions = await search_service.get_suggestions(
        partial_query=q,
        limit=limit,
    )

    return SuggestionsResponse(
        suggestions=suggestions,
        query=q,
    )


@router.get("/users", response_model=List[UserSearchResult])
async def search_users(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    limit: int = Query(default=20, ge=1, le=50, description="Maximum results")
):
    """
    Search users by display name.

    Returns users matching the search query, ranked by relevance.
    """
    search_service = SearchService()
    users = await search_service.search_users(q, limit=limit)
    return [user_result_to_response(u) for u in users]


@router.get("/bots", response_model=List[BotSearchResult])
async def search_bots(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    limit: int = Query(default=20, ge=1, le=50, description="Maximum results")
):
    """
    Search bots by name, handle, bio, and interests.

    Returns bots matching the search query, ranked by relevance.
    Searches across multiple fields with different weights (name/handle highest).
    """
    search_service = SearchService()
    bots = await search_service.search_bots(q, limit=limit)
    return [bot_result_to_response(b) for b in bots]
