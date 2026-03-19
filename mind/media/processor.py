"""
Media processing service for images and videos.
Handles resizing, thumbnail generation, and metadata extraction.
"""

import io
import os
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, BinaryIO, List
from uuid import UUID

try:
    from PIL import Image, ImageOps
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    Image = None
    ImageOps = None

try:
    from moviepy.editor import VideoFileClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    VideoFileClip = None

# Configure logger
logger = logging.getLogger(__name__)


@dataclass
class ProcessedImage:
    """Result of image processing."""
    width: int
    height: int
    format: str
    size_bytes: int
    thumbnail_data: Optional[bytes] = None
    thumbnail_width: Optional[int] = None
    thumbnail_height: Optional[int] = None
    resized_data: Optional[bytes] = None


@dataclass
class ProcessedVideo:
    """Result of video processing."""
    width: int
    height: int
    duration_seconds: float
    format: str
    size_bytes: int
    thumbnail_data: Optional[bytes] = None
    thumbnail_width: Optional[int] = None
    thumbnail_height: Optional[int] = None


@dataclass
class VideoValidationResult:
    """Result of video validation."""
    is_valid: bool
    error_message: Optional[str] = None
    format: Optional[str] = None
    size_bytes: Optional[int] = None
    duration_seconds: Optional[float] = None


class MediaProcessingError(Exception):
    """Error during media processing."""
    pass


class VideoProcessingError(MediaProcessingError):
    """Error during video processing."""
    pass


