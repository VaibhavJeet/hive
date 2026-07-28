"""
Media API routes - Upload, retrieve, delete media files.
"""

from datetime import datetime, timedelta

from mind.core.time import utcnow
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, select

from mind.api.dependencies import CurrentUser
from mind.media.validation import (
    UploadTooLarge,
    content_type_matches,
    read_upload_within_limit,
    sniff_content_type,
)
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

# ============================================================================
# UPLOAD QUOTAS (HIVE-011)
# ============================================================================
#
# Authenticated does not mean unlimited: one account could previously fill the disk
# or the object-storage bill one 10 MB image at a time. These are deliberately
# generous — the goal is to bound abuse, not to ration normal use.

MAX_UPLOADS_PER_DAY = 100
MAX_UPLOAD_BYTES_PER_DAY = 500 * 1024 * 1024  # 500 MB


async def _enforce_upload_quota(uploader_id: UUID) -> None:
    """Reject the request if the caller is over their rolling 24-hour quota."""
    since = utcnow() - timedelta(hours=24)

    async with async_session_factory() as session:
        stmt = select(
            func.count(MediaDB.id), func.coalesce(func.sum(MediaDB.size_bytes), 0)
        ).where(
            MediaDB.uploader_id == uploader_id,
            MediaDB.created_at >= since,
            MediaDB.is_deleted == False,
        )
        result = await session.execute(stmt)
        count, total_bytes = result.one()

    if count >= MAX_UPLOADS_PER_DAY:
        raise HTTPException(
            status_code=429,
            detail=f"Upload limit reached ({MAX_UPLOADS_PER_DAY} files per 24 hours)",
        )

    if total_bytes >= MAX_UPLOAD_BYTES_PER_DAY:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Upload size limit reached "
                f"({MAX_UPLOAD_BYTES_PER_DAY // (1024 * 1024)} MB per 24 hours)"
            ),
        )


@router.post("/upload", response_model=MediaUploadResponse)
async def upload_media(
    current_user: CurrentUser,
    file: UploadFile = File(...),
):
    """
    Upload a media file (image or video).

    The uploader is the signed-in caller. `is_bot` was removed with the caller-supplied
    `uploader_id` (HIVE-003) — bots write media through the engine, not this endpoint.

    Supports:
    - Images: JPEG, PNG, GIF, WebP (max 10MB by default)
    - Videos: MP4, WebM, MOV (max 100MB by default)

    Returns the media info including URLs for the original and thumbnail.
    """
    content_type = file.content_type or "application/octet-stream"

    # HIVE-011: enforce the daily quota before reading a byte, so a caller who is
    # already over their limit cannot make us buffer the body to find out.
    await _enforce_upload_quota(current_user.id)

    # HIVE-029: the size cap is applied while streaming. It used to be checked with
    # len(content) *after* the whole body had been read into memory, so it protected
    # disk but not RAM.
    limit_mb = (
        settings.MAX_VIDEO_SIZE_MB
        if content_type.startswith("video/")
        else settings.MAX_IMAGE_SIZE_MB
    )
    try:
        content = await read_upload_within_limit(file, int(limit_mb * 1024 * 1024))
    except UploadTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc))

    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    # HIVE-029: the declared content type is client-supplied and is not evidence.
    # Sniff the leading bytes and require them to agree, or we will happily store
    # arbitrary content and serve it back from our own origin under a MIME type of
    # the uploader's choosing.
    sniffed = sniff_content_type(content[:32])
    if not content_type_matches(content_type, sniffed):
        raise HTTPException(
            status_code=415,
            detail=(
                f"File content does not match the declared type '{content_type}'"
                + (f" (looks like '{sniffed}')" if sniffed else "")
            ),
        )

    # Get storage and processor
    storage = get_media_storage()

    try:
        # Validate and upload file
        upload_result = await storage.upload_file(
            content=content,
            original_filename=file.filename or "unnamed",
            content_type=content_type,
            uploader_id=current_user.id,
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
            uploader_id=current_user.id,
            uploader_is_bot=False,
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
async def delete_media(media_id: UUID, current_user: CurrentUser):
    """
    Delete a media file.

    Only the uploader can delete their own media (soft delete). Ownership is checked
    against the bearer token, not a caller-supplied id.
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
        if media.uploader_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="You can only delete your own media"
            )

        # Soft delete in database
        media.is_deleted = True
        media.deleted_at = utcnow()

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


def _resolve_within_storage(root: Path, *parts: str) -> Path:
    """Join `parts` under `root` and refuse anything that escapes the target directory.

    HIVE-028: `filename` arrives as a path parameter. Starlette matches path segments
    on the raw URL but hands the handler the **decoded** value, so `%2e%2e%2f` reaches
    this function as `../`. Joining it straight onto the storage root walked out of the
    media directory and served arbitrary files.

    Containment is enforced against the *type* directory (e.g. `<root>/images`), not
    merely against `root`. Containing only to `root` would still let
    `images/../videos/x.mp4` sidestep the `file_type` allowlist — inside storage, but
    not the directory the caller asked for.
    """
    if not parts:
        raise HTTPException(status_code=400, detail="Invalid path")

    # Every component must be a plain name. A filename is never a path.
    for part in parts:
        if not part or part in (".", "..") or "/" in part or "\\" in part:
            raise HTTPException(status_code=400, detail="Invalid path")

    root = root.resolve()
    base = root.joinpath(*parts[:-1])
    candidate = base.joinpath(parts[-1])

    try:
        resolved_base = base.resolve()
        resolved = candidate.resolve()
    except (OSError, RuntimeError):
        raise HTTPException(status_code=400, detail="Invalid path")

    if resolved_base != root and root not in resolved_base.parents:
        raise HTTPException(status_code=400, detail="Invalid path")
    if resolved.parent != resolved_base:
        raise HTTPException(status_code=400, detail="Invalid path")

    return resolved

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
    file_path = _resolve_within_storage(storage.storage_path, file_type, filename)

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
    file_path = _resolve_within_storage(
        storage.storage_path, file_type, "thumbnails", filename
    )

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
