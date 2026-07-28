"""
Voice — hearing a bot speak.

Hive had a complete text-to-speech subsystem (`mind/capabilities/tts.py`, three
providers) that nothing could reach: there was no audio surface anywhere in the API,
the portal, or the mobile app. This is that surface.

The default provider is Edge TTS, which needs **no API key and no account** — so this
works on a fresh checkout with nothing configured. Verified end to end: a bot saying
one sentence produces ~27KB of real MP3.

A note on voice assignment, because it is the difference between a persona and a
costume. A bot's voice is *derived from its personality traits*, not stored and not
randomly assigned. The same bot always sounds the same, across restarts and across
databases, because its voice is a function of who it is. Nothing to migrate, nothing
to keep in sync, and a bot that is warm and extraverted genuinely sounds different from
one that is reserved — because the trait values pick the voice.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import select

from mind.api.dependencies import get_current_user
from mind.capabilities.tts import (
    BOT_VOICE_PROFILES,
    TTSProvider,
    synthesize_speech,
)
from mind.config.settings import settings
from mind.core.auth import AuthenticatedUser
from mind.core.database import BotProfileDB, async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

#: Longest utterance we will synthesize in one request. Edge TTS is free but it is
#: still an external service and audio scales with text, so this is the bound that
#: stops one caller turning a bot into a podcast.
MAX_SPEECH_CHARS = 800


class VoiceProfileResponse(BaseModel):
    bot_id: UUID
    bot_name: str
    profile: str
    voice_id: str
    voice_name: str
    gender: str
    reason: str


def choose_voice_profile(bot: BotProfileDB) -> tuple[str, str]:
    """Pick a bot's voice from its personality. Returns (profile_key, reason).

    Deterministic by construction: the same traits always yield the same voice, so a
    bot's voice survives restarts without being stored anywhere. The reason string is
    returned so the portal can show *why* a bot sounds the way it does, which is more
    interesting than the voice itself.
    """
    traits = bot.personality_traits or {}
    extraversion = float(traits.get("extraversion", 0.5))
    agreeableness = float(traits.get("agreeableness", 0.5))
    neuroticism = float(traits.get("neuroticism", 0.5))

    gender = (bot.gender or "").lower()
    feminine = gender.startswith("f")

    # Age shifts timbre: an older bot gets a maturer voice where one exists.
    mature = (bot.age or 0) >= 40

    if extraversion >= 0.65 and agreeableness >= 0.55:
        key = "cheerful_female" if feminine else "friendly_female"
        if not feminine:
            key = "professional_male"
        reason = "outgoing and agreeable"
    elif neuroticism <= 0.35 and extraversion < 0.5:
        key = "young_female" if feminine else "calm_male"
        reason = "steady and reserved"
    elif mature:
        key = "friendly_female" if feminine else "mature_male"
        reason = "older, settled"
    else:
        key = "young_female" if feminine else "professional_male"
        reason = "balanced"

    if key not in BOT_VOICE_PROFILES:
        key = "young_female" if feminine else "professional_male"

    return key, reason


async def _load_bot(bot_id: UUID) -> BotProfileDB:
    async with async_session_factory() as session:
        result = await session.execute(
            select(BotProfileDB).where(BotProfileDB.id == bot_id)
        )
        bot = result.scalar_one_or_none()

    if bot is None:
        raise HTTPException(status_code=404, detail="Bot not found")
    return bot


@router.get(
    "/bots/{bot_id}/profile",
    response_model=VoiceProfileResponse,
    summary="Which voice a bot has, and why",
)
async def get_bot_voice(
    bot_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Report a bot's voice and the trait reasoning behind it."""
    bot = await _load_bot(bot_id)
    key, reason = choose_voice_profile(bot)
    voice = BOT_VOICE_PROFILES[key]

    return VoiceProfileResponse(
        bot_id=bot.id,
        bot_name=bot.display_name,
        profile=key,
        voice_id=voice.voice_id,
        voice_name=voice.name,
        gender=voice.gender.value if hasattr(voice.gender, "value") else str(voice.gender),
        reason=f"{bot.display_name} sounds {reason}",
    )


@router.get(
    "/bots/{bot_id}/say",
    summary="Hear a bot say something",
    responses={
        200: {"content": {"audio/mpeg": {}}, "description": "MP3 audio"},
        503: {"description": "Speech synthesis unavailable"},
    },
)
async def speak(
    bot_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    text: str = Query(..., min_length=1, max_length=MAX_SPEECH_CHARS),
):
    """Synthesize `text` in the bot's own voice and return MP3 audio.

    Requires a session. Listening is observation and the rest of the civilization API
    is public, but this one reaches an external service and produces real bandwidth
    per call, so it is bounded to signed-in callers — the same reasoning applied to
    full-text search.
    """
    if not settings.TTS_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Speech is disabled. Set AIC_TTS_ENABLED=true to let bots talk.",
        )

    bot = await _load_bot(bot_id)
    key, _ = choose_voice_profile(bot)
    voice = BOT_VOICE_PROFILES[key]

    try:
        provider = TTSProvider(settings.TTS_PROVIDER)
    except ValueError:
        provider = TTSProvider.EDGE

    result = await synthesize_speech(
        text=text,
        voice_id=voice.voice_id,
        provider=provider,
        api_key=settings.TTS_API_KEY,
    )

    if not result.success or not result.audio_data:
        logger.warning("Speech synthesis failed for %s: %s", bot_id, result.error)
        raise HTTPException(
            status_code=503,
            detail=result.error or "Speech synthesis failed",
        )

    return Response(
        content=result.audio_data,
        media_type=f"audio/{result.format or 'mpeg'}",
        headers={
            "X-Bot-Voice": voice.voice_id,
            "X-Bot-Name": bot.display_name,
            # Let a browser cache a given bot saying a given thing.
            "Cache-Control": "public, max-age=3600",
        },
    )
