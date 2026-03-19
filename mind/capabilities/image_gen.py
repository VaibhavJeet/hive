"""
Image Generation - Enable bots to create images using AI.

Supports multiple image generation providers with a unified interface.
Bots can generate images based on their interests, for posts, or in response
to user requests.
"""

import base64
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional
import aiohttp

logger = logging.getLogger(__name__)


class ImageProvider(str, Enum):
    """Available image generation providers."""
    OPENAI = "openai"  # DALL-E
    STABILITY = "stability"  # Stable Diffusion
    REPLICATE = "replicate"
    TOGETHER = "together"
    LOCAL = "local"  # Local Stable Diffusion


class ImageSize(str, Enum):
    """Standard image sizes."""
    SQUARE_SMALL = "256x256"
    SQUARE_MEDIUM = "512x512"
    SQUARE_LARGE = "1024x1024"
    LANDSCAPE = "1792x1024"
    PORTRAIT = "1024x1792"


class ImageStyle(str, Enum):
    """Image generation styles."""
    NATURAL = "natural"
    VIVID = "vivid"
    ANIME = "anime"
    PHOTOREALISTIC = "photorealistic"
    ARTISTIC = "artistic"
    SKETCH = "sketch"


@dataclass
class GeneratedImage:
    """A generated image result."""
    url: Optional[str] = None  # URL if hosted
    base64_data: Optional[str] = None  # Base64 encoded image
    local_path: Optional[Path] = None  # Local file path
    prompt: str = ""
    revised_prompt: Optional[str] = None  # Some providers revise prompts
    provider: ImageProvider = ImageProvider.OPENAI
    size: str = "1024x1024"
    metadata: dict = field(default_factory=dict)

    @property
    def has_data(self) -> bool:
        return bool(self.url or self.base64_data or self.local_path)

    def save(self, path: Path) -> Path:
        """Save image to file."""
        if self.base64_data:
            data = base64.b64decode(self.base64_data)
            path.write_bytes(data)
            self.local_path = path
            return path
        raise ValueError("No image data to save")


@dataclass
class ImageGenerationResult:
    """Result from image generation request."""
    images: list[GeneratedImage]
    success: bool = True
    error: Optional[str] = None
    generation_time_ms: float = 0


