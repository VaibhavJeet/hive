"""
Hashtag API routes - Trending, Follow, Search.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from mind.hashtags.hashtag_service import (
    get_hashtag_service,
    TrendingHashtag,
    HashtagPost,
)


router = APIRouter(prefix="/hashtags", tags=["hashtags"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class TrendingHashtagResponse(BaseModel):
    tag: str
    post_count: int
    trend_direction: str
    recent_post_count: int


class HashtagPostAuthor(BaseModel):
    id: UUID
    display_name: str
    handle: str
    avatar_seed: str


class HashtagPostResponse(BaseModel):
    id: UUID
    author: HashtagPostAuthor
    community_id: UUID
    community_name: str
    content: str
    image_url: Optional[str]
    like_count: int
    comment_count: int
    created_at: datetime


class HashtagInfoResponse(BaseModel):
    tag: str
    post_count: int
    is_following: bool = False


class FollowedHashtagResponse(BaseModel):
    tag: str
    followed_at: str
    post_count: int


class SearchHashtagResponse(BaseModel):
    tag: str
    post_count: int


# ============================================================================
# TRENDING ENDPOINTS
# ============================================================================

@router.get("/trending", response_model=List[TrendingHashtagResponse])
async def get_trending_hashtags(
    limit: int = Query(default=10, le=50, description="Max number of trending hashtags"),
    hours: int = Query(default=24, le=168, description="Time window in hours")
):
    """
    Get trending hashtags based on recent usage.

    Returns hashtags sorted by popularity within the time window,
    including trend direction (up/down/stable).
    """
    service = get_hashtag_service()
    trending = await service.get_trending(limit=limit, hours=hours)

    return [
        TrendingHashtagResponse(
            tag=t.tag,
            post_count=t.post_count,
            trend_direction=t.trend_direction,
            recent_post_count=t.recent_post_count
        )
        for t in trending
    ]


# ============================================================================
# HASHTAG INFO & POSTS ENDPOINTS
# ============================================================================

@router.get("/{tag}", response_model=HashtagInfoResponse)
async def get_hashtag_info(
    tag: str,
    user_id: Optional[UUID] = Query(default=None, description="User ID to check if following")
):
    """
    Get information about a specific hashtag.

    Returns the hashtag, post count, and whether the user is following it.
    """
    service = get_hashtag_service()

    post_count = await service.get_hashtag_post_count(tag)

    is_following = False
    if user_id:
        is_following = await service.is_following_hashtag(user_id, tag)

    return HashtagInfoResponse(
        tag=tag.lower().strip('#'),
        post_count=post_count,
        is_following=is_following
    )


@router.get("/{tag}/posts", response_model=List[HashtagPostResponse])
async def get_hashtag_posts(
    tag: str,
    limit: int = Query(default=20, le=50),
    offset: int = Query(default=0, ge=0)
):
    """
    Get posts containing a specific hashtag.

    Returns posts in reverse chronological order (newest first).
    """
    service = get_hashtag_service()
    posts = await service.get_posts_by_hashtag(tag, limit=limit, offset=offset)

    return [
        HashtagPostResponse(
            id=p.id,
            author=HashtagPostAuthor(
                id=p.author_id,
                display_name=p.author_name,
                handle=p.author_handle,
                avatar_seed=p.author_avatar
            ),
            community_id=p.community_id,
            community_name=p.community_name,
            content=p.content,
            image_url=p.image_url,
            like_count=p.like_count,
            comment_count=p.comment_count,
            created_at=p.created_at
        )
        for p in posts
    ]


# ============================================================================
# FOLLOW/UNFOLLOW ENDPOINTS
# ============================================================================

@router.post("/{tag}/follow")
async def follow_hashtag(tag: str, user_id: UUID):
    """
    Follow a hashtag to receive notifications for new posts.

    Users will be notified when new posts are created with this hashtag.
    """
    service = get_hashtag_service()
    followed = await service.follow_hashtag(user_id, tag)

    if followed:
        return {"status": "followed", "tag": tag.lower().strip('#')}
    else:
        return {"status": "already_following", "tag": tag.lower().strip('#')}


@router.delete("/{tag}/follow")
async def unfollow_hashtag(tag: str, user_id: UUID):
    """
    Unfollow a hashtag.

    User will no longer receive notifications for this hashtag.
    """
    service = get_hashtag_service()
    unfollowed = await service.unfollow_hashtag(user_id, tag)

    if unfollowed:
        return {"status": "unfollowed", "tag": tag.lower().strip('#')}
    else:
        return {"status": "not_following", "tag": tag.lower().strip('#')}


@router.get("/following/list", response_model=List[FollowedHashtagResponse])
async def get_followed_hashtags(user_id: UUID):
    """
    Get all hashtags a user is following.

    Returns hashtags with follow date and post count.
    """
    service = get_hashtag_service()
    hashtags = await service.get_followed_hashtags(user_id)

    return [
        FollowedHashtagResponse(
            tag=h["tag"],
            followed_at=h["followed_at"],
            post_count=h["post_count"]
        )
        for h in hashtags
    ]


# ============================================================================
# SEARCH ENDPOINTS
# ============================================================================

@router.get("/search/query", response_model=List[SearchHashtagResponse])
async def search_hashtags(
    q: str = Query(..., min_length=1, max_length=50, description="Search query"),
    limit: int = Query(default=10, le=50)
):
    """
    Search for hashtags matching a query.

    Performs a partial match search and returns results sorted by popularity.
    """
    service = get_hashtag_service()
    results = await service.search_hashtags(q, limit=limit)

    return [
        SearchHashtagResponse(tag=r["tag"], post_count=r["post_count"])
        for r in results
    ]
