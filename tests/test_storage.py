"""
Tests for media storage providers.

Tests the configurable object storage system:
- Local filesystem storage
- S3-compatible storage interface
- Provider factory
"""

import pytest
from uuid import UUID
from unittest.mock import patch, MagicMock, AsyncMock

from mind.media.providers import (
    StorageProvider,
    StorageResult,
    LocalStorageProvider,
    S3StorageProvider,
    get_storage_provider,
    reset_storage_provider,
    DEFAULT_PROVIDER_CONFIGS,
)
from mind.media.storage import (
    MediaStorage,
    get_media_storage,
    reset_media_storage,
    MediaStorageError,
    FileTooLargeError,
    InvalidFileTypeError,
)


class TestStorageResult:
    """Test StorageResult data class."""

    def test_success_result(self):
        """Test creating a successful storage result."""
        result = StorageResult(
            success=True,
            media_id=UUID("12345678-1234-5678-1234-567812345678"),
            filename="test.jpg",
            url="/media/files/images/test.jpg",
            size_bytes=1024,
            content_type="image/jpeg",
        )

        assert result.success is True
        assert result.filename == "test.jpg"
        assert result.error is None

    def test_failure_result(self):
        """Test creating a failed storage result."""
        result = StorageResult(
            success=False,
            error="Upload failed: connection timeout",
        )

        assert result.success is False
        assert result.error == "Upload failed: connection timeout"

    def test_to_dict(self):
        """Test converting result to dict."""
        result = StorageResult(
            success=True,
            filename="test.jpg",
            url="/media/files/images/test.jpg",
        )

        data = result.to_dict()
        assert data["success"] is True
        assert data["filename"] == "test.jpg"


class TestStorageProviderEnum:
    """Test StorageProvider enum."""

    def test_local_provider(self):
        """Test local provider value."""
        assert StorageProvider.LOCAL.value == "local"

    def test_minio_provider(self):
        """Test MinIO provider value."""
        assert StorageProvider.MINIO.value == "minio"

    def test_seaweedfs_provider(self):
        """Test SeaweedFS provider value."""
        assert StorageProvider.SEAWEEDFS.value == "seaweedfs"

    def test_garage_provider(self):
        """Test Garage provider value."""
        assert StorageProvider.GARAGE.value == "garage"

    def test_s3_provider(self):
        """Test S3 provider value."""
        assert StorageProvider.S3.value == "s3"


class TestLocalStorageProvider:
    """Test LocalStorageProvider."""

    @pytest.fixture
    def local_provider(self, tmp_path):
        """Create a local storage provider with temp directory."""
        return LocalStorageProvider(base_path=str(tmp_path))

    def test_initialization(self, local_provider):
        """Test provider initialization."""
        assert local_provider.provider_name == "local"

    def test_directories_created(self, local_provider, tmp_path):
        """Test that required directories are created."""
        assert (tmp_path / "images").exists()
        assert (tmp_path / "videos").exists()
        assert (tmp_path / "uploads").exists()

    @pytest.mark.asyncio
    async def test_upload_image(self, local_provider):
        """Test uploading an image file."""
        content = b"fake image content"
        result = await local_provider.upload(
            content=content,
            filename="test.jpg",
            content_type="image/jpeg",
        )

        assert result.success is True
        assert result.filename is not None
        assert result.url is not None
        assert "images" in result.url
        assert result.size_bytes == len(content)

    @pytest.mark.asyncio
    async def test_upload_video(self, local_provider):
        """Test uploading a video file."""
        content = b"fake video content"
        result = await local_provider.upload(
            content=content,
            filename="test.mp4",
            content_type="video/mp4",
        )

        assert result.success is True
        assert "videos" in result.url

    @pytest.mark.asyncio
    async def test_file_exists(self, local_provider):
        """Test checking if file exists."""
        # Upload a file first
        result = await local_provider.upload(
            content=b"test content",
            filename="exists.txt",
            content_type="image/jpeg",
        )

        assert await local_provider.exists(result.url) is True
        assert await local_provider.exists("/nonexistent/file.jpg") is False

    @pytest.mark.asyncio
    async def test_delete_file(self, local_provider):
        """Test deleting a file."""
        # Upload first
        result = await local_provider.upload(
            content=b"delete me",
            filename="delete.jpg",
            content_type="image/jpeg",
        )

        # Delete
        deleted = await local_provider.delete(result.url)
        assert deleted is True

        # Verify deleted
        assert await local_provider.exists(result.url) is False

    def test_get_url(self, local_provider):
        """Test URL generation."""
        url = local_provider.get_url("test.jpg", "images")
        assert url == "/media/files/images/test.jpg"


