"""
Media storage service for file uploads.

This module provides a unified interface for media storage operations,
using configurable storage providers (local, MinIO, SeaweedFS, Garage, S3).

Configuration via environment variables:
- STORAGE_PROVIDER: local, minio, seaweedfs, garage, s3 (default: local)
- STORAGE_ENDPOINT: Endpoint URL for S3-compatible services
- STORAGE_ACCESS_KEY: Access key for authentication
- STORAGE_SECRET_KEY: Secret key for authentication
- STORAGE_BUCKET: Bucket/container name (default: hive-media)
"""

import logging
from typing import Optional, List
from uuid import UUID

from mind.config.settings import settings
from mind.media.providers import (
    BaseStorageProvider,
    StorageResult,
    StorageProvider,
    get_storage_provider,
    reset_storage_provider,
    DEFAULT_PROVIDER_CONFIGS,
)

logger = logging.getLogger(__name__)


class MediaStorageError(Exception):
    """Base exception for media storage errors."""
    pass


class FileTooLargeError(MediaStorageError):
    """File exceeds maximum allowed size."""
    pass


class InvalidFileTypeError(MediaStorageError):
    """File type is not allowed."""
    pass


class FileNotFoundError(MediaStorageError):
    """Media file not found."""
    pass


class MediaStorage:
    """
    Unified media storage service.

    Provides a consistent interface for file operations across
    different storage backends (local, S3, MinIO, etc.).

    Usage:
        storage = MediaStorage()
        result = await storage.upload_file(content, filename, content_type)
        if result["success"]:
            print(f"Uploaded to: {result['url']}")
    """

    def __init__(self, provider: Optional[BaseStorageProvider] = None):
        """
        Initialize media storage.

        Args:
            provider: Optional storage provider. If not specified,
                     uses the configured provider from settings.
        """
        self._provider = provider or get_storage_provider()

    @property
    def provider_name(self) -> str:
        """Get the name of the current storage provider."""
        return self._provider.provider_name

    def validate_file(
        self,
        content: bytes,
        content_type: str,
        max_size_mb: Optional[float] = None,
        allowed_types: Optional[List[str]] = None
    ) -> dict:
        """
        Validate a file before upload.

        Args:
            content: File content as bytes
            content_type: MIME type of the file
            max_size_mb: Maximum file size in MB (uses settings default if None)
            allowed_types: List of allowed MIME types (uses settings default if None)

        Returns:
            dict with validation results

        Raises:
            FileTooLargeError: If file exceeds size limit
            InvalidFileTypeError: If file type is not allowed
        """
        # Determine file category
        is_image = content_type.startswith("image/")
        is_video = content_type.startswith("video/")
        is_audio = content_type.startswith("audio/")

        if not is_image and not is_video and not is_audio:
            raise InvalidFileTypeError(
                f"Content type '{content_type}' is not supported. "
                "Must be image, video, or audio."
            )

        # Get size limits
        if max_size_mb is None:
            if is_image:
                max_size_mb = settings.MAX_IMAGE_SIZE_MB
            elif is_video:
                max_size_mb = settings.MAX_VIDEO_SIZE_MB
            else:
                max_size_mb = settings.MAX_IMAGE_SIZE_MB  # Use image limit for audio

        # Get allowed types
        if allowed_types is None:
            if is_image:
                allowed_types = settings.ALLOWED_IMAGE_TYPES
            elif is_video:
                allowed_types = settings.ALLOWED_VIDEO_TYPES
            else:
                allowed_types = ["audio/mpeg", "audio/wav", "audio/ogg", "audio/webm"]

        # Check size
        size_mb = len(content) / (1024 * 1024)
        if size_mb > max_size_mb:
            raise FileTooLargeError(
                f"File size {size_mb:.2f}MB exceeds maximum allowed {max_size_mb}MB"
            )

        # Check type
        if content_type not in allowed_types:
            raise InvalidFileTypeError(
                f"File type '{content_type}' is not allowed. "
                f"Allowed types: {', '.join(allowed_types)}"
            )

        return {
            "valid": True,
            "size_bytes": len(content),
            "size_mb": size_mb,
            "content_type": content_type,
            "is_image": is_image,
            "is_video": is_video,
            "is_audio": is_audio,
        }

    async def upload_file(
        self,
        content: bytes,
        original_filename: str,
        content_type: str,
        uploader_id: Optional[UUID] = None,
        folder: Optional[str] = None,
    ) -> dict:
        """
        Upload a file to storage.

        Args:
            content: File content as bytes
            original_filename: Original name of the file
            content_type: MIME type of the file
            uploader_id: ID of the user uploading the file
            folder: Optional folder/prefix for organization

        Returns:
            dict with upload results including media_id and urls
        """
        # Validate first
        validation = self.validate_file(content, content_type)

        # Upload using provider
        result = await self._provider.upload(
            content=content,
            filename=original_filename,
            content_type=content_type,
            folder=folder,
        )

        if not result.success:
            raise MediaStorageError(f"Upload failed: {result.error}")

        return {
            "success": True,
            "media_id": result.media_id,
            "filename": result.filename,
            "original_filename": original_filename,
            "file_type": "image" if validation["is_image"] else (
                "video" if validation["is_video"] else "audio"
            ),
            "content_type": content_type,
            "size_bytes": validation["size_bytes"],
            "media_url": result.url,
            "provider": self.provider_name,
        }

    async def delete_file(self, media_url: str) -> bool:
        """
        Delete a file from storage.

        Args:
            media_url: URL of the media file to delete

        Returns:
            True if deleted, False if not found
        """
        return await self._provider.delete(media_url)

    async def file_exists(self, media_url: str) -> bool:
        """Check if a media file exists."""
        return await self._provider.exists(media_url)

    def get_file_url(self, filename: str, folder: str = "uploads") -> str:
        """
        Get the URL for a media file.

        Args:
            filename: Name of the file
            folder: Folder containing the file

        Returns:
            URL to access the media file
        """
        return self._provider.get_url(filename, folder)

    @staticmethod
    def get_provider_info() -> dict:
        """Get information about available storage providers."""
        current_provider = settings.STORAGE_PROVIDER.lower()
        return {
            "current_provider": current_provider,
            "available_providers": DEFAULT_PROVIDER_CONFIGS,
            "is_configured": (
                current_provider == "local" or
                (settings.STORAGE_ENDPOINT is not None and
                 settings.STORAGE_ACCESS_KEY is not None)
            ),
        }


# ============================================================================
# SINGLETON ACCESS
# ============================================================================

_media_storage: Optional[MediaStorage] = None


def get_media_storage() -> MediaStorage:
    """Get the global media storage instance."""
    global _media_storage
    if _media_storage is None:
        _media_storage = MediaStorage()
        logger.info(f"Initialized media storage with provider: {_media_storage.provider_name}")
    return _media_storage


def reset_media_storage():
    """Reset the media storage singleton (for testing)."""
    global _media_storage
    _media_storage = None
    reset_storage_provider()
