"""
Chat authorization tests (HIVE-005).

HIVE-003 gave the chat router authentication. Authentication is not authorization:
`GET /chat/dm/{conversation_id}` still filtered on the conversation id alone, and
conversation ids are derivable — `send_direct_message` builds them as
`f"{min(id_a, id_b)}_{max(id_a, id_b)}"`, and bot UUIDs are public via
`/communities/{id}/bots`. Any signed-in user could read any private thread.

These tests pin the participation requirement.
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
    """A TestClient signed in as `user_id`, with the token's DB lookup stubbed."""
    def _factory(user_id):
        result = MagicMock()
        result.scalar_one_or_none.return_value = _token_user(user_id)
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


def _conversation_id(a, b):
    """Mirrors send_direct_message — this derivability is the whole point."""
    ids = sorted([str(a), str(b)])
    return f"{ids[0]}_{ids[1]}"


class _FakeSession:
    """Session stub that records the statements the handler issues."""

    def __init__(self, participation_rows):
        self.participation_rows = participation_rows
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        result = MagicMock()
        result.first.return_value = self.participation_rows
        result.scalars.return_value.all.return_value = []
        result.scalar_one_or_none.return_value = None
        return result

    async def commit(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def test_outsider_cannot_read_a_derivable_conversation(client_as, monkeypatch):
    """The attack: build the id from two public UUIDs and ask for the thread."""
    alice, bob, mallory = uuid4(), uuid4(), uuid4()
    conversation = _conversation_id(alice, bob)

    # No row in this conversation involves Mallory.
    fake = _FakeSession(participation_rows=None)
    monkeypatch.setattr(
        "mind.api.routes.chat.async_session_factory", lambda: fake
    )

    client = client_as(mallory)
    response = client.get(f"/chat/dm/{conversation}")

    assert response.status_code == 404, (
        "a non-participant must not be able to read the thread"
    )
    # 404 rather than 403: the status code must not reveal that the thread exists.
    assert "not found" in response.text.lower()


def test_participant_can_read_their_own_conversation(client_as, monkeypatch):
    alice, bob = uuid4(), uuid4()
    conversation = _conversation_id(alice, bob)

    fake = _FakeSession(participation_rows=(uuid4(),))  # Alice is a participant
    monkeypatch.setattr(
        "mind.api.routes.chat.async_session_factory", lambda: fake
    )

    client = client_as(alice)
    response = client.get(f"/chat/dm/{conversation}")

    assert response.status_code == 200
    assert response.json() == []


def test_message_query_is_scoped_to_the_caller(client_as, monkeypatch):
    """Defence in depth: the message SELECT itself filters on sender/receiver."""
    alice, bob = uuid4(), uuid4()
    conversation = _conversation_id(alice, bob)

    fake = _FakeSession(participation_rows=(uuid4(),))
    monkeypatch.setattr(
        "mind.api.routes.chat.async_session_factory", lambda: fake
    )

    client = client_as(alice)
    client.get(f"/chat/dm/{conversation}")

    # Both the participation probe and the message SELECT must name the caller.
    assert len(fake.statements) >= 2
    for statement in fake.statements[:2]:
        assert str(alice) in str(statement.compile(compile_kwargs={"literal_binds": True})), (
            "query was not scoped to the authenticated caller"
        )


def test_dm_endpoints_reject_anonymous_callers():
    client = TestClient(app, raise_server_exceptions=False)
    conversation = _conversation_id(uuid4(), uuid4())

    assert client.get(f"/chat/dm/{conversation}").status_code == 401
    assert client.get("/chat/dm/conversations").status_code == 401
    assert client.post("/chat/dm", json={"receiver_id": str(uuid4()), "content": "hi"}).status_code == 401
