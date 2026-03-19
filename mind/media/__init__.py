"""
Media module for image/video upload, storage, and processing.

Supports configurable storage backends:
- local: Local filesystem (default, free)
- minio: MinIO S3-compatible storage (free, self-hosted)
- seaweedfs: SeaweedFS distributed storage (free, self-hosted)
- garage: Garage S3-compatible storage (free, self-hosted)
- s3: AWS S3 (paid, cloud)
"""

from mind.media.storage import MediaStorage, get_media_storage, reset_media_storage
from mind.media.providers import (
    StorageProvider,
    StorageResult,
    BaseStorageProvider,
    LocalStorageProvider,
    S3StorageProvider,
    get_storage_provider,
    reset_storage_provider,
    DEFAULT_PROVIDER_CONFIGS,
)
from mind.media.processor import (
    MediaProcessor,
    ProcessedImage,
    ProcessedVideo,
    VideoValidationResult,
    MediaProcessingError,
    VideoProcessingError,
    get_media_processor,
)

__all__ = [
    # Storage
    "MediaStorage",
    "get_media_storage",
    "reset_media_storage",
    # Providers
    "StorageProvider",
    "StorageResult",
    "BaseStorageProvider",
    "LocalStorageProvider",
    "S3StorageProvider",
    "get_storage_provider",
    "reset_storage_provider",
    "DEFAULT_PROVIDER_CONFIGS",
    # Processing
    "MediaProcessor",
    "ProcessedImage",
    "ProcessedVideo",
    "VideoValidationResult",
    "MediaProcessingError",
    "VideoProcessingError",
    "get_media_processor",
]
