"""
Actor-identity tests (HIVE-003).

The rule under test: the actor performing a request is derived from the bearer token
and never from a request parameter. Before this change, `POST /feed/posts/{id}/like`
took `user_id` as a query parameter and `POST /moderation/resolve/{id}` took
`moderator_id` — so any caller could act as any user or attribute a moderation
decision to any moderator.

Acceptance criteria:
    - route signatures expose actor-shaped ids only where a *target* is meant
    - user A cannot act as user B
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from mind.api.dependencies import get_db_session
from mind.api.main import app
from mind.core.auth import create_access_token

# Actor-shaped names. Any of these surviving as an operation parameter must be a
# deliberate *target* or *filter*, enumerated below.
ACTOR_NAMES = {
    "user_id", "moderator_id", "author_id", "reporter_id", "reviewer_id",
    "admin_id", "liker_id", "viewer_id", "blocker_id", "sender_id",
    "requester_id", "actor_id",
}

# (method, path, param) triples where the id names a target or filter, not the caller.
ALLOWED_TARGET_PARAMS = {
    ("get", "/admin/users/{user_id}", "user_id"),          # view this user
    ("put", "/admin/users/{user_id}/ban", "user_id"),      # ban this user
    ("put", "/admin/users/{user_id}/unban", "user_id"),    # unban this user
    ("get", "/admin/posts", "author_id"),                  # filter by author
    ("get", "/admin/audit-logs", "admin_id"),              # filter by admin
    ("post", "/notifications/send", "user_id"),            # recipient
    ("get", "/search/posts", "author_id"),                 # filter by author
    ("get", "/stories/user/{user_id}", "user_id"),         # whose stories
    ("get", "/users/{user_id}", "user_id"),                # view this profile
    ("put", "/users/{user_id}", "user_id"),                # target, ownership-checked
}


def _fake_user(user_id, *, is_admin=False, is_banned=False):
    return SimpleNamespace(
        id=user_id,
        email="user@example.com",
        display_name="Test User",
        avatar_seed=str(user_id),
        created_at=datetime(2026, 1, 1),
        is_active=True,
        is_admin=is_admin,
        is_banned=is_banned,
    )


@pytest.fixture
def as_user():
    """Sign requests as a given user, stubbing the DB lookup behind the token."""
    def _factory(user_id, **flags):
        result = MagicMock()
        result.scalar_one_or_none.return_value = _fake_user(user_id, **flags)
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


# ============================================================================
# AC 1 — no actor-shaped parameters survive except deliberate targets
# ============================================================================

def test_no_actor_parameters_outside_the_allowlist():
    spec = app.openapi()
    offenders = []

    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            if method not in ("get", "post", "put", "delete", "patch"):
                continue
            for parameter in operation.get("parameters", []):
                name = parameter.get("name")
                if name not in ACTOR_NAMES:
                    continue
                if (method, path, name) in ALLOWED_TARGET_PARAMS:
                    continue
                offenders.append(f"{method.upper()} {path} :: {name}")

    assert not offenders, (
        "actor identity must come from the token, not a parameter:\n  "
        + "\n  ".join(sorted(offenders))
    )


def test_allowlist_has_no_stale_entries():
    """A target that disappears should be removed from the allowlist, not left to rot."""
    spec = app.openapi()
    live = {
        (method, path, parameter["name"])
        for path, operations in spec["paths"].items()
        for method, operation in operations.items()
        if method in ("get", "post", "put", "delete", "patch")
        for parameter in operation.get("parameters", [])
    }
    assert not (ALLOWED_TARGET_PARAMS - live), (
        f"stale allowlist entries: {sorted(ALLOWED_TARGET_PARAMS - live)}"
    )


# ============================================================================
# AC 2 — user A cannot act as user B
# ============================================================================

def test_actor_is_the_token_user_not_a_query_parameter(as_user, monkeypatch):
    """A stray `user_id` query param must not redirect the action to another user."""
    alice, bob = uuid4(), uuid4()
    seen = {}

    service = MagicMock()

    async def _mark_all_read(user_id):
        seen["user_id"] = user_id
        return 3

    service.mark_all_read = _mark_all_read
    monkeypatch.setattr(
        "mind.api.routes.notifications.get_notification_service", lambda: service
    )

    client = as_user(alice)
    response = client.post(f"/notifications/read-all?user_id={bob}")

    assert response.status_code == 200
    assert seen["user_id"] == alice, "action was attributed to the parameter, not the token"


def test_notification_mutations_are_scoped_to_the_owner(as_user, monkeypatch):
    """HIVE-003 also closed an IDOR: notification ids alone were enough to act."""
    alice = uuid4()
    seen = {}

    service = MagicMock()

    async def _mark_as_read(notification_id, owner_id=None):
        seen["owner_id"] = owner_id
        return True

    service.mark_as_read = _mark_as_read
    monkeypatch.setattr(
        "mind.api.routes.notifications.get_notification_service", lambda: service
    )

    client = as_user(alice)
    response = client.post(f"/notifications/{uuid4()}/read")

    assert response.status_code == 200
    assert seen["owner_id"] == alice, "mutation was not scoped to the caller"


def test_cannot_update_another_users_profile(as_user):
    alice, bob = uuid4(), uuid4()
    client = as_user(alice)

    response = client.put(f"/users/{bob}?display_name=hacked")

    assert response.status_code == 403
    # The app wraps errors via mind.core.error_handlers, so the message is not
    # necessarily under "detail" — assert on the payload rather than its shape.
    assert "your own profile" in response.text


# ============================================================================
# AC 2 (cont.) — the converted endpoints reject anonymous callers
# ============================================================================

@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/feed/posts/{id}/like"),
        ("delete", "/feed/posts/{id}/like"),
        ("post", "/chat/dm"),
        ("get", "/chat/dm/conversations"),
        ("post", "/notifications/read-all"),
        ("delete", "/notifications"),
        ("get", "/hashtags/following/list"),
        ("post", "/hashtags/python/follow"),
        ("post", "/stories"),
        ("post", "/moderation/reports"),
        ("post", "/users/block/{id}"),
        ("get", "/users/blocked"),
    ],
)
def test_converted_endpoints_require_authentication(method, path):
    client = TestClient(app, raise_server_exceptions=False)
    response = client.request(method, path.replace("{id}", str(uuid4())))

    assert response.status_code == 401, (
        f"{method.upper()} {path} returned {response.status_code}, expected 401"
    )
