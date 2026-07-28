"""
User identity disclosure tests (HIVE-012).

Hive runs two parallel account systems:

    /auth/register    email + password -> JWT
    /users/register   device_id, no secret; returns the EXISTING account when handed
                      a device_id it already knows

The second is the mobile app's identity mechanism. It makes `device_id` a bearer
credential — and `GET /users/{user_id}` was anonymous and returned it. So the chain was:
read any user's device_id without authenticating, replay it to /users/register, receive
that user's account record.

These tests pin the two halves of the fix: `device_id` never appears in a public view,
and profile reads require a session.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from mind.api.dependencies import get_db_session
from mind.api.main import app
from mind.api.routes.users import RegisteredUserResponse, UserResponse
from mind.core.auth import create_access_token


def _token_user(user_id):
    return SimpleNamespace(
        id=user_id,
        email="user@example.com",
        display_name="Test User",
        avatar_seed=str(user_id),
        created_at=datetime(2026, 1, 1),
        is_active=True,
        is_admin=False,
        is_banned=False,
    )


@pytest.fixture
def client_as():
    def _factory(user_id=None):
        headers = {}
        if user_id is not None:
            result = MagicMock()
            result.scalar_one_or_none.return_value = _token_user(user_id)
            session = MagicMock()
            session.execute = AsyncMock(return_value=result)

            async def _override():
                yield session

            app.dependency_overrides[get_db_session] = _override
            headers["Authorization"] = f"Bearer {create_access_token(user_id)}"

        client = TestClient(app, raise_server_exceptions=False)
        client.headers.update(headers)
        return client

    yield _factory
    app.dependency_overrides.clear()


# ============================================================================
# device_id must never appear in a public view
# ============================================================================

def test_public_user_response_has_no_device_id():
    assert "device_id" not in UserResponse.model_fields, (
        "device_id is a credential for the /users/register path; it must not be in "
        "the public user view"
    )


def test_registration_response_still_returns_device_id():
    """The caller supplied it, so echoing it back discloses nothing."""
    assert "device_id" in RegisteredUserResponse.model_fields


def test_get_user_schema_does_not_expose_device_id():
    """Belt and braces: assert on the published contract, not just the model."""
    spec = app.openapi()
    operation = spec["paths"]["/users/{user_id}"]["get"]
    ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    schema_name = ref.rsplit("/", 1)[-1]
    properties = spec["components"]["schemas"][schema_name]["properties"]

    assert "device_id" not in properties, (
        f"{schema_name} publishes device_id: {sorted(properties)}"
    )


# ============================================================================
# profile reads require a session
# ============================================================================

def test_anonymous_cannot_read_a_profile(client_as):
    response = client_as().get(f"/users/{uuid4()}")
    assert response.status_code == 401


def test_registration_stays_open(client_as):
    """Registration must not require the session it exists to create."""
    spec = app.openapi()
    assert "security" not in spec["paths"]["/users/register"]["post"], (
        "registration became authenticated, which makes it unusable"
    )


def test_bot_listings_stay_public(client_as):
    """Bot browsing is the observation product; it must not regress to authenticated."""
    spec = app.openapi()
    for path in ("/users/bots", "/users/communities"):
        assert "security" not in spec["paths"][path]["get"], f"{path} became authenticated"
