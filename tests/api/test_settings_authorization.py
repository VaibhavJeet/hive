"""
Settings authorization tests (HIVE-007).

`/settings/*` is platform-wide configuration. Every endpoint was anonymous, including
the writes — so any caller could disable two-factor auth, raise the login-attempt
limit, turn off the profanity filter, or switch on maintenance mode.

The reads matter too: `GET /settings/auth` reports whether 2FA is on, how many login
attempts are allowed, and how long a lockout lasts. That is reconnaissance for a
credential-stuffing run, so reads are admin-gated as well.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from mind.api.dependencies import get_db_session
from mind.api.main import app
from mind.core.auth import create_access_token

WRITE_ENDPOINTS = [
    ("put", "/settings", {}),
    ("post", "/settings/reset", None),
    ("put", "/settings/general", {"site_name": "pwned"}),
    ("put", "/settings/bot", {}),
    ("put", "/settings/auth", {"two_factor_enabled": False, "max_login_attempts": 10}),
    ("put", "/settings/moderation", {"profanity_filter": False}),
    ("put", "/settings/notifications", {}),
]

READ_ENDPOINTS = [
    "/settings",
    "/settings/general",
    "/settings/bot",
    "/settings/auth",
    "/settings/moderation",
    "/settings/notifications",
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
        client.headers.update(
            {"Authorization": f"Bearer {create_access_token(user_id)}"}
        )
        return client

    yield _factory
    app.dependency_overrides.clear()


@pytest.mark.parametrize("method,path,payload", WRITE_ENDPOINTS)
def test_settings_writes_reject_anonymous_callers(method, path, payload):
    client = TestClient(app, raise_server_exceptions=False)
    response = client.request(method, path, json=payload)
    assert response.status_code == 401, f"{method.upper()} {path} allowed an anonymous write"


@pytest.mark.parametrize("path", READ_ENDPOINTS)
def test_settings_reads_reject_anonymous_callers(path):
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get(path).status_code == 401, f"GET {path} leaked configuration"


@pytest.mark.parametrize("method,path,payload", WRITE_ENDPOINTS)
def test_settings_writes_reject_non_admins(client_as, method, path, payload):
    client = client_as(is_admin=False)
    response = client.request(method, path, json=payload)
    assert response.status_code == 403, (
        f"{method.upper()} {path} allowed a signed-in non-admin to change platform config"
    )


def test_admin_can_read_settings(client_as):
    response = client_as(is_admin=True).get("/settings")
    assert response.status_code == 200
    assert "auth" in response.json()


def test_disabling_two_factor_requires_admin(client_as):
    """The single most damaging write, called out explicitly."""
    response = client_as(is_admin=False).put(
        "/settings/auth", json={"two_factor_enabled": False}
    )
    assert response.status_code == 403
