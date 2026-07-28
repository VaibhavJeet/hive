"""
Admin authentication tests (HIVE-001).

Covers the acceptance criteria for replacing the unsigned `X-User-ID` admin header
with JWT bearer auth:

    - a request with only `X-User-ID` returns 401
    - a valid non-admin JWT returns 403
    - a valid admin JWT succeeds

The unit under test is the `require_admin` dependency chain, so these tests mount it
on a minimal app rather than driving the real admin routes — that keeps them free of
database and AdminService setup while still exercising the exact dependency the 20
admin routes use.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from mind.api.dependencies import get_db_session
from mind.api.routes.admin import require_admin
from mind.core.auth import create_access_token


def _fake_user(*, user_id, is_admin=False, is_banned=False):
    """A stand-in for an AppUserDB row."""
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


def _session_returning(user):
    """An AsyncSession stub whose scalar_one_or_none() yields `user`."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    return session


def _build_client(user):
    """Minimal app exposing one `require_admin`-protected route."""
    app = FastAPI()

    @app.get("/admin/probe")
    async def probe(admin=Depends(require_admin)):
        return {"admin_id": str(admin.id)}

    async def _override_session():
        yield _session_returning(user)

    # Both the token lookup (mind.api.dependencies.get_current_user) and the admin
    # row lookup resolve their session through this dependency.
    app.dependency_overrides[get_db_session] = _override_session
    return TestClient(app, raise_server_exceptions=False)


# ============================================================================
# ACCEPTANCE CRITERIA
# ============================================================================

def test_x_user_id_header_alone_is_rejected():
    """AC 1: the old auth scheme no longer authenticates anything."""
    admin_id = uuid4()
    client = _build_client(_fake_user(user_id=admin_id, is_admin=True))

    response = client.get("/admin/probe", headers={"X-User-ID": str(admin_id)})

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


def test_valid_non_admin_jwt_is_forbidden():
    """AC 2: authentication succeeds, authorization does not."""
    user_id = uuid4()
    client = _build_client(_fake_user(user_id=user_id, is_admin=False))
    token = create_access_token(user_id)

    response = client.get(
        "/admin/probe", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"


def test_valid_admin_jwt_succeeds():
    """AC 3: an admin token gets through."""
    admin_id = uuid4()
    client = _build_client(_fake_user(user_id=admin_id, is_admin=True))
    token = create_access_token(admin_id)

    response = client.get(
        "/admin/probe", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json() == {"admin_id": str(admin_id)}


# ============================================================================
# REGRESSION GUARDS
# ============================================================================

def test_no_authorization_header_is_rejected():
    client = _build_client(_fake_user(user_id=uuid4(), is_admin=True))
    assert client.get("/admin/probe").status_code == 401


def test_tampered_token_is_rejected():
    admin_id = uuid4()
    client = _build_client(_fake_user(user_id=admin_id, is_admin=True))
    token = create_access_token(admin_id) + "x"

    response = client.get(
        "/admin/probe", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


def test_banned_admin_is_forbidden():
    admin_id = uuid4()
    client = _build_client(
        _fake_user(user_id=admin_id, is_admin=True, is_banned=True)
    )
    token = create_access_token(admin_id)

    response = client.get(
        "/admin/probe", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "User is banned"


def test_admin_x_user_id_scheme_is_gone_from_openapi():
    """The retired header must not reappear as a documented security scheme."""
    from mind.api.main import app

    schemes = app.openapi().get("components", {}).get("securitySchemes", {})

    assert "Admin X-User-ID" not in schemes
    assert "JWT Bearer" in schemes
