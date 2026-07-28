"""
Text-to-Speech - Give bots unique voices.

Supports multiple TTS providers for generating speech from text.
Each bot can have a distinct voice that matches their personality.
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


class TTSProvider(str, Enum):
    """Available TTS providers."""
    OPENAI = "openai"
    ELEVENLABS = "elevenlabs"
    AZURE = "azure"
    EDGE = "edge"  # Microsoft Edge TTS (free)


class VoiceGender(str, Enum):
    """Voice gender options."""
    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"


class VoiceStyle(str, Enum):
    """Voice style/emotion."""
    NEUTRAL = "neutral"
    CHEERFUL = "cheerful"
    SAD = "sad"
    ANGRY = "angry"
    FEARFUL = "fearful"
    FRIENDLY = "friendly"
    HOPEFUL = "hopeful"
    SHOUTING = "shouting"
    WHISPERING = "whispering"


@dataclass
class Voice:
    """A TTS voice configuration."""
    voice_id: str
    name: str
    provider: TTSProvider
    gender: VoiceGender = VoiceGender.NEUTRAL
    language: str = "en-US"
    description: str = ""
    preview_url: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class SpeechResult:
    """Result from speech synthesis."""
    audio_data: Optional[bytes] = None
    audio_url: Optional[str] = None
    local_path: Optional[Path] = None
    format: str = "mp3"
    duration_ms: float = 0
    success: bool = True
    error: Optional[str] = None

    def save(self, path: Path) -> Path:
        """Save audio to file."""
        if self.audio_data:
            path.write_bytes(self.audio_data)
            self.local_path = path
            return path
        raise ValueError("No audio data to save")

    def to_base64(self) -> str:
        """Get audio as base64 string."""
        if self.audio_data:
            return base64.b64encode(self.audio_data).decode()
        raise ValueError("No audio data")


class TTSProviderBase(ABC):
    """Abstract base class for TTS providers."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    @abstractmethod
    def provider_id(self) -> TTSProvider:
        pass

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: Voice,
        speed: float = 1.0,
        **kwargs
    ) -> SpeechResult:
        """Synthesize speech from text."""
        pass

    @abstractmethod
    async def list_voices(self) -> list[Voice]:
        """List available voices."""
        pass

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


