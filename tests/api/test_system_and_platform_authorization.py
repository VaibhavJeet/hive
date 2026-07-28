"""
System telemetry and platform bootstrap authorization (HIVE-015, HIVE-138).

`/system/*` is operator telemetry, not observation: host CPU, memory, disk and
network, plus the application log buffer — which carries user content, bot output,
and error detail including filesystem paths.

The `platform` endpoints are defined directly on `app` in `main.py` rather than in a
route module, which is why the original audit counted them but filed no task. Three
of them were anonymous and expensive:

    POST /communities            seeds up to 200 bots, each of them LLM work
    POST /platform/initialize    ~10 communities x 50 bots — ~500 generations per call
    POST /bots/{id}/message      memory recall + LLM generation, per request

Anonymous access to those was unmetered inference on the operator's budget, and a
mass-write against the database.
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

ADMIN_ONLY = [
    ("get", "/system/status"),
    ("get", "/system/performance"),
    ("get", "/system/logs"),
    ("post", "/communities"),
    ("post", "/platform/initialize"),
    ("get", "/platform/stats"),
]

PUBLIC_READS = [
    "/communities",
    f"/communities/{uuid4()}",
    f"/communities/{uuid4()}/bots",
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


@pytest.mark.parametrize("method,path", ADMIN_ONLY)
def test_admin_surfaces_reject_anonymous_callers(method, path):
    client = TestClient(app, raise_server_exceptions=False)
    response = client.request(method, path, json={})
    assert response.status_code == 401, f"{method.upper()} {path} was anonymous"


@pytest.mark.parametrize("method,path", ADMIN_ONLY)
def test_admin_surfaces_reject_non_admins(client_as, method, path):
    response = client_as(is_admin=False).request(method, path, json={})
    assert response.status_code == 403, f"{method.upper()} {path} allowed a non-admin"


def test_dm_pipeline_requires_a_session():
    """Every call runs memory recall and an LLM generation."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        f"/bots/{uuid4()}/message",
        json={
            "bot_id": str(uuid4()),
            "conversation_id": "c1",
            "content": "hello",
            "is_direct_message": True,
        },
    )
    assert response.status_code == 401


def test_dm_pipeline_allows_ordinary_users(client_as):
    """It must not become admin-only — messaging a bot is the product."""
    response = client_as(is_admin=False).post(
        f"/bots/{uuid4()}/message",
        json={
            "bot_id": str(uuid4()),
            "conversation_id": "c1",
            "content": "hello",
            "is_direct_message": True,
        },
    )
    assert response.status_code != 403, "a signed-in user was refused the DM pipeline"


@pytest.mark.parametrize("path", PUBLIC_READS)
def test_community_browsing_stays_public(path):
    """Community listings back the portal and the mobile app's discovery screen."""
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get(path).status_code != 401, f"GET {path} now requires auth"


def test_log_buffer_is_not_anonymously_readable():
    """Called out separately: logs are the highest-value target in this router."""
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get("/system/logs?limit=500").status_code == 401
