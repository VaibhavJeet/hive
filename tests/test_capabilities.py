"""
Unit tests for Bot Capabilities.

Tests the various capability modules:
- Web Search
- Image Generation
- Text-to-Speech
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mind.capabilities.web_search import (
    DuckDuckGoSearch,
    SearchResult,
    SearchResponse,
    SearchProvider,
)
from mind.capabilities.image_gen import (
    OpenAIImageGenerator,
    GeneratedImage,
    ImageGenerationResult,
    ImageSize,
    ImageStyle,
    ImageProvider,
)
from mind.capabilities.tts import (
    OpenAITTS,
    ElevenLabsTTS,
    EdgeTTS,
    Voice,
    SpeechResult,
    TTSProvider,
    VoiceGender,
    get_tts_provider,
    BOT_VOICE_PROFILES,
)


class TestWebSearch:
    """Test suite for Web Search capability."""

    def test_duckduckgo_provider_id(self):
        """Test DuckDuckGo provider ID."""
        search = DuckDuckGoSearch()
        assert search.provider_id == SearchProvider.DUCKDUCKGO

    def test_search_result_creation(self):
        """Test creating a SearchResult."""
        result = SearchResult(
            title="Test Result",
            url="https://example.com",
            snippet="This is a test snippet",
            source="test"
        )

        assert result.title == "Test Result"
        assert result.url == "https://example.com"
        assert result.snippet == "This is a test snippet"

    def test_search_response_to_text(self):
        """Test converting search response to text."""
        results = [
            SearchResult(
                title="Result 1",
                url="https://example1.com",
                snippet="First result snippet"
            ),
            SearchResult(
                title="Result 2",
                url="https://example2.com",
                snippet="Second result snippet"
            ),
        ]

        response = SearchResponse(
            query="test query",
            results=results,
            provider=SearchProvider.DUCKDUCKGO,
            total_results=2
        )

        text = response.to_text()
        assert "test query" in text
        assert "Result 1" in text
        assert "Result 2" in text

    def test_search_response_success_property(self):
        """Test search response success property."""
        # Success case
        success_response = SearchResponse(
            query="test",
            results=[SearchResult("T", "u", "s")],
            provider=SearchProvider.DUCKDUCKGO
        )
        assert success_response.success is True

        # Failure case - no results
        fail_response = SearchResponse(
            query="test",
            results=[],
            provider=SearchProvider.DUCKDUCKGO
        )
        assert fail_response.success is False

        # Failure case - error
        error_response = SearchResponse(
            query="test",
            results=[],
            provider=SearchProvider.DUCKDUCKGO,
            error="Connection failed"
        )
        assert error_response.success is False


class TestImageGeneration:
    """Test suite for Image Generation capability."""

    def test_openai_provider_id(self):
        """Test OpenAI image generator provider ID."""
        generator = OpenAIImageGenerator()
        assert generator.provider_id == ImageProvider.OPENAI

    def test_generated_image_has_data(self):
        """Test GeneratedImage has_data property."""
        # With URL
        img_with_url = GeneratedImage(url="https://example.com/image.png")
        assert img_with_url.has_data is True

        # With base64
        img_with_b64 = GeneratedImage(base64_data="aGVsbG8=")
        assert img_with_b64.has_data is True

        # Without data
        img_empty = GeneratedImage()
        assert img_empty.has_data is False

    def test_image_size_enum(self):
        """Test ImageSize enum values."""
        assert ImageSize.SQUARE_SMALL.value == "256x256"
        assert ImageSize.SQUARE_LARGE.value == "1024x1024"
        assert ImageSize.LANDSCAPE.value == "1792x1024"

    def test_image_generation_result(self):
        """Test ImageGenerationResult structure."""
        result = ImageGenerationResult(
            images=[GeneratedImage(url="https://example.com/img.png")],
            success=True,
            generation_time_ms=1500.0
        )

        assert result.success is True
        assert len(result.images) == 1
        assert result.generation_time_ms == 1500.0

    def test_requires_api_key(self):
        """Test that OpenAI generator requires API key."""
        generator = OpenAIImageGenerator()  # No API key
        assert generator.api_key is None


class TestTextToSpeech:
    """Test suite for TTS capability."""

    def test_voice_creation(self):
        """Test creating a Voice object."""
        voice = Voice(
            voice_id="test-voice",
            name="Test Voice",
            provider=TTSProvider.EDGE,
            gender=VoiceGender.FEMALE,
            language="en-US"
        )

        assert voice.voice_id == "test-voice"
        assert voice.gender == VoiceGender.FEMALE
        assert voice.language == "en-US"

    def test_speech_result_structure(self):
        """Test SpeechResult structure."""
        result = SpeechResult(
            audio_data=b"test audio data",
            format="mp3",
            success=True
        )

        assert result.success is True
        assert result.format == "mp3"
        assert result.audio_data == b"test audio data"

    def test_speech_result_to_base64(self):
        """Test converting speech result to base64."""
        result = SpeechResult(
            audio_data=b"hello",
            format="mp3",
            success=True
        )

        b64 = result.to_base64()
        assert b64 == "aGVsbG8="  # base64 of "hello"

    def test_get_tts_provider(self):
        """Test getting TTS provider by type."""
        edge_provider = get_tts_provider(TTSProvider.EDGE)
        assert isinstance(edge_provider, EdgeTTS)

        openai_provider = get_tts_provider(TTSProvider.OPENAI, api_key="test")
        assert isinstance(openai_provider, OpenAITTS)

    def test_bot_voice_profiles(self):
        """Test predefined bot voice profiles."""
        assert "friendly_female" in BOT_VOICE_PROFILES
        assert "professional_male" in BOT_VOICE_PROFILES

        voice = BOT_VOICE_PROFILES["friendly_female"]
        assert voice.gender == VoiceGender.FEMALE
        assert voice.provider == TTSProvider.EDGE

    def test_openai_voices(self):
        """Test OpenAI TTS available voices."""
        tts = OpenAITTS()
        assert "alloy" in tts.VOICES
        assert "nova" in tts.VOICES
        assert tts.VOICES["nova"].gender == VoiceGender.FEMALE


class TestTTSProviders:
    """Test different TTS provider implementations."""

    def test_openai_tts_provider_id(self):
        """Test OpenAI TTS provider ID."""
        tts = OpenAITTS()
        assert tts.provider_id == TTSProvider.OPENAI

    def test_elevenlabs_tts_provider_id(self):
        """Test ElevenLabs TTS provider ID."""
        tts = ElevenLabsTTS()
        assert tts.provider_id == TTSProvider.ELEVENLABS

    def test_edge_tts_provider_id(self):
        """Test Edge TTS provider ID."""
        tts = EdgeTTS()
        assert tts.provider_id == TTSProvider.EDGE

    def test_requires_api_key_openai(self):
        """Test OpenAI TTS requires API key."""
        tts = OpenAITTS()
        assert tts.api_key is None

    def test_requires_api_key_elevenlabs(self):
        """Test ElevenLabs TTS requires API key."""
        tts = ElevenLabsTTS()
        assert tts.api_key is None

    def test_edge_no_api_key_needed(self):
        """Test Edge TTS works without API key."""
        tts = EdgeTTS()
        # Edge TTS is free and doesn't need an API key
        assert tts.api_key is None