class ImageGenerator(ABC):
    """Abstract base class for image generation providers."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    @abstractmethod
    def provider_id(self) -> ImageProvider:
        """Get the provider identifier."""
        pass

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        size: ImageSize = ImageSize.SQUARE_LARGE,
        style: ImageStyle = ImageStyle.NATURAL,
        num_images: int = 1,
        **kwargs
    ) -> ImageGenerationResult:
        """Generate images from a prompt."""
        pass

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


class OpenAIImageGenerator(ImageGenerator):
    """
    OpenAI DALL-E image generation.

    Supports DALL-E 2 and DALL-E 3 models.
    """

    BASE_URL = "https://api.openai.com/v1/images/generations"

    @property
    def provider_id(self) -> ImageProvider:
        return ImageProvider.OPENAI

    async def generate(
        self,
        prompt: str,
        size: ImageSize = ImageSize.SQUARE_LARGE,
        style: ImageStyle = ImageStyle.NATURAL,
        num_images: int = 1,
        model: str = "dall-e-3",
        quality: str = "standard",  # or "hd"
        response_format: str = "url",  # or "b64_json"
        **kwargs
    ) -> ImageGenerationResult:
        """Generate images using DALL-E."""
        if not self.api_key:
            return ImageGenerationResult(
                images=[],
                success=False,
                error="OpenAI API key required"
            )

        import time
        start_time = time.time()

        try:
            session = await self._ensure_session()

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            # Map style to DALL-E style parameter
            dalle_style = "vivid" if style == ImageStyle.VIVID else "natural"

            payload = {
                "model": model,
                "prompt": prompt,
                "n": min(num_images, 1 if model == "dall-e-3" else 10),
                "size": size.value,
                "style": dalle_style,
                "quality": quality,
                "response_format": response_format,
            }

            async with session.post(
                self.BASE_URL,
                json=payload,
                headers=headers
            ) as resp:
                if resp.status != 200:
                    error_data = await resp.json()
                    return ImageGenerationResult(
                        images=[],
                        success=False,
                        error=error_data.get("error", {}).get("message", f"HTTP {resp.status}")
                    )

                data = await resp.json()
                images = []

                for img_data in data.get("data", []):
                    images.append(GeneratedImage(
                        url=img_data.get("url"),
                        base64_data=img_data.get("b64_json"),
                        prompt=prompt,
                        revised_prompt=img_data.get("revised_prompt"),
                        provider=self.provider_id,
                        size=size.value,
                    ))

                return ImageGenerationResult(
                    images=images,
                    success=True,
                    generation_time_ms=(time.time() - start_time) * 1000
                )

        except Exception as e:
            logger.error(f"OpenAI image generation error: {e}")
            return ImageGenerationResult(
                images=[],
                success=False,
                error=str(e)
            )


class StabilityImageGenerator(ImageGenerator):
    """
    Stability AI image generation (Stable Diffusion).

    Supports various Stable Diffusion models via Stability API.
    """

    BASE_URL = "https://api.stability.ai/v1/generation"

    @property
    def provider_id(self) -> ImageProvider:
        return ImageProvider.STABILITY

    async def generate(
        self,
        prompt: str,
        size: ImageSize = ImageSize.SQUARE_LARGE,
        style: ImageStyle = ImageStyle.NATURAL,
        num_images: int = 1,
        engine: str = "stable-diffusion-xl-1024-v1-0",
        steps: int = 30,
        cfg_scale: float = 7.0,
        **kwargs
    ) -> ImageGenerationResult:
        """Generate images using Stability AI."""
        if not self.api_key:
            return ImageGenerationResult(
                images=[],
                success=False,
                error="Stability API key required"
            )

        import time
        start_time = time.time()

        try:
            session = await self._ensure_session()

            # Parse size
            width, height = map(int, size.value.split("x"))

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            # Add style preset based on style enum
            style_preset = {
                ImageStyle.ANIME: "anime",
                ImageStyle.PHOTOREALISTIC: "photographic",
                ImageStyle.ARTISTIC: "digital-art",
                ImageStyle.SKETCH: "line-art",
            }.get(style)

            payload = {
                "text_prompts": [{"text": prompt, "weight": 1.0}],
                "cfg_scale": cfg_scale,
                "width": width,
                "height": height,
                "samples": num_images,
                "steps": steps,
            }

            if style_preset:
                payload["style_preset"] = style_preset

            async with session.post(
                f"{self.BASE_URL}/{engine}/text-to-image",
                json=payload,
                headers=headers
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    return ImageGenerationResult(
                        images=[],
                        success=False,
                        error=f"HTTP {resp.status}: {error_text}"
                    )

                data = await resp.json()
                images = []

                for artifact in data.get("artifacts", []):
                    if artifact.get("finishReason") == "SUCCESS":
                        images.append(GeneratedImage(
                            base64_data=artifact.get("base64"),
                            prompt=prompt,
                            provider=self.provider_id,
                            size=size.value,
                        ))

                return ImageGenerationResult(
                    images=images,
                    success=True,
                    generation_time_ms=(time.time() - start_time) * 1000
                )

        except Exception as e:
            logger.error(f"Stability image generation error: {e}")
            return ImageGenerationResult(
                images=[],
                success=False,
                error=str(e)
            )


class TogetherImageGenerator(ImageGenerator):
    """
    Together AI image generation.

    Access to various open-source image models.
    """

    BASE_URL = "https://api.together.xyz/v1/images/generations"

    @property
    def provider_id(self) -> ImageProvider:
        return ImageProvider.TOGETHER

    async def generate(
        self,
        prompt: str,
        size: ImageSize = ImageSize.SQUARE_LARGE,
        style: ImageStyle = ImageStyle.NATURAL,
        num_images: int = 1,
        model: str = "stabilityai/stable-diffusion-xl-base-1.0",
        steps: int = 20,
        **kwargs
    ) -> ImageGenerationResult:
        """Generate images using Together AI."""
        if not self.api_key:
            return ImageGenerationResult(
                images=[],
                success=False,
                error="Together API key required"
            )

        import time
        start_time = time.time()

        try:
            session = await self._ensure_session()

            width, height = map(int, size.value.split("x"))

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": model,
                "prompt": prompt,
                "width": width,
                "height": height,
                "steps": steps,
                "n": num_images,
            }

            async with session.post(
                self.BASE_URL,
                json=payload,
                headers=headers
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    return ImageGenerationResult(
                        images=[],
                        success=False,
                        error=f"HTTP {resp.status}: {error_text}"
                    )

                data = await resp.json()
                images = []

                for img_data in data.get("data", []):
                    images.append(GeneratedImage(
                        url=img_data.get("url"),
                        base64_data=img_data.get("b64_json"),
                        prompt=prompt,
                        provider=self.provider_id,
                        size=size.value,
                    ))

                return ImageGenerationResult(
                    images=images,
                    success=True,
                    generation_time_ms=(time.time() - start_time) * 1000
                )

        except Exception as e:
            logger.error(f"Together image generation error: {e}")
            return ImageGenerationResult(
                images=[],
                success=False,
                error=str(e)
            )


# Registry
_image_providers: dict[ImageProvider, type[ImageGenerator]] = {
    ImageProvider.OPENAI: OpenAIImageGenerator,
    ImageProvider.STABILITY: StabilityImageGenerator,
    ImageProvider.TOGETHER: TogetherImageGenerator,
}


def get_image_generator(
    provider: ImageProvider = ImageProvider.OPENAI,
    api_key: Optional[str] = None
) -> ImageGenerator:
    """Get an image generator instance."""
    provider_class = _image_providers.get(provider)
    if not provider_class:
        raise ValueError(f"Unknown image provider: {provider}")
    return provider_class(api_key=api_key)


async def generate_image(
    prompt: str,
    provider: ImageProvider = ImageProvider.OPENAI,
    size: ImageSize = ImageSize.SQUARE_LARGE,
    style: ImageStyle = ImageStyle.NATURAL,
    api_key: Optional[str] = None,
    **kwargs
) -> ImageGenerationResult:
    """
    Convenience function to generate an image.

    Usage:
        result = await generate_image("A sunset over mountains")
        if result.success:
            print(result.images[0].url)
    """
    generator = get_image_generator(provider, api_key)
    try:
        return await generator.generate(prompt, size, style, **kwargs)
    finally:
        await generator.close()
