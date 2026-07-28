"""
Voice tests.

Hive shipped a complete three-provider TTS subsystem that nothing could reach — no
audio surface existed anywhere in the API, portal or mobile app. These cover the
surface that makes it real.

The interesting assertions are about *voice assignment*. A bot's voice is derived from
its personality traits rather than stored, which means it is stable across restarts and
across databases without any migration, and two bots with different temperaments
genuinely sound different. That is the difference between a persona and a costume, and
it is what these tests pin.

The synthesis test marked `network` reaches Microsoft's Edge TTS service. It needs no
API key or account, so it runs on a fresh checkout — but it does need connectivity.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from mind.api.dependencies import get_db_session
from mind.api.main import app
from mind.api.routes.voice import MAX_SPEECH_CHARS, choose_voice_profile
from mind.capabilities.tts import BOT_VOICE_PROFILES
from mind.core.auth import create_access_token


def _bot(*, gender="female", age=25, extraversion=0.5, agreeableness=0.5, neuroticism=0.5):
    return SimpleNamespace(
        id=uuid4(),
        display_name="Ada",
        gender=gender,
        age=age,
        personality_traits={
            "extraversion": extraversion,
            "agreeableness": agreeableness,
            "neuroticism": neuroticism,
        },
    )


def _token_user(user_id):
    return SimpleNamespace(
        id=user_id, email="u@example.com", display_name="U", avatar_seed="s",
        created_at=datetime(2026, 1, 1), is_active=True, is_admin=False, is_banned=False,
    )


@pytest.fixture
def signed_in():
    user_id = uuid4()
    result = MagicMock()
    result.scalar_one_or_none.return_value = _token_user(user_id)
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    async def _override():
        yield session

    app.dependency_overrides[get_db_session] = _override
    client = TestClient(app, raise_server_exceptions=False)
    client.headers.update({"Authorization": f"Bearer {create_access_token(user_id)}"})
    yield client
    app.dependency_overrides.clear()


# ============================================================================
# A voice is derived from who the bot is
# ============================================================================

def test_the_same_bot_always_sounds_the_same():
    """Derived, not stored — so it survives restarts with nothing to migrate."""
    bot = _bot(extraversion=0.8, agreeableness=0.7)
    first, _ = choose_voice_profile(bot)
    second, _ = choose_voice_profile(bot)
    assert first == second


def test_different_temperaments_sound_different():
    outgoing, _ = choose_voice_profile(
        _bot(gender="male", extraversion=0.85, agreeableness=0.75)
    )
    reserved, _ = choose_voice_profile(
        _bot(gender="male", extraversion=0.2, neuroticism=0.2)
    )
    assert outgoing != reserved, "temperament made no difference to the voice"


def test_age_shifts_the_voice():
    young, _ = choose_voice_profile(_bot(gender="male", age=22, extraversion=0.5))
    old, _ = choose_voice_profile(_bot(gender="male", age=61, extraversion=0.5))
    assert young != old


def test_every_chosen_profile_actually_exists():
    """A profile key that is not in BOT_VOICE_PROFILES would 500 at synthesis time."""
    for gender in ("female", "male", "", None):
        for age in (18, 45, 80):
            for extra in (0.1, 0.5, 0.9):
                for agree in (0.1, 0.9):
                    for neuro in (0.1, 0.9):
                        bot = _bot(
                            gender=gender, age=age, extraversion=extra,
                            agreeableness=agree, neuroticism=neuro,
                        )
                        key, _ = choose_voice_profile(bot)
                        assert key in BOT_VOICE_PROFILES, f"{key} is not a real profile"


def test_missing_traits_do_not_crash():
    """Bots created before a trait existed must still get a voice."""
    bot = SimpleNamespace(
        id=uuid4(), display_name="X", gender=None, age=None, personality_traits={}
    )
    key, reason = choose_voice_profile(bot)
    assert key in BOT_VOICE_PROFILES
    assert reason


# ============================================================================
# The endpoints
# ============================================================================

def test_voice_requires_a_session():
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get(f"/voice/bots/{uuid4()}/profile").status_code == 401
    assert client.get(f"/voice/bots/{uuid4()}/say?text=hello").status_code == 401


def test_an_overlong_utterance_is_refused(signed_in):
    response = signed_in.get(
        f"/voice/bots/{uuid4()}/say?text={'a' * (MAX_SPEECH_CHARS + 1)}"
    )
    assert response.status_code == 422, "no bound on how much a bot will say"


def test_empty_text_is_refused(signed_in):
    assert signed_in.get(f"/voice/bots/{uuid4()}/say?text=").status_code == 422


def test_an_unknown_bot_is_a_404(signed_in, monkeypatch):
    async def _no_bot(bot_id):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Bot not found")

    monkeypatch.setattr("mind.api.routes.voice._load_bot", _no_bot)
    assert signed_in.get(f"/voice/bots/{uuid4()}/profile").status_code == 404


def test_the_profile_endpoint_explains_itself(signed_in, monkeypatch):
    bot = _bot(gender="male", extraversion=0.85, agreeableness=0.8)

    async def _load(bot_id):
        return bot

    monkeypatch.setattr("mind.api.routes.voice._load_bot", _load)

    response = signed_in.get(f"/voice/bots/{bot.id}/profile")
    assert response.status_code == 200

    body = response.json()
    assert body["voice_id"].startswith("en-US-")
    assert body["bot_name"] == "Ada"
    # The reason is the interesting part — it says WHY the bot sounds this way.
    assert "outgoing" in body["reason"]


def test_speech_can_be_disabled(signed_in, monkeypatch):
    from mind.config.settings import settings

    monkeypatch.setattr(settings, "TTS_ENABLED", False)
    response = signed_in.get(f"/voice/bots/{uuid4()}/say?text=hello")

    assert response.status_code == 503
    assert "disabled" in response.text.lower()


def test_a_synthesis_failure_is_a_503_not_a_crash(signed_in, monkeypatch):
    bot = _bot()

    async def _load(bot_id):
        return bot

    async def _fail(**kwargs):
        return SimpleNamespace(success=False, audio_data=None, error="upstream down", format="mp3")

    monkeypatch.setattr("mind.api.routes.voice._load_bot", _load)
    monkeypatch.setattr("mind.api.routes.voice.synthesize_speech", _fail)

    response = signed_in.get(f"/voice/bots/{bot.id}/say?text=hello")
    assert response.status_code == 503
    assert "upstream down" in response.text


def test_audio_is_returned_with_the_right_headers(signed_in, monkeypatch):
    bot = _bot()

    async def _load(bot_id):
        return bot

    async def _synth(**kwargs):
        return SimpleNamespace(
            success=True, audio_data=b"ID3fake-mp3-bytes", error=None, format="mpeg"
        )

    monkeypatch.setattr("mind.api.routes.voice._load_bot", _load)
    monkeypatch.setattr("mind.api.routes.voice.synthesize_speech", _synth)

    response = signed_in.get(f"/voice/bots/{bot.id}/say?text=hello there")

    assert response.status_code == 200
    assert response.content == b"ID3fake-mp3-bytes"
    assert response.headers["content-type"].startswith("audio/")
    assert response.headers["X-Bot-Name"] == "Ada"
    assert response.headers["X-Bot-Voice"].startswith("en-US-")


# ============================================================================
# The real thing
# ============================================================================

@pytest.mark.slow
@pytest.mark.asyncio
async def test_edge_tts_really_produces_audio_with_no_credentials():
    """Reaches Microsoft's Edge TTS. No API key, no account — just connectivity.

    This is the assertion that the subsystem is genuinely usable rather than merely
    wired: a bot saying one sentence comes back as real MP3 bytes.
    """
    from mind.capabilities.tts import TTSProvider, synthesize_speech

    result = await synthesize_speech(
        text="I am one of the beings that live here.",
        voice_id="en-US-AriaNeural",
        provider=TTSProvider.EDGE,
    )

    if not result.success:
        pytest.skip(f"Edge TTS unreachable: {result.error}")

    assert result.audio_data
    assert len(result.audio_data) > 5000, "suspiciously small for a spoken sentence"

    # Either an ID3 tag or a raw MPEG frame-sync. Compared at the right widths:
    # an earlier version sliced 3 bytes and compared against 2-byte sync markers,
    # so it could never match even though the audio was perfectly valid.
    head = result.audio_data
    assert head[:3] == b"ID3" or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"), (
        f"not recognisable MP3, starts with {head[:4]!r}"
    )