class MediaProcessor:
    """
    Processes uploaded media files.
    - Image: resize, thumbnail generation, format conversion
    - Video: thumbnail extraction, duration, compression, validation
    """

    # Default thumbnail dimensions
    DEFAULT_THUMB_SIZE = (200, 200)

    # Default max dimensions for resizing
    DEFAULT_MAX_WIDTH = 1920
    DEFAULT_MAX_HEIGHT = 1080

    # Default video settings
    DEFAULT_MAX_VIDEO_SIZE_MB = 100
    DEFAULT_MAX_VIDEO_DURATION_SECONDS = 300
    DEFAULT_VIDEO_FORMATS = ["mp4", "mov", "webm"]

    def __init__(
        self,
        max_video_size_mb: Optional[int] = None,
        max_video_duration_seconds: Optional[int] = None,
        allowed_video_formats: Optional[List[str]] = None,
    ):
        """
        Initialize MediaProcessor.

        Args:
            max_video_size_mb: Maximum video file size in MB
            max_video_duration_seconds: Maximum video duration in seconds
            allowed_video_formats: List of allowed video formats (e.g., ['mp4', 'mov', 'webm'])
        """
        if not PILLOW_AVAILABLE:
            raise ImportError(
                "Pillow is required for image processing. "
                "Install with: pip install Pillow"
            )

        # Video configuration from parameters or environment
        self.max_video_size_mb = max_video_size_mb or int(
            os.getenv("AIC_MAX_VIDEO_SIZE_MB", self.DEFAULT_MAX_VIDEO_SIZE_MB)
        )
        self.max_video_duration_seconds = max_video_duration_seconds or int(
            os.getenv("AIC_MAX_VIDEO_DURATION_SECONDS", self.DEFAULT_MAX_VIDEO_DURATION_SECONDS)
        )

        if allowed_video_formats:
            self.allowed_video_formats = [fmt.lower() for fmt in allowed_video_formats]
        else:
            formats_env = os.getenv("AIC_VIDEO_FORMATS", "mp4,mov,webm")
            self.allowed_video_formats = [fmt.strip().lower() for fmt in formats_env.split(",")]

        logger.info(
            f"MediaProcessor initialized: max_video_size={self.max_video_size_mb}MB, "
            f"max_duration={self.max_video_duration_seconds}s, formats={self.allowed_video_formats}"
        )

    def process_image(
        self,
        content: bytes,
        generate_thumbnail: bool = True,
        max_width: Optional[int] = None,
        max_height: Optional[int] = None,
    ) -> ProcessedImage:
        """
        Process an uploaded image.

        Args:
            content: Image file content as bytes
            generate_thumbnail: Whether to generate a thumbnail
            max_width: Maximum width for resizing (None = no resize)
            max_height: Maximum height for resizing (None = no resize)

        Returns:
            ProcessedImage with dimensions and optional thumbnail
        """
        try:
            # Open image
            img = Image.open(io.BytesIO(content))

            # Auto-rotate based on EXIF
            img = ImageOps.exif_transpose(img)

            # Get original dimensions
            original_width, original_height = img.size
            img_format = img.format or "JPEG"

            result = ProcessedImage(
                width=original_width,
                height=original_height,
                format=img_format,
                size_bytes=len(content),
            )

            # Generate thumbnail
            if generate_thumbnail:
                thumb = self._create_thumbnail(img, self.DEFAULT_THUMB_SIZE)
                thumb_bytes = self._image_to_bytes(thumb, img_format)
                result.thumbnail_data = thumb_bytes
                result.thumbnail_width, result.thumbnail_height = thumb.size

            # Resize if needed
            if max_width or max_height:
                max_w = max_width or self.DEFAULT_MAX_WIDTH
                max_h = max_height or self.DEFAULT_MAX_HEIGHT

                if original_width > max_w or original_height > max_h:
                    resized = self._resize_image(img, max_w, max_h)
                    result.resized_data = self._image_to_bytes(resized, img_format)
                    result.width, result.height = resized.size

            return result

        except Exception as e:
            logger.error(f"Failed to process image: {e}")
            raise MediaProcessingError(f"Failed to process image: {str(e)}")

    def resize_image(
        self,
        content: bytes,
        max_width: int,
        max_height: int,
        maintain_aspect: bool = True,
    ) -> bytes:
        """
        Resize an image to fit within specified dimensions.

        Args:
            content: Image file content as bytes
            max_width: Maximum width
            max_height: Maximum height
            maintain_aspect: Whether to maintain aspect ratio

        Returns:
            Resized image as bytes
        """
        try:
            img = Image.open(io.BytesIO(content))
            img = ImageOps.exif_transpose(img)
            img_format = img.format or "JPEG"

            if maintain_aspect:
                resized = self._resize_image(img, max_width, max_height)
            else:
                resized = img.resize((max_width, max_height), Image.Resampling.LANCZOS)

            return self._image_to_bytes(resized, img_format)

        except Exception as e:
            logger.error(f"Failed to resize image: {e}")
            raise MediaProcessingError(f"Failed to resize image: {str(e)}")

    def generate_thumbnail(
        self,
        content: bytes,
        size: Tuple[int, int] = None,
    ) -> bytes:
        """
        Generate a thumbnail from an image.

        Args:
            content: Image file content as bytes
            size: Thumbnail dimensions (width, height)

        Returns:
            Thumbnail image as bytes
        """
        size = size or self.DEFAULT_THUMB_SIZE

        try:
            img = Image.open(io.BytesIO(content))
            img = ImageOps.exif_transpose(img)
            img_format = img.format or "JPEG"

            thumb = self._create_thumbnail(img, size)
            return self._image_to_bytes(thumb, img_format)

        except Exception as e:
            logger.error(f"Failed to generate thumbnail: {e}")
            raise MediaProcessingError(f"Failed to generate thumbnail: {str(e)}")

    def _create_thumbnail(self, img: "Image.Image", size: Tuple[int, int]) -> "Image.Image":
        """Create a thumbnail that fits within size while maintaining aspect ratio."""
        thumb = img.copy()
        thumb.thumbnail(size, Image.Resampling.LANCZOS)
        return thumb

    def _resize_image(
        self,
        img: "Image.Image",
        max_width: int,
        max_height: int,
    ) -> "Image.Image":
        """Resize image to fit within max dimensions while maintaining aspect ratio."""
        width, height = img.size

        # Calculate scaling factor
        width_ratio = max_width / width
        height_ratio = max_height / height
        ratio = min(width_ratio, height_ratio)

        # Only resize if image is larger
        if ratio < 1:
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            return img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        return img

    def _image_to_bytes(self, img: "Image.Image", format: str) -> bytes:
        """Convert PIL Image to bytes."""
        buffer = io.BytesIO()

        # Convert RGBA to RGB for JPEG
        if format.upper() == "JPEG" and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Save with quality settings
        save_kwargs = {}
        if format.upper() == "JPEG":
            save_kwargs["quality"] = 85
            save_kwargs["optimize"] = True
        elif format.upper() == "PNG":
            save_kwargs["optimize"] = True
        elif format.upper() == "WEBP":
            save_kwargs["quality"] = 85

        img.save(buffer, format=format, **save_kwargs)
        return buffer.getvalue()

    def get_image_dimensions(self, content: bytes) -> Tuple[int, int]:
        """Get image dimensions without full processing."""
        try:
            img = Image.open(io.BytesIO(content))
            img = ImageOps.exif_transpose(img)
            return img.size
        except Exception as e:
            logger.error(f"Failed to get image dimensions: {e}")
            raise MediaProcessingError(f"Failed to get image dimensions: {str(e)}")

    # ========================================================================
    # VIDEO PROCESSING
    # ========================================================================

    def _check_moviepy_available(self) -> None:
        """Check if moviepy is available and raise an error if not."""
        if not MOVIEPY_AVAILABLE:
            raise VideoProcessingError(
                "moviepy is required for video processing. "
                "Install with: pip install moviepy"
            )

    def _get_video_extension(self, video_path: str) -> str:
        """Get the video file extension in lowercase."""
        return Path(video_path).suffix.lower().lstrip(".")

    def extract_video_thumbnail(
        self,
        video_path: str,
        time_offset: float = 1.0,
        size: Tuple[int, int] = None,
    ) -> bytes:
        """
        Extract a thumbnail frame from a video file.

        Args:
            video_path: Path to the video file
            time_offset: Time in seconds to extract frame from (default: 1.0s)
            size: Thumbnail dimensions (width, height), defaults to DEFAULT_THUMB_SIZE

        Returns:
            Thumbnail image as JPEG bytes

        Raises:
            VideoProcessingError: If extraction fails
        """
        self._check_moviepy_available()
        size = size or self.DEFAULT_THUMB_SIZE
        clip = None

        try:
            logger.debug(f"Extracting thumbnail from video: {video_path}")
            clip = VideoFileClip(video_path)

            # Ensure time_offset is within video duration
            if time_offset >= clip.duration:
                time_offset = min(1.0, clip.duration / 2)
                logger.debug(f"Adjusted time_offset to {time_offset}s (video duration: {clip.duration}s)")

            # Extract frame at specified time
            frame = clip.get_frame(time_offset)

            # Convert numpy array to PIL Image
            img = Image.fromarray(frame)

            # Create thumbnail
            thumb = self._create_thumbnail(img, size)

            # Convert to JPEG bytes
            thumbnail_bytes = self._image_to_bytes(thumb, "JPEG")

            logger.info(f"Successfully extracted thumbnail from {video_path}")
            return thumbnail_bytes

        except Exception as e:
            logger.error(f"Failed to extract video thumbnail from {video_path}: {e}")
            raise VideoProcessingError(f"Failed to extract video thumbnail: {str(e)}")
        finally:
            if clip is not None:
                try:
                    clip.close()
                except Exception as e:
                    logger.warning(f"Error closing video clip: {e}")

    def get_video_duration(self, video_path: str) -> float:
        """
        Get the duration of a video file in seconds.

        Args:
            video_path: Path to the video file

        Returns:
            Duration in seconds

        Raises:
            VideoProcessingError: If duration extraction fails
        """
        self._check_moviepy_available()
        clip = None

        try:
            logger.debug(f"Getting duration for video: {video_path}")
            clip = VideoFileClip(video_path)
            duration = clip.duration

            logger.info(f"Video duration: {duration:.2f}s for {video_path}")
            return duration

        except Exception as e:
            logger.error(f"Failed to get video duration for {video_path}: {e}")
            raise VideoProcessingError(f"Failed to get video duration: {str(e)}")
        finally:
            if clip is not None:
                try:
                    clip.close()
                except Exception as e:
                    logger.warning(f"Error closing video clip: {e}")

    def compress_video(
        self,
        video_path: str,
        quality: str = "medium",
        output_path: Optional[str] = None,
    ) -> str:
        """
        Compress a video file to reduce file size.

        Args:
            video_path: Path to the input video file
            quality: Quality preset - 'low', 'medium', or 'high'
                - 'low': High compression, smaller file (bitrate ~500k)
                - 'medium': Balanced compression (bitrate ~1500k)
                - 'high': Light compression, larger file (bitrate ~3000k)
            output_path: Optional output path. If None, creates temp file.

        Returns:
            Path to the compressed video file

        Raises:
            VideoProcessingError: If compression fails
        """
        self._check_moviepy_available()

        # Quality presets (bitrate in kbps)
        quality_presets = {
            "low": "500k",
            "medium": "1500k",
            "high": "3000k",
        }

        if quality not in quality_presets:
            raise VideoProcessingError(
                f"Invalid quality preset: {quality}. Must be one of: {list(quality_presets.keys())}"
            )

        bitrate = quality_presets[quality]
        clip = None

        try:
            logger.info(f"Compressing video: {video_path} with quality={quality}")

            # Determine output path
            if output_path is None:
                ext = self._get_video_extension(video_path) or "mp4"
                fd, output_path = tempfile.mkstemp(suffix=f".{ext}")
                os.close(fd)

            clip = VideoFileClip(video_path)

            # Write compressed video
            clip.write_videofile(
                output_path,
                bitrate=bitrate,
                audio_codec="aac",
                codec="libx264",
                preset="medium",
                logger=None,  # Suppress moviepy's verbose output
            )

            original_size = os.path.getsize(video_path)
            compressed_size = os.path.getsize(output_path)
            compression_ratio = (1 - compressed_size / original_size) * 100

            logger.info(
                f"Video compressed: {original_size / 1024 / 1024:.2f}MB -> "
                f"{compressed_size / 1024 / 1024:.2f}MB ({compression_ratio:.1f}% reduction)"
            )

            return output_path

        except Exception as e:
            logger.error(f"Failed to compress video {video_path}: {e}")
            # Clean up output file on failure
            if output_path and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception:
                    pass
            raise VideoProcessingError(f"Failed to compress video: {str(e)}")
        finally:
            if clip is not None:
                try:
                    clip.close()
                except Exception as e:
                    logger.warning(f"Error closing video clip: {e}")

    def validate_video(self, video_path: str) -> VideoValidationResult:
        """
        Validate a video file against configured limits.

        Checks:
        - File exists and is readable
        - Format is in allowed formats
        - File size is within limit
        - Duration is within limit

        Args:
            video_path: Path to the video file

        Returns:
            VideoValidationResult with validation status and details
        """
        try:
            # Check file exists
            if not os.path.exists(video_path):
                logger.warning(f"Video file not found: {video_path}")
                return VideoValidationResult(
                    is_valid=False,
                    error_message=f"Video file not found: {video_path}"
                )

            # Check format
            video_format = self._get_video_extension(video_path)
            if video_format not in self.allowed_video_formats:
                logger.warning(
                    f"Invalid video format: {video_format}. "
                    f"Allowed formats: {self.allowed_video_formats}"
                )
                return VideoValidationResult(
                    is_valid=False,
                    error_message=f"Invalid video format: {video_format}. Allowed: {', '.join(self.allowed_video_formats)}",
                    format=video_format
                )

            # Check file size
            size_bytes = os.path.getsize(video_path)
            size_mb = size_bytes / (1024 * 1024)
            if size_mb > self.max_video_size_mb:
                logger.warning(
                    f"Video too large: {size_mb:.2f}MB > {self.max_video_size_mb}MB"
                )
                return VideoValidationResult(
                    is_valid=False,
                    error_message=f"Video too large: {size_mb:.2f}MB exceeds limit of {self.max_video_size_mb}MB",
                    format=video_format,
                    size_bytes=size_bytes
                )

            # Check duration (requires moviepy)
            duration_seconds = None
            if MOVIEPY_AVAILABLE:
                try:
                    duration_seconds = self.get_video_duration(video_path)
                    if duration_seconds > self.max_video_duration_seconds:
                        logger.warning(
                            f"Video too long: {duration_seconds:.2f}s > {self.max_video_duration_seconds}s"
                        )
                        return VideoValidationResult(
                            is_valid=False,
                            error_message=f"Video too long: {duration_seconds:.2f}s exceeds limit of {self.max_video_duration_seconds}s",
                            format=video_format,
                            size_bytes=size_bytes,
                            duration_seconds=duration_seconds
                        )
                except VideoProcessingError as e:
                    logger.warning(f"Could not check video duration: {e}")
                    # Continue validation even if duration check fails
            else:
                logger.warning("moviepy not available, skipping duration validation")

            logger.info(
                f"Video validated successfully: {video_path} "
                f"(format={video_format}, size={size_mb:.2f}MB, duration={duration_seconds}s)"
            )

            return VideoValidationResult(
                is_valid=True,
                format=video_format,
                size_bytes=size_bytes,
                duration_seconds=duration_seconds
            )

        except Exception as e:
            logger.error(f"Unexpected error validating video {video_path}: {e}")
            return VideoValidationResult(
                is_valid=False,
                error_message=f"Validation error: {str(e)}"
            )

    def process_video(self, video_path: str) -> ProcessedVideo:
        """
        Process a video file and extract metadata.

        Args:
            video_path: Path to the video file

        Returns:
            ProcessedVideo with metadata and optional thumbnail

        Raises:
            VideoProcessingError: If processing fails
        """
        self._check_moviepy_available()
        clip = None

        try:
            logger.info(f"Processing video: {video_path}")

            # Validate first
            validation = self.validate_video(video_path)
            if not validation.is_valid:
                raise VideoProcessingError(validation.error_message)

            clip = VideoFileClip(video_path)
            width, height = clip.size
            duration = clip.duration
            video_format = self._get_video_extension(video_path)
            size_bytes = os.path.getsize(video_path)

            # Extract thumbnail
            thumbnail_data = None
            thumbnail_width = None
            thumbnail_height = None
            try:
                thumbnail_data = self.extract_video_thumbnail(video_path)
                if thumbnail_data:
                    # Get thumbnail dimensions
                    thumb_img = Image.open(io.BytesIO(thumbnail_data))
                    thumbnail_width, thumbnail_height = thumb_img.size
            except Exception as e:
                logger.warning(f"Could not extract thumbnail: {e}")

            result = ProcessedVideo(
                width=width,
                height=height,
                duration_seconds=duration,
                format=video_format,
                size_bytes=size_bytes,
                thumbnail_data=thumbnail_data,
                thumbnail_width=thumbnail_width,
                thumbnail_height=thumbnail_height,
            )

            logger.info(
                f"Video processed: {width}x{height}, {duration:.2f}s, {video_format}, "
                f"{size_bytes / 1024 / 1024:.2f}MB"
            )

            return result

        except VideoProcessingError:
            raise
        except Exception as e:
            logger.error(f"Failed to process video {video_path}: {e}")
            raise VideoProcessingError(f"Failed to process video: {str(e)}")
        finally:
            if clip is not None:
                try:
                    clip.close()
                except Exception as e:
                    logger.warning(f"Error closing video clip: {e}")


# ============================================================================
# SINGLETON ACCESS
# ============================================================================

_media_processor: Optional[MediaProcessor] = None


def get_media_processor() -> MediaProcessor:
    """Get the global media processor instance."""
    global _media_processor
    if _media_processor is None:
        _media_processor = MediaProcessor()
    return _media_processor