class OpenAITTS(TTSProviderBase):
    """OpenAI TTS provider."""

    BASE_URL = "https://api.openai.com/v1/audio/speech"

    # Available OpenAI voices
    VOICES = {
        "alloy": Voice("alloy", "Alloy", TTSProvider.OPENAI, VoiceGender.NEUTRAL),
        "echo": Voice("echo", "Echo", TTSProvider.OPENAI, VoiceGender.MALE),
        "fable": Voice("fable", "Fable", TTSProvider.OPENAI, VoiceGender.NEUTRAL),
        "onyx": Voice("onyx", "Onyx", TTSProvider.OPENAI, VoiceGender.MALE),
        "nova": Voice("nova", "Nova", TTSProvider.OPENAI, VoiceGender.FEMALE),
        "shimmer": Voice("shimmer", "Shimmer", TTSProvider.OPENAI, VoiceGender.FEMALE),
    }

    @property
    def provider_id(self) -> TTSProvider:
        return TTSProvider.OPENAI

    async def synthesize(
        self,
        text: str,
        voice: Voice,
        speed: float = 1.0,
        model: str = "tts-1",  # or "tts-1-hd"
        response_format: str = "mp3",
        **kwargs
    ) -> SpeechResult:
        """Synthesize speech using OpenAI TTS."""
        if not self.api_key:
            return SpeechResult(success=False, error="OpenAI API key required")

        try:
            session = await self._ensure_session()

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": model,
                "input": text,
                "voice": voice.voice_id,
                "speed": max(0.25, min(4.0, speed)),
                "response_format": response_format,
            }

            async with session.post(
                self.BASE_URL,
                json=payload,
                headers=headers
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    return SpeechResult(
                        success=False,
                        error=f"HTTP {resp.status}: {error_text}"
                    )

                audio_data = await resp.read()

                return SpeechResult(
                    audio_data=audio_data,
                    format=response_format,
                    success=True,
                )

        except Exception as e:
            logger.error(f"OpenAI TTS error: {e}")
            return SpeechResult(success=False, error=str(e))

    async def list_voices(self) -> list[Voice]:
        return list(self.VOICES.values())


class ElevenLabsTTS(TTSProviderBase):
    """ElevenLabs TTS provider - high quality, expressive voices."""

    BASE_URL = "https://api.elevenlabs.io/v1"

    @property
    def provider_id(self) -> TTSProvider:
        return TTSProvider.ELEVENLABS

    async def synthesize(
        self,
        text: str,
        voice: Voice,
        speed: float = 1.0,
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        model_id: str = "eleven_monolingual_v1",
        **kwargs
    ) -> SpeechResult:
        """Synthesize speech using ElevenLabs."""
        if not self.api_key:
            return SpeechResult(success=False, error="ElevenLabs API key required")

        try:
            session = await self._ensure_session()

            headers = {
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
            }

            payload = {
                "text": text,
                "model_id": model_id,
                "voice_settings": {
                    "stability": stability,
                    "similarity_boost": similarity_boost,
                }
            }

            url = f"{self.BASE_URL}/text-to-speech/{voice.voice_id}"

            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    return SpeechResult(
                        success=False,
                        error=f"HTTP {resp.status}: {error_text}"
                    )

                audio_data = await resp.read()

                return SpeechResult(
                    audio_data=audio_data,
                    format="mp3",
                    success=True,
                )

        except Exception as e:
            logger.error(f"ElevenLabs TTS error: {e}")
            return SpeechResult(success=False, error=str(e))

    async def list_voices(self) -> list[Voice]:
        """Fetch available voices from ElevenLabs."""
        if not self.api_key:
            return []

        try:
            session = await self._ensure_session()

            headers = {"xi-api-key": self.api_key}

            async with session.get(
                f"{self.BASE_URL}/voices",
                headers=headers
            ) as resp:
                if resp.status != 200:
                    return []

                data = await resp.json()
                voices = []

                for v in data.get("voices", []):
                    labels = v.get("labels", {})
                    gender = VoiceGender.MALE if labels.get("gender") == "male" else \
                             VoiceGender.FEMALE if labels.get("gender") == "female" else \
                             VoiceGender.NEUTRAL

                    voices.append(Voice(
                        voice_id=v["voice_id"],
                        name=v["name"],
                        provider=TTSProvider.ELEVENLABS,
                        gender=gender,
                        description=labels.get("description", ""),
                        preview_url=v.get("preview_url"),
                    ))

                return voices

        except Exception as e:
            logger.error(f"Failed to fetch ElevenLabs voices: {e}")
            return []


class EdgeTTS(TTSProviderBase):
    """
    Microsoft Edge TTS - Free, high-quality TTS.

    Uses the edge-tts library for free access to Microsoft's neural voices.
    """

    @property
    def provider_id(self) -> TTSProvider:
        return TTSProvider.EDGE

    async def synthesize(
        self,
        text: str,
        voice: Voice,
        speed: float = 1.0,
        pitch: str = "+0Hz",
        **kwargs
    ) -> SpeechResult:
        """Synthesize speech using Edge TTS."""
        try:
            import edge_tts

            # Convert speed to Edge TTS rate format
            rate = f"+{int((speed - 1) * 100)}%" if speed >= 1 else f"{int((speed - 1) * 100)}%"

            communicate = edge_tts.Communicate(
                text,
                voice.voice_id,
                rate=rate,
                pitch=pitch
            )

            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]

            return SpeechResult(
                audio_data=audio_data,
                format="mp3",
                success=True,
            )

        except ImportError:
            return SpeechResult(
                success=False,
                error="edge-tts package not installed. Run: pip install edge-tts"
            )
        except Exception as e:
            logger.error(f"Edge TTS error: {e}")
            return SpeechResult(success=False, error=str(e))

    async def list_voices(self) -> list[Voice]:
        """List available Edge TTS voices."""
        try:
            import edge_tts

            voices_list = await edge_tts.list_voices()
            voices = []

            for v in voices_list:
                gender = VoiceGender.MALE if v["Gender"] == "Male" else \
                         VoiceGender.FEMALE if v["Gender"] == "Female" else \
                         VoiceGender.NEUTRAL

                voices.append(Voice(
                    voice_id=v["ShortName"],
                    name=v["FriendlyName"],
                    provider=TTSProvider.EDGE,
                    gender=gender,
                    language=v["Locale"],
                ))

            return voices

        except ImportError:
            logger.warning("edge-tts not installed")
            return []
        except Exception as e:
            logger.error(f"Failed to list Edge voices: {e}")
            return []


# Registry
_tts_providers: dict[TTSProvider, type[TTSProviderBase]] = {
    TTSProvider.OPENAI: OpenAITTS,
    TTSProvider.ELEVENLABS: ElevenLabsTTS,
    TTSProvider.EDGE: EdgeTTS,
}


def get_tts_provider(
    provider: TTSProvider = TTSProvider.EDGE,
    api_key: Optional[str] = None
) -> TTSProviderBase:
    """Get a TTS provider instance."""
    provider_class = _tts_providers.get(provider)
    if not provider_class:
        raise ValueError(f"Unknown TTS provider: {provider}")
    return provider_class(api_key=api_key)


async def synthesize_speech(
    text: str,
    voice_id: str = "en-US-AriaNeural",  # Edge TTS default
    provider: TTSProvider = TTSProvider.EDGE,
    api_key: Optional[str] = None,
    **kwargs
) -> SpeechResult:
    """
    Convenience function to synthesize speech.

    Usage:
        result = await synthesize_speech("Hello, I am a bot!")
        if result.success:
            result.save(Path("output.mp3"))
    """
    tts = get_tts_provider(provider, api_key)
    try:
        voice = Voice(voice_id=voice_id, name=voice_id, provider=provider)
        return await tts.synthesize(text, voice, **kwargs)
    finally:
        await tts.close()


# Predefined voice profiles for bot personalities
BOT_VOICE_PROFILES = {
    "friendly_female": Voice("en-US-JennyNeural", "Jenny", TTSProvider.EDGE, VoiceGender.FEMALE),
    "professional_male": Voice("en-US-GuyNeural", "Guy", TTSProvider.EDGE, VoiceGender.MALE),
    "young_female": Voice("en-US-AriaNeural", "Aria", TTSProvider.EDGE, VoiceGender.FEMALE),
    "mature_male": Voice("en-US-DavisNeural", "Davis", TTSProvider.EDGE, VoiceGender.MALE),
    "cheerful_female": Voice("en-US-SaraNeural", "Sara", TTSProvider.EDGE, VoiceGender.FEMALE),
    "calm_male": Voice("en-US-TonyNeural", "Tony", TTSProvider.EDGE, VoiceGender.MALE),
}
