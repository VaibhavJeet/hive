"""
Object storage providers for Hive media storage.

Supports multiple backends:
- local: Local filesystem (default, free)
- minio: MinIO S3-compatible storage (free, self-hosted)
- seaweedfs: SeaweedFS distributed storage (free, self-hosted)
- garage: Garage S3-compatible storage (free, self-hosted)
- s3: AWS S3 (paid, cloud)

All S3-compatible providers (minio, seaweedfs, garage, s3) use the same
S3StorageProvider class with different endpoint configurations.
"""

import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, BinaryIO
from uuid import UUID, uuid4

import aiofiles
import aiofiles.os

from mind.config.settings import settings

logger = logging.getLogger(__name__)


class StorageProvider(str, Enum):
    """Supported storage providers."""
    LOCAL = "local"
    MINIO = "minio"
    SEAWEEDFS = "seaweedfs"
    GARAGE = "garage"
    S3 = "s3"


class StorageResult:
    """Result of a storage operation."""

    def __init__(
        self,
        success: bool,
        media_id: Optional[UUID] = None,
        filename: Optional[str] = None,
        url: Optional[str] = None,
        size_bytes: Optional[int] = None,
        content_type: Optional[str] = None,
        error: Optional[str] = None,
    ):
        self.success = success
        self.media_id = media_id
        self.filename = filename
        self.url = url
        self.size_bytes = size_bytes
        self.content_type = content_type
        self.error = error

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "media_id": str(self.media_id) if self.media_id else None,
            "filename": self.filename,
            "url": self.url,
            "size_bytes": self.size_bytes,
            "content_type": self.content_type,
            "error": self.error,
        }


class BaseStorageProvider(ABC):
    """Abstract base class for storage providers."""

    def __init__(self):
        self.provider_name = "base"

    @abstractmethod
    async def upload(
        self,
        content: bytes,
        filename: str,
        content_type: str,
        folder: str = "uploads",
    ) -> StorageResult:
        """Upload a file to storage."""
        pass

    @abstractmethod
    async def delete(self, url: str) -> bool:
        """Delete a file from storage."""
        pass

    @abstractmethod
    async def exists(self, url: str) -> bool:
        """Check if a file exists."""
        pass

    @abstractmethod
    def get_url(self, filename: str, folder: str = "uploads") -> str:
        """Get the URL for a stored file."""
        pass

    def _generate_filename(self, original_name: str, content: bytes) -> str:
        """Generate a unique filename based on content hash and timestamp."""
        ext = Path(original_name).suffix.lower()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        content_hash = hashlib.sha256(content).hexdigest()[:16]
        unique_id = str(uuid4())[:8]
        return f"{timestamp}_{content_hash}_{unique_id}{ext}"

    def _get_folder_for_type(self, content_type: str) -> str:
        """Determine folder based on content type."""
        if content_type.startswith("image/"):
            return "images"
        elif content_type.startswith("video/"):
            return "videos"
        elif content_type.startswith("audio/"):
            return "audio"
        return "uploads"


