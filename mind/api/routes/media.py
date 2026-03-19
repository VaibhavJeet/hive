"""
Media API routes - Upload, retrieve, delete media files.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select

from mind.core.database import async_session_factory, MediaDB
from mind.media.storage import (
    get_media_storage,
    MediaStorageError,
    FileTooLargeError,
    InvalidFileTypeError,
)
from mind.media.processor import get_media_processor, MediaProcessingError
from mind.config.settings import settings


router = APIRouter(prefix="/media", tags=["media"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class MediaResponse(BaseModel):
    """Response model for media info."""
    id: UUID
    file_type: str
    content_type: str
    original_filename: str
    original_url: str
    thumbnail_url: Optional[str]
    width: Optional[int]
    height: Optional[int]
    duration_seconds: Optional[float]
    size_bytes: int
    created_at: datetime


class MediaUploadResponse(BaseModel):
    """Response model for upload result."""
    id: UUID
    file_type: str
    original_url: str
    thumbnail_url: Optional[str]
    width: Optional[int]
    height: Optional[int]
    size_bytes: int


class MediaDeleteResponse(BaseModel):
    """Response model for delete result."""
    id: UUID
    deleted: bool
    message: str


# ============================================================================
# MEDIA ENDPOINTS
# ============================================================================

@router.post("/upload", response_model=MediaUploadResponse)
async def upload_media(
    file: UploadFile = File(...),
    uploader_id: UUID = Query(..., description="ID of the user or bot uploading"),
    is_bot: bool = Query(False, description="Whether uploader is a bot"),
):
    """
    Upload a media file (image or video).

    Supports:
    - Images: JPEG, PNG, GIF, WebP (max 10MB by default)
    - Videos: MP4, WebM, MOV (max 100MB by default)

    Returns the media info including URLs for the original and thumbnail.
    """
    # Read file content
    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    # Get content type
    content_type = file.content_type or "application/octet-stream"

    # Get storage and processor
    storage = get_media_storage()

    try:
        # Validate and upload file
        upload_result = await storage.upload_file(
            content=content,
            original_filename=file.filename or "unnamed",
            content_type=content_type,
            uploader_id=uploader_id,
        )
    except FileTooLargeError as e:
        raise HTTPException(status_code=413, detail=str(e))
    except InvalidFileTypeError as e:
        raise HTTPException(status_code=415, detail=str(e))
    except MediaStorageError as e:
        raise HTTPException(status_code=500, detail=f"Storage error: {str(e)}")

    # Process media for dimensions and thumbnail
    width = None
    height = None
    thumbnail_url = None
    duration_seconds = None

    if upload_result["file_type"] == "image":
        try:
            processor = get_media_processor()
            processed = processor.process_image(content, generate_thumbnail=True)
            width = processed.width
            height = processed.height

            # Save thumbnail if generated
            if processed.thumbnail_data:
                thumb_filename = f"thumb_{upload_result['filename']}"
                thumb_path = storage.storage_path / "images" / "thumbnails" / thumb_filename

                import aiofiles
                async with aiofiles.open(thumb_path, "wb") as f:
                    await f.write(processed.thumbnail_data)

                thumbnail_url = f"/media/files/images/thumbnails/{thumb_filename}"
        except MediaProcessingError as e:
            # Log but don't fail - we still have the original file
            pass
    else:
        # Video processing (placeholder - would extract dimensions and thumbnail)
        try:
            processor = get_media_processor()
            processed = processor.process_video(content)
            width = processed.width if processed.width > 0 else None
            height = processed.height if processed.height > 0 else None
            duration_seconds = processed.duration_seconds if processed.duration_seconds > 0 else None
        except MediaProcessingError:
            pass

    # Save to database
    async with async_session_factory() as session:
        media = MediaDB(
            id=upload_result["media_id"],
            uploader_id=uploader_id,
            uploader_is_bot=is_bot,
            file_type=upload_result["file_type"],
            content_type=content_type,
            original_filename=upload_result["original_filename"],
            stored_filename=upload_result["filename"],
            original_url=upload_result["media_url"],
            thumbnail_url=thumbnail_url,
            width=width,
            height=height,
            duration_seconds=duration_seconds,
            size_bytes=upload_result["size_bytes"],
        )
        session.add(media)
        await session.commit()
        await session.refresh(media)

        return MediaUploadResponse(
            id=media.id,
            file_type=media.file_type,
            original_url=media.original_url,
            thumbnail_url=media.thumbnail_url,
            width=media.width,
            height=media.height,
            size_bytes=media.size_bytes,
        )


@router.get("/{media_id}", response_model=MediaResponse)
async def get_media(media_id: UUID):
    """Get information about a media file."""
    async with async_session_factory() as session:
        stmt = select(MediaDB).where(
            MediaDB.id == media_id,
            MediaDB.is_deleted == False
        )
        result = await session.execute(stmt)
        media = result.scalar_one_or_none()

        if not media:
            raise HTTPException(status_code=404, detail="Media not found")

        return MediaResponse(
            id=media.id,
            file_type=media.file_type,
            content_type=media.content_type,
            original_filename=media.original_filename,
            original_url=media.original_url,
            thumbnail_url=media.thumbnail_url,
            width=media.width,
            height=media.height,
            duration_seconds=media.duration_seconds,
            size_bytes=media.size_bytes,
            created_at=media.created_at,
        )


@router.delete("/{media_id}", response_model=MediaDeleteResponse)
async def delete_media(
    media_id: UUID,
    requester_id: UUID = Query(..., description="ID of the user requesting deletion"),
):
    """
    Delete a media file.

    Only the uploader can delete their own media (soft delete).
    """
    async with async_session_factory() as session:
        stmt = select(MediaDB).where(
            MediaDB.id == media_id,
            MediaDB.is_deleted == False
        )
        result = await session.execute(stmt)
        media = result.scalar_one_or_none()

        if not media:
            raise HTTPException(status_code=404, detail="Media not found")

        # Check ownership (only uploader can delete)
        if media.uploader_id != requester_id:
            raise HTTPException(
                status_code=403,
                detail="You can only delete your own media"
            )

        # Soft delete in database
        media.is_deleted = True
        media.deleted_at = datetime.utcnow()

        # Optionally delete from storage (uncomment for hard delete)
        # storage = get_media_storage()
        # await storage.delete_file(media.original_url)
        # if media.thumbnail_url:
        #     await storage.delete_file(media.thumbnail_url)

        await session.commit()

        return MediaDeleteResponse(
            id=media_id,
            deleted=True,
            message="Media deleted successfully"
        )


# ============================================================================
# FILE SERVING ENDPOINTS
# ============================================================================

@router.get("/files/{file_type}/{filename}")
async def serve_media_file(file_type: str, filename: str):
    """
    Serve a media file.

    This endpoint serves the actual file content.
    In production, consider using a CDN or nginx for static file serving.
    """
    if file_type not in ["images", "videos"]:
        raise HTTPException(status_code=400, detail="Invalid file type")

    storage = get_media_storage()
    file_path = storage.storage_path / file_type / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # Determine media type
    suffix = file_path.suffix.lower()
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
    }
    media_type = media_types.get(suffix, "application/octet-stream")

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename,
    )


@router.get("/files/{file_type}/thumbnails/{filename}")
async def serve_thumbnail(file_type: str, filename: str):
    """
    Serve a thumbnail file.
    """
    if file_type not in ["images", "videos"]:
        raise HTTPException(status_code=400, detail="Invalid file type")

    storage = get_media_storage()
    file_path = storage.storage_path / file_type / "thumbnails" / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")

    # Thumbnails are typically JPEG
    suffix = file_path.suffix.lower()
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    media_type = media_types.get(suffix, "image/jpeg")

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename,
    )
