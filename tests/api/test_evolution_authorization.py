"""
Evolution router authorization tests (HIVE-014).

The three `trigger-*` endpoints were anonymous. Two of them spend LLM tokens on
demand. The third is worse:

    POST /evolution/bots/{id}/trigger-self-coding?what_to_improve=<caller text>
      -> analyze_and_code(what_to_improve=...)
      -> interpolated verbatim into the code-generation prompt (bot_self_coding.py:226)
      -> LLM emits Python
      -> _validate_code(), a substring denylist that string concatenation defeats
      -> exec(code, sandbox_globals)  in this process

Caller-controlled text therefore reached code execution, with no authentication.

Gating removes anonymous reachability, but an admin-only RCE is still an RCE, so the
endpoint is additionally off unless explicitly enabled. Both layers are pinned here.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from mind.api.dependencies import get_db_session
from mind.api.main import app
from mind.config.settings import settings
from mind.core.auth import create_access_token

TRIGGERS = [
    "/evolution/bots/{id}/trigger-reflection",
    "/evolution/bots/{id}/trigger-evolution",
    "/evolution/bots/{id}/trigger-self-coding",
]

PUBLIC_READS = [
    "/evolution/bots/{id}/intelligence",
    "/evolution/bots/{id}/skills",
    "/evolution/platform/intelligence",
    "/evolution/activity/recent",
]


def _user(user_id, *, is_admin):
    return SimpleNamespace(
        id=user_id,
        email="user@example.com",
        display_name="Test User",
        avatar_seed=str(user_id),
        created_at=datetime(2026, 1, 1),
        is_active=True,
        is_admin=is_admin,
        is_banned=False,
    )


@pytest.fixture
def client_as():
    def _factory(*, is_admin):
        user_id = uuid4()
        result = MagicMock()
        result.scalar_one_or_none.return_value = _user(user_id, is_admin=is_admin)
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)

        async def _override():
            yield session

        app.dependency_overrides[get_db_session] = _override
        client = TestClient(app, raise_server_exceptions=False)
        client.headers.update({"Authorization": f"Bearer {create_access_token(user_id)}"})
        return client

    yield _factory
    app.dependency_overrides.clear()


# ============================================================================
# The triggers are admin-only
# ============================================================================

@pytest.mark.parametrize("path", TRIGGERS)
def test_triggers_reject_anonymous_callers(path):
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(path.replace("{id}", str(uuid4())))
    assert response.status_code == 401, f"{path} was reachable anonymously"


@pytest.mark.parametrize("path", TRIGGERS)
def test_triggers_reject_non_admins(client_as, path):
    response = client_as(is_admin=False).post(path.replace("{id}", str(uuid4())))
    assert response.status_code == 403, f"{path} was reachable by a non-admin"


def test_github_status_is_admin_only(client_as):
    """It reports whether a token is configured — reconnaissance, not observation."""
    anonymous = TestClient(app, raise_server_exceptions=False)
    assert anonymous.get("/evolution/github/status").status_code == 401
    assert client_as(is_admin=False).get("/evolution/github/status").status_code == 403


# ============================================================================
# The self-coding trigger is off unless explicitly enabled
# ============================================================================

def test_self_coding_trigger_is_enabled_by_default():
    """Deliberately reversed once the sandbox was rebuilt.

    HIVE-014 defaulted this to False because generated code ran in-process behind a
    substring denylist that string concatenation defeats — an admin-only RCE. HIVE-032
    replaced that with a separate interpreter, killed on timeout, with no import
    system, filesystem or network, and capped memory and CPU.

    Bots writing code that extends themselves is the point of this project, so with
    containment moved to the process boundary the endpoint is on. It stays admin-only:
    it still turns an API parameter into code execution.
    """
    assert settings.SELF_CODING_HTTP_TRIGGER_ENABLED is True


def test_the_trigger_remains_admin_only():
    """Enabling it must not have widened WHO can reach it."""
    spec = app.openapi()
    operation = spec["paths"]["/evolution/bots/{bot_id}/trigger-self-coding"]["post"]
    assert operation.get("security"), "the self-coding trigger lost its auth requirement"


def test_self_coding_trigger_returns_503_when_disabled(client_as, monkeypatch):
    monkeypatch.setattr(settings, "SELF_CODING_HTTP_TRIGGER_ENABLED", False)

    response = client_as(is_admin=True).post(
        f"/evolution/bots/{uuid4()}/trigger-self-coding?what_to_improve=anything"
    )

    assert response.status_code == 503
    assert "disabled" in response.text.lower()


def test_disabled_check_runs_before_any_work(client_as, monkeypatch):
    """The 503 must short-circuit — no DB read, no bot lookup, no LLM call."""
    monkeypatch.setattr(settings, "SELF_CODING_HTTP_TRIGGER_ENABLED", False)

    called = {"factory": False}

    def _factory():
        called["factory"] = True
        raise AssertionError("session opened despite the trigger being disabled")

    monkeypatch.setattr("mind.api.routes.evolution.async_session_factory", _factory)

    response = client_as(is_admin=True).post(
        f"/evolution/bots/{uuid4()}/trigger-self-coding"
    )

    assert response.status_code == 503
    assert not called["factory"]


# ============================================================================
# Reads stay public — bot intelligence is part of the observation product
# ============================================================================

@pytest.mark.parametrize("path", PUBLIC_READS)
def test_reads_remain_anonymous(path):
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get(path.replace("{id}", str(uuid4()))).status_code != 401, (
        f"GET {path} now requires auth; these back the portal"
    )