class TestS3StorageProvider:
    """Test S3StorageProvider."""

    def test_initialization(self):
        """Test S3 provider initialization."""
        provider = S3StorageProvider(
            endpoint="http://localhost:9000",
            access_key="test-key",
            secret_key="test-secret",
            bucket="test-bucket",
            provider_name="minio",
        )

        assert provider.provider_name == "minio"
        assert provider.bucket == "test-bucket"

    def test_url_generation_with_public_url(self):
        """Test URL generation with public URL configured."""
        provider = S3StorageProvider(
            public_url="https://cdn.example.com",
            bucket="test",
        )

        url = provider.get_url("test.jpg", "images")
        assert url == "https://cdn.example.com/images/test.jpg"

    def test_url_generation_with_endpoint(self):
        """Test URL generation with endpoint."""
        provider = S3StorageProvider(
            endpoint="http://minio.local:9000",
            bucket="media",
            use_ssl=False,
        )

        url = provider.get_url("file.jpg", "uploads")
        assert "minio.local:9000" in url
        assert "media" in url


class TestMediaStorage:
    """Test MediaStorage unified interface."""

    @pytest.fixture
    def storage(self, tmp_path):
        """Create a media storage with local provider."""
        reset_media_storage()
        provider = LocalStorageProvider(base_path=str(tmp_path))
        return MediaStorage(provider=provider)

    def test_validate_image(self, storage):
        """Test image validation."""
        content = b"x" * 1000  # 1KB
        result = storage.validate_file(content, "image/jpeg")

        assert result["valid"] is True
        assert result["is_image"] is True
        assert result["is_video"] is False

    def test_validate_video(self, storage):
        """Test video validation."""
        content = b"x" * 1000
        result = storage.validate_file(content, "video/mp4")

        assert result["valid"] is True
        assert result["is_video"] is True

    def test_validate_invalid_type(self, storage):
        """Test validation of unsupported type."""
        content = b"x" * 1000

        with pytest.raises(InvalidFileTypeError):
            storage.validate_file(content, "application/pdf")

    def test_validate_file_too_large(self, storage):
        """Test validation of oversized file."""
        # Create content larger than max size
        content = b"x" * (15 * 1024 * 1024)  # 15MB

        with pytest.raises(FileTooLargeError):
            storage.validate_file(
                content,
                "image/jpeg",
                max_size_mb=10.0,
            )

    @pytest.mark.asyncio
    async def test_upload_file(self, storage):
        """Test file upload through unified interface."""
        result = await storage.upload_file(
            content=b"test image data",
            original_filename="photo.jpg",
            content_type="image/jpeg",
        )

        assert result["success"] is True
        assert result["media_id"] is not None
        assert result["media_url"] is not None
        assert result["provider"] == "local"

    @pytest.mark.asyncio
    async def test_delete_file(self, storage):
        """Test file deletion."""
        # Upload first
        result = await storage.upload_file(
            content=b"delete me",
            original_filename="temp.jpg",
            content_type="image/jpeg",
        )

        # Delete
        deleted = await storage.delete_file(result["media_url"])
        assert deleted is True

    def test_get_provider_info(self):
        """Test getting provider configuration info."""
        info = MediaStorage.get_provider_info()

        assert "current_provider" in info
        assert "available_providers" in info
        assert "local" in info["available_providers"]
        assert "minio" in info["available_providers"]
        assert "seaweedfs" in info["available_providers"]


class TestProviderFactory:
    """Test the provider factory function."""

    def test_default_provider_is_local(self):
        """Test that default provider is local."""
        reset_storage_provider()

        with patch("mind.media.providers.settings") as mock_settings:
            mock_settings.STORAGE_PROVIDER = "local"
            mock_settings.MEDIA_STORAGE_PATH = "./test_media"

            provider = get_storage_provider()
            assert provider.provider_name == "local"

    def test_unknown_provider_fallback(self):
        """Test that unknown provider falls back to local."""
        reset_storage_provider()

        with patch("mind.media.providers.settings") as mock_settings:
            mock_settings.STORAGE_PROVIDER = "unknown_provider"
            mock_settings.MEDIA_STORAGE_PATH = "./test_media"

            provider = get_storage_provider()
            assert provider.provider_name == "local"


class TestDefaultProviderConfigs:
    """Test default provider configuration metadata."""

    def test_local_config(self):
        """Test local provider config."""
        config = DEFAULT_PROVIDER_CONFIGS["local"]

        assert config["free"] is True
        assert config["self_hosted"] is True
        assert config["requires_credentials"] is False

    def test_minio_config(self):
        """Test MinIO provider config."""
        config = DEFAULT_PROVIDER_CONFIGS["minio"]

        assert config["free"] is True
        assert config["self_hosted"] is True
        assert config["requires_endpoint"] is True
        assert "install_docs" in config

    def test_s3_config(self):
        """Test S3 provider config."""
        config = DEFAULT_PROVIDER_CONFIGS["s3"]

        assert config["free"] is False
        assert config["self_hosted"] is False