class LocalStorageProvider(BaseStorageProvider):
    """Local filesystem storage provider."""

    def __init__(self, base_path: Optional[str] = None):
        super().__init__()
        self.provider_name = "local"
        self.base_path = Path(base_path or settings.MEDIA_STORAGE_PATH)
        self._ensure_directories()

    def _ensure_directories(self):
        """Create storage directories if they don't exist."""
        directories = [
            self.base_path,
            self.base_path / "images",
            self.base_path / "images" / "thumbnails",
            self.base_path / "videos",
            self.base_path / "videos" / "thumbnails",
            self.base_path / "audio",
            self.base_path / "uploads",
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    async def upload(
        self,
        content: bytes,
        filename: str,
        content_type: str,
        folder: Optional[str] = None,
    ) -> StorageResult:
        """Upload a file to local filesystem."""
        try:
            if folder is None:
                folder = self._get_folder_for_type(content_type)

            # Generate unique filename
            unique_filename = self._generate_filename(filename, content)
            media_id = uuid4()

            # Ensure folder exists
            folder_path = self.base_path / folder
            folder_path.mkdir(parents=True, exist_ok=True)

            # Write file
            file_path = folder_path / unique_filename
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(content)

            # Generate URL
            url = self.get_url(unique_filename, folder)

            logger.debug(f"Uploaded file to local storage: {file_path}")

            return StorageResult(
                success=True,
                media_id=media_id,
                filename=unique_filename,
                url=url,
                size_bytes=len(content),
                content_type=content_type,
            )

        except Exception as e:
            logger.error(f"Failed to upload to local storage: {e}")
            return StorageResult(success=False, error=str(e))

    async def delete(self, url: str) -> bool:
        """Delete a file from local filesystem."""
        try:
            # Extract path from URL
            # URL format: /media/files/{folder}/{filename}
            parts = url.split("/")
            if len(parts) < 4:
                return False

            folder = parts[-2]
            filename = parts[-1]
            file_path = self.base_path / folder / filename

            if await aiofiles.os.path.exists(file_path):
                await aiofiles.os.remove(file_path)

                # Try to delete thumbnail if exists
                thumb_path = self.base_path / folder / "thumbnails" / f"thumb_{filename}"
                if await aiofiles.os.path.exists(thumb_path):
                    await aiofiles.os.remove(thumb_path)

                logger.debug(f"Deleted file from local storage: {file_path}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to delete from local storage: {e}")
            return False

    async def exists(self, url: str) -> bool:
        """Check if a file exists in local filesystem."""
        try:
            parts = url.split("/")
            if len(parts) < 4:
                return False

            folder = parts[-2]
            filename = parts[-1]
            file_path = self.base_path / folder / filename

            return await aiofiles.os.path.exists(file_path)

        except Exception:
            return False

    def get_url(self, filename: str, folder: str = "uploads") -> str:
        """Get the URL for a stored file."""
        return f"/media/files/{folder}/{filename}"


class S3StorageProvider(BaseStorageProvider):
    """
    S3-compatible storage provider.

    Works with:
    - AWS S3
    - MinIO
    - SeaweedFS S3 Gateway
    - Garage
    - Any S3-compatible service
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket: Optional[str] = None,
        region: Optional[str] = None,
        use_ssl: bool = True,
        public_url: Optional[str] = None,
        provider_name: str = "s3",
    ):
        super().__init__()
        self.provider_name = provider_name
        self.endpoint = endpoint or settings.STORAGE_ENDPOINT
        self.access_key = access_key or settings.STORAGE_ACCESS_KEY
        self.secret_key = secret_key or settings.STORAGE_SECRET_KEY
        self.bucket = bucket or settings.STORAGE_BUCKET
        self.region = region or settings.STORAGE_REGION
        self.use_ssl = use_ssl if use_ssl is not None else settings.STORAGE_USE_SSL
        self.public_url = public_url or settings.STORAGE_PUBLIC_URL

        self._client = None
        self._initialized = False

    async def _get_client(self):
        """Get or create the S3 client."""
        if self._client is not None:
            return self._client

        try:
            # Try to import aioboto3 for async S3 operations
            import aioboto3

            session = aioboto3.Session()
            client_config = {
                "service_name": "s3",
                "aws_access_key_id": self.access_key,
                "aws_secret_access_key": self.secret_key,
                "region_name": self.region,
            }

            if self.endpoint:
                client_config["endpoint_url"] = self.endpoint

            self._client = session.client(**client_config)
            self._initialized = True

            logger.info(f"Initialized {self.provider_name} storage client")
            return self._client

        except ImportError:
            logger.warning(
                "aioboto3 not installed. Install with: pip install aioboto3 "
                "to enable S3-compatible storage."
            )
            raise ImportError(
                "aioboto3 is required for S3-compatible storage. "
                "Install with: pip install aioboto3"
            )

    async def _ensure_bucket(self):
        """Ensure the bucket exists."""
        try:
            async with await self._get_client() as client:
                try:
                    await client.head_bucket(Bucket=self.bucket)
                except Exception:
                    # Bucket doesn't exist, create it
                    await client.create_bucket(
                        Bucket=self.bucket,
                        CreateBucketConfiguration={"LocationConstraint": self.region}
                        if self.region != "us-east-1"
                        else {},
                    )
                    logger.info(f"Created bucket: {self.bucket}")
        except Exception as e:
            logger.error(f"Failed to ensure bucket exists: {e}")
            raise

    async def upload(
        self,
        content: bytes,
        filename: str,
        content_type: str,
        folder: Optional[str] = None,
    ) -> StorageResult:
        """Upload a file to S3-compatible storage."""
        try:
            if folder is None:
                folder = self._get_folder_for_type(content_type)

            # Generate unique filename
            unique_filename = self._generate_filename(filename, content)
            media_id = uuid4()

            # S3 key (path in bucket)
            key = f"{folder}/{unique_filename}"

            async with await self._get_client() as client:
                await client.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=content,
                    ContentType=content_type,
                )

            # Generate URL
            url = self.get_url(unique_filename, folder)

            logger.debug(f"Uploaded file to {self.provider_name}: {key}")

            return StorageResult(
                success=True,
                media_id=media_id,
                filename=unique_filename,
                url=url,
                size_bytes=len(content),
                content_type=content_type,
            )

        except ImportError as e:
            return StorageResult(success=False, error=str(e))
        except Exception as e:
            logger.error(f"Failed to upload to {self.provider_name}: {e}")
            return StorageResult(success=False, error=str(e))

    async def delete(self, url: str) -> bool:
        """Delete a file from S3-compatible storage."""
        try:
            # Extract key from URL
            key = self._url_to_key(url)
            if not key:
                return False

            async with await self._get_client() as client:
                await client.delete_object(Bucket=self.bucket, Key=key)

            logger.debug(f"Deleted file from {self.provider_name}: {key}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete from {self.provider_name}: {e}")
            return False

    async def exists(self, url: str) -> bool:
        """Check if a file exists in S3-compatible storage."""
        try:
            key = self._url_to_key(url)
            if not key:
                return False

            async with await self._get_client() as client:
                await client.head_object(Bucket=self.bucket, Key=key)
                return True

        except Exception:
            return False

    def get_url(self, filename: str, folder: str = "uploads") -> str:
        """Get the URL for a stored file."""
        if self.public_url:
            # Use configured public URL (CDN, etc.)
            return f"{self.public_url.rstrip('/')}/{folder}/{filename}"

        if self.endpoint:
            # Use endpoint URL for S3-compatible services
            protocol = "https" if self.use_ssl else "http"
            endpoint = self.endpoint.replace("https://", "").replace("http://", "")
            return f"{protocol}://{endpoint}/{self.bucket}/{folder}/{filename}"

        # Default AWS S3 URL format
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{folder}/{filename}"

    def _url_to_key(self, url: str) -> Optional[str]:
        """Extract S3 key from URL."""
        try:
            # Try to extract folder/filename from URL
            if self.bucket in url:
                # URL contains bucket name
                parts = url.split(self.bucket + "/")
                if len(parts) > 1:
                    return parts[-1]

            # Try simple path extraction
            parts = url.rstrip("/").split("/")
            if len(parts) >= 2:
                return f"{parts[-2]}/{parts[-1]}"

            return None
        except Exception:
            return None


# ============================================================================
# PROVIDER FACTORY
# ============================================================================

_storage_provider: Optional[BaseStorageProvider] = None


def get_storage_provider() -> BaseStorageProvider:
    """
    Get the configured storage provider.

    Returns the appropriate provider based on settings.STORAGE_PROVIDER:
    - local: LocalStorageProvider (default, free)
    - minio: S3StorageProvider with MinIO endpoint
    - seaweedfs: S3StorageProvider with SeaweedFS endpoint
    - garage: S3StorageProvider with Garage endpoint
    - s3: S3StorageProvider with AWS S3
    """
    global _storage_provider

    if _storage_provider is not None:
        return _storage_provider

    provider_type = settings.STORAGE_PROVIDER.lower()

    if provider_type == "local":
        _storage_provider = LocalStorageProvider()
        logger.info("Using local filesystem storage")

    elif provider_type in ("minio", "seaweedfs", "garage", "s3"):
        # All S3-compatible providers use the same class
        if not settings.STORAGE_ENDPOINT and provider_type != "s3":
            logger.warning(
                f"STORAGE_ENDPOINT not set for {provider_type}. "
                f"Using local storage as fallback."
            )
            _storage_provider = LocalStorageProvider()
        else:
            _storage_provider = S3StorageProvider(provider_name=provider_type)
            logger.info(f"Using {provider_type} storage")

    else:
        logger.warning(
            f"Unknown storage provider: {provider_type}. "
            f"Falling back to local storage."
        )
        _storage_provider = LocalStorageProvider()

    return _storage_provider


def reset_storage_provider():
    """Reset the storage provider singleton (for testing)."""
    global _storage_provider
    _storage_provider = None


# ============================================================================
# DEFAULT PROVIDER CONFIGURATIONS
# ============================================================================

DEFAULT_PROVIDER_CONFIGS = {
    "local": {
        "description": "Local filesystem storage (default)",
        "requires_endpoint": False,
        "requires_credentials": False,
        "free": True,
        "self_hosted": True,
    },
    "minio": {
        "description": "MinIO S3-compatible object storage",
        "requires_endpoint": True,
        "requires_credentials": True,
        "default_endpoint": "http://localhost:9000",
        "free": True,
        "self_hosted": True,
        "install_docs": "https://min.io/docs/minio/container/index.html",
    },
    "seaweedfs": {
        "description": "SeaweedFS distributed storage with S3 gateway",
        "requires_endpoint": True,
        "requires_credentials": True,
        "default_endpoint": "http://localhost:8333",
        "free": True,
        "self_hosted": True,
        "install_docs": "https://github.com/seaweedfs/seaweedfs",
    },
    "garage": {
        "description": "Garage lightweight S3-compatible storage",
        "requires_endpoint": True,
        "requires_credentials": True,
        "default_endpoint": "http://localhost:3900",
        "free": True,
        "self_hosted": True,
        "install_docs": "https://garagehq.deuxfleurs.fr/documentation/quick-start/",
    },
    "s3": {
        "description": "AWS S3 cloud storage",
        "requires_endpoint": False,
        "requires_credentials": True,
        "free": False,
        "self_hosted": False,
        "docs": "https://aws.amazon.com/s3/",
    },
}
