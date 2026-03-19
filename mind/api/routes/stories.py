"""
Stories API routes - Ephemeral content like Instagram/Snapchat stories.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
import html
import re

from mind.stories.story_service import get_story_service


router = APIRouter(prefix="/stories", tags=["stories"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class AuthorInfo(BaseModel):
    """Author information for a story."""
    id: UUID
    display_name: str
    handle: str
    avatar_seed: str
    is_bot: bool
    is_ai_labeled: bool
    ai_label_text: str


class StoryResponse(BaseModel):
    """Single story response."""
    id: UUID
    author: AuthorInfo
    content: str
    media_url: Optional[str]
    background_color: str
    font_style: str
    created_at: datetime
    expires_at: datetime
    is_viewed: bool = False
    view_count: int = 0
    is_expired: bool = False


class StoryListResponse(BaseModel):
    """List of stories response."""
    stories: List[StoryResponse]
    total: int
    has_more: bool


class StoryViewerInfo(BaseModel):
    """Viewer information."""
    id: UUID
    display_name: str
    handle: str
    avatar_seed: str
    is_bot: bool


class StoryViewerResponse(BaseModel):
    """Story viewer response."""
    viewer: StoryViewerInfo
    viewed_at: datetime


class ViewersListResponse(BaseModel):
    """List of story viewers."""
    viewers: List[StoryViewerResponse]
    total: int


def sanitize_content(content: str) -> str:
    """Sanitize user input to prevent XSS and injection attacks."""
    content = html.escape(content)
    content = re.sub(r'\s+', ' ', content).strip()
    return content


class CreateStoryRequest(BaseModel):
    """Request to create a new story."""
    content: str = Field(..., min_length=1, max_length=500, description="Story content")
    media_url: Optional[str] = Field(None, max_length=500)
    background_color: str = Field(default="#1a1a2e", max_length=20)
    font_style: str = Field(default="normal", max_length=30)
    expires_hours: int = Field(default=24, ge=1, le=48)

    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        v = sanitize_content(v)
        if len(v) < 1:
            raise ValueError('Content cannot be empty after sanitization')
        return v

    @field_validator('media_url')
    @classmethod
    def validate_media_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not v.startswith(('http://', 'https://')):
            raise ValueError('Media URL must start with http:// or https://')
        return v

    @field_validator('background_color')
    @classmethod
    def validate_background_color(cls, v: str) -> str:
        if not re.match(r'^#[0-9A-Fa-f]{6}$', v):
            raise ValueError('Background color must be a valid hex color (e.g., #1a1a2e)')
        return v

    @field_validator('font_style')
    @classmethod
    def validate_font_style(cls, v: str) -> str:
        valid_styles = ['normal', 'bold', 'italic', 'handwritten', 'typewriter']
        if v not in valid_styles:
            raise ValueError(f'Font style must be one of: {", ".join(valid_styles)}')
        return v


# ============================================================================
# STORY ENDPOINTS
# ============================================================================

@router.post("", response_model=StoryResponse)
async def create_story(
    request: CreateStoryRequest,
    author_id: UUID,
    author_is_bot: bool = False,
):
    """
    Create a new story.

    Stories expire after the specified hours (default 24).
    """
    story_service = await get_story_service()

    story = await story_service.create_story(
        author_id=author_id,
        content=request.content,
        media_url=request.media_url,
        background_color=request.background_color,
        font_style=request.font_style,
        expires_hours=request.expires_hours,
        author_is_bot=author_is_bot,
    )

    # Get author info
    story_data = await story_service.get_story_by_id(story.id)

    if not story_data:
        raise HTTPException(status_code=500, detail="Failed to create story")

    return StoryResponse(
        id=story_data["id"],
        author=AuthorInfo(**story_data["author"]),
        content=story_data["content"],
        media_url=story_data["media_url"],
        background_color=story_data["background_color"],
        font_style=story_data["font_style"],
        created_at=story_data["created_at"],
        expires_at=story_data["expires_at"],
        is_viewed=False,
        view_count=story_data["view_count"],
        is_expired=story_data["is_expired"],
    )


@router.get("", response_model=StoryListResponse)
async def get_stories(
    viewer_id: Optional[UUID] = None,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
):
    """
    Get active stories feed.

    Returns stories from all users/bots that haven't expired.
    If viewer_id is provided, includes viewed status.
    """
    story_service = await get_story_service()

    stories = await story_service.get_active_stories(
        viewer_id=viewer_id,
        limit=limit + 1,  # Get one extra to check has_more
        offset=offset,
    )

    has_more = len(stories) > limit
    stories = stories[:limit]

    story_responses = [
        StoryResponse(
            id=s["id"],
            author=AuthorInfo(**s["author"]),
            content=s["content"],
            media_url=s["media_url"],
            background_color=s["background_color"],
            font_style=s["font_style"],
            created_at=s["created_at"],
            expires_at=s["expires_at"],
            is_viewed=s.get("is_viewed", False),
            view_count=s["view_count"],
        )
        for s in stories
    ]

    return StoryListResponse(
        stories=story_responses,
        total=len(story_responses),
        has_more=has_more,
    )


@router.get("/{story_id}", response_model=StoryResponse)
async def get_story(story_id: UUID):
    """Get a single story by ID."""
    story_service = await get_story_service()

    story_data = await story_service.get_story_by_id(story_id)

    if not story_data:
        raise HTTPException(status_code=404, detail="Story not found")

    return StoryResponse(
        id=story_data["id"],
        author=AuthorInfo(**story_data["author"]),
        content=story_data["content"],
        media_url=story_data["media_url"],
        background_color=story_data["background_color"],
        font_style=story_data["font_style"],
        created_at=story_data["created_at"],
        expires_at=story_data["expires_at"],
        view_count=story_data["view_count"],
        is_expired=story_data["is_expired"],
    )


@router.get("/user/{user_id}", response_model=StoryListResponse)
async def get_user_stories(
    user_id: UUID,
    include_expired: bool = Query(default=False),
):
    """
    Get all stories from a specific user/bot.

    Can optionally include expired stories.
    """
    story_service = await get_story_service()

    stories = await story_service.get_user_stories(
        author_id=user_id,
        include_expired=include_expired,
    )

    # For user stories, we need to get author info once
    if stories:
        first_story = await story_service.get_story_by_id(stories[0]["id"])
        author_info = first_story["author"] if first_story else None
    else:
        author_info = None

    story_responses = []
    for s in stories:
        if author_info:
            story_responses.append(
                StoryResponse(
                    id=s["id"],
                    author=AuthorInfo(**author_info),
                    content=s["content"],
                    media_url=s["media_url"],
                    background_color=s["background_color"],
                    font_style=s["font_style"],
                    created_at=s["created_at"],
                    expires_at=s["expires_at"],
                    view_count=s["view_count"],
                    is_expired=s.get("is_expired", False),
                )
            )

    return StoryListResponse(
        stories=story_responses,
        total=len(story_responses),
        has_more=False,
    )


@router.get("/{story_id}/viewers", response_model=ViewersListResponse)
async def get_story_viewers(
    story_id: UUID,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
):
    """
    Get list of users who viewed a story.

    Only the story author should typically have access to this.
    """
    story_service = await get_story_service()

    # Verify story exists
    story = await story_service.get_story_by_id(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    viewers = await story_service.get_viewers(
        story_id=story_id,
        limit=limit,
        offset=offset,
    )

    viewer_responses = [
        StoryViewerResponse(
            viewer=StoryViewerInfo(
                id=v["viewer"]["id"],
                display_name=v["viewer"]["display_name"],
                handle=v["viewer"]["handle"],
                avatar_seed=v["viewer"]["avatar_seed"],
                is_bot=v["viewer"]["is_bot"],
            ),
            viewed_at=v["viewed_at"],
        )
        for v in viewers
    ]

    return ViewersListResponse(
        viewers=viewer_responses,
        total=len(viewer_responses),
    )


@router.post("/{story_id}/view")
async def mark_story_viewed(
    story_id: UUID,
    viewer_id: UUID,
    viewer_is_bot: bool = False,
):
    """
    Mark a story as viewed by a user.

    Creates a view record if not already viewed.
    """
    story_service = await get_story_service()

    # Verify story exists
    story = await story_service.get_story_by_id(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    recorded = await story_service.record_view(
        story_id=story_id,
        viewer_id=viewer_id,
        viewer_is_bot=viewer_is_bot,
    )

    return {
        "status": "recorded" if recorded else "already_viewed",
        "story_id": str(story_id),
        "viewer_id": str(viewer_id),
    }


@router.delete("/{story_id}")
async def delete_story(
    story_id: UUID,
    author_id: UUID,
):
    """
    Delete a story.

    Only the story author can delete their own story.
    """
    story_service = await get_story_service()

    deleted = await story_service.delete_story(
        story_id=story_id,
        author_id=author_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Story not found or you don't have permission to delete it"
        )

    return {
        "status": "deleted",
        "story_id": str(story_id),
    }
