"""
WebSocket authentication tests (HIVE-017, HIVE-018).

`/ws/{client_id}` accepted any `client_id` with no handshake check, then trusted a
`user_id` sent inside the message body. A client could therefore subscribe to anyone's
notification stream and post DMs and community chat as anyone — the same
actor-identity-from-a-parameter flaw HIVE-003 fixed across REST, still live on the
socket.

`/ws/admin/{admin_id}` took the admin's UUID from the URL path and merely looked it up.
Knowing a UUID was the entire credential, exactly as in HIVE-001.

Both now authenticate from `?token=`. Browsers cannot set headers on a WebSocket
handshake, so a query parameter is the standard workaround.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from mind.api.main import app
from mind.core.auth import create_access_token

UNAUTHENTICATED = 4401
FORBIDDEN = 4403


@pytest.fixture
def db_returns(monkeypatch):
    """Point the socket's user lookup at a stub row."""
    def _install(user):
        result = MagicMock()
        result.scalar_one_or_none.return_value = user

        session = MagicMock()
        session.execute = AsyncMock(return_value=result)
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        monkeypatch.setattr("mind.api.main.async_session_factory", lambda: session)
        return session

    return _install


def _user(user_id, *, is_admin=False, is_banned=False):
    return SimpleNamespace(
        id=user_id, display_name="U", avatar_seed="s",
        is_admin=is_admin, is_banned=is_banned, is_active=True,
    )


def _closes_with(client, url, code):
    """Assert the server closes the socket with `code`.

    Sends a `ping` and reads the reply rather than blocking on `receive_json()` alone.
    If the handshake check is missing, the server answers `pong` and this fails with a
    clear message — verified by reverting the fix. Waiting on a close that never comes
    would hang the suite instead, and a hanging test is worse than a failing one.
    """
    try:
        with client.websocket_connect(url) as ws:
            ws.send_json({"type": "ping"})
            reply = ws.receive_json()
    except WebSocketDisconnect as exc:
        assert exc.code == code, f"closed with {exc.code}, expected {code}"
        return

    pytest.fail(
        f"{url} stayed open and replied {reply!r}; expected close code {code}"
    )


# ============================================================================
# HIVE-017 — the user socket
# ============================================================================

def test_connection_without_a_token_is_rejected(db_returns):
    db_returns(_user(uuid4()))
    client = TestClient(app)
    _closes_with(client, "/ws/client-1", UNAUTHENTICATED)


def test_connection_with_a_tampered_token_is_rejected(db_returns):
    db_returns(_user(uuid4()))
    client = TestClient(app)
    token = create_access_token(uuid4()) + "x"
    _closes_with(client, f"/ws/client-1?token={token}", UNAUTHENTICATED)


def test_connection_with_an_expired_token_is_rejected(db_returns, monkeypatch):
    user_id = uuid4()
    db_returns(_user(user_id))

    from jose import jwt

    from mind.config.settings import settings

    expired = jwt.encode(
        {
            "user_id": str(user_id),
            "exp": datetime.utcnow() - timedelta(hours=1),
            "iat": datetime.utcnow() - timedelta(hours=2),
            "token_type": "access",
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    _closes_with(TestClient(app), f"/ws/c1?token={expired}", UNAUTHENTICATED)


def test_connection_for_an_unknown_user_is_rejected(db_returns):
    db_returns(None)  # valid signature, no such row
    token = create_access_token(uuid4())
    _closes_with(TestClient(app), f"/ws/c1?token={token}", UNAUTHENTICATED)


def test_banned_user_is_rejected(db_returns):
    user_id = uuid4()
    db_returns(_user(user_id, is_banned=True))
    token = create_access_token(user_id)
    _closes_with(TestClient(app), f"/ws/c1?token={token}", UNAUTHENTICATED)


def test_valid_token_connects_and_identity_comes_from_the_token(db_returns):
    """The `auth` frame must echo the token's user, not one the client names."""
    alice, mallory = uuid4(), uuid4()
    db_returns(_user(alice))
    token = create_access_token(alice)

    with TestClient(app).websocket_connect(f"/ws/c1?token={token}") as ws:
        ws.send_json({"type": "auth", "user_id": str(mallory)})
        reply = ws.receive_json()

    assert reply["type"] == "authenticated"
    assert reply["user_id"] == str(alice), "the client's claimed user_id was honoured"


def test_notification_subscription_ignores_a_claimed_user_id(db_returns, monkeypatch):
    """The original leak: subscribe to someone else's notification stream."""
    alice, mallory = uuid4(), uuid4()
    db_returns(_user(alice))

    seen = {}
    service = MagicMock()

    async def _unread(user_id):
        seen["user_id"] = user_id
        return 7

    service.get_unread_count = _unread
    monkeypatch.setattr("mind.api.main.get_notification_service", lambda: service)

    token = create_access_token(alice)
    with TestClient(app).websocket_connect(f"/ws/c1?token={token}") as ws:
        ws.send_json({"type": "subscribe_notifications", "user_id": str(mallory)})
        reply = ws.receive_json()

    assert seen["user_id"] == alice, "unread count was fetched for another user"
    assert reply["user_id"] == str(alice)


# ============================================================================
# HIVE-018 — the admin socket
# ============================================================================

def test_admin_socket_rejects_a_bare_uuid(db_returns):
    """Knowing an admin's UUID used to be the entire credential."""
    admin_id = uuid4()
    db_returns(_user(admin_id, is_admin=True))
    _closes_with(TestClient(app), f"/ws/admin/{admin_id}", UNAUTHENTICATED)


def test_admin_socket_rejects_a_non_admin_token(db_returns):
    user_id = uuid4()
    db_returns(_user(user_id, is_admin=False))
    token = create_access_token(user_id)
    _closes_with(TestClient(app), f"/ws/admin/anything?token={token}", FORBIDDEN)


def test_admin_socket_accepts_an_admin_token(db_returns):
    admin_id = uuid4()
    db_returns(_user(admin_id, is_admin=True))
    token = create_access_token(admin_id)

    with TestClient(app).websocket_connect(f"/ws/admin/x?token={token}") as ws:
        ws.send_json({"type": "ping"})
        assert ws.receive_json()["type"] in ("pong", "engine_stats")
