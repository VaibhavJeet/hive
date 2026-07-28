"""
Push subscription ownership tests (HIVE-009).

`PushService.register_device` looked its row up by **endpoint alone** and, on a match,
reassigned `user_id` to the caller. Submitting another user's endpoint therefore took
over their subscription: the victim silently stopped receiving push notifications, and
the attacker's notifications were delivered to the victim's device.

A transfer *is* legitimate on a shared device, so the fix is not to forbid it — it is
to require the caller to present the subscription's own keys, which the browser hands
only to the origin. The endpoint on its own is not proof of control.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from mind.notifications.push_service import PushService

ALICE_KEYS = {"p256dh": "alice-p256dh", "auth": "alice-auth"}
ENDPOINT = "https://push.example.com/subscription/alice-device"


class _Session:
    def __init__(self, existing=None):
        self.existing = existing
        self.added = []

    async def execute(self, statement):
        result = MagicMock()
        result.scalar_one_or_none.return_value = self.existing
        return result

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def service_with(monkeypatch):
    def _factory(session):
        monkeypatch.setattr(
            "mind.notifications.push_service.async_session_factory", lambda: session
        )
        return PushService()

    return _factory


def _existing_row(owner_id, keys):
    return SimpleNamespace(
        id=uuid4(),
        user_id=owner_id,
        endpoint=ENDPOINT,
        keys=keys,
        created_at=datetime(2026, 1, 1),
    )


@pytest.mark.asyncio
async def test_cannot_take_over_another_users_endpoint(service_with):
    """The attack: submit Alice's endpoint with keys you do not have."""
    alice, mallory = uuid4(), uuid4()
    row = _existing_row(alice, ALICE_KEYS)
    session = _Session(existing=row)
    service = service_with(session)

    with pytest.raises(PermissionError):
        await service.register_device(
            user_id=mallory,
            subscription={
                "endpoint": ENDPOINT,
                "keys": {"p256dh": "guessed", "auth": "guessed"},
            },
        )

    assert row.user_id == alice, "the subscription was reassigned to the attacker"


@pytest.mark.asyncio
async def test_cannot_take_over_by_omitting_keys(service_with):
    alice, mallory = uuid4(), uuid4()
    row = _existing_row(alice, ALICE_KEYS)
    session = _Session(existing=row)
    service = service_with(session)

    with pytest.raises(PermissionError):
        await service.register_device(
            user_id=mallory, subscription={"endpoint": ENDPOINT, "keys": {}}
        )

    assert row.user_id == alice


@pytest.mark.asyncio
async def test_shared_device_transfer_with_matching_keys_is_allowed(service_with):
    """The legitimate case the original code was written for must keep working."""
    alice, bob = uuid4(), uuid4()
    row = _existing_row(alice, ALICE_KEYS)
    session = _Session(existing=row)
    service = service_with(session)

    await service.register_device(
        user_id=bob, subscription={"endpoint": ENDPOINT, "keys": dict(ALICE_KEYS)}
    )

    assert row.user_id == bob, "a genuine shared-device transfer was blocked"


@pytest.mark.asyncio
async def test_same_user_reregistering_refreshes_keys(service_with):
    alice = uuid4()
    row = _existing_row(alice, ALICE_KEYS)
    session = _Session(existing=row)
    service = service_with(session)

    rotated = {"p256dh": "rotated", "auth": "rotated"}
    await service.register_device(
        user_id=alice, subscription={"endpoint": ENDPOINT, "keys": rotated}
    )

    assert row.user_id == alice
    assert row.keys == rotated


@pytest.mark.asyncio
async def test_new_endpoint_creates_a_row(service_with):
    alice = uuid4()
    session = _Session(existing=None)
    service = service_with(session)

    await service.register_device(
        user_id=alice, subscription={"endpoint": ENDPOINT, "keys": ALICE_KEYS}
    )

    assert len(session.added) == 1
    assert session.added[0].user_id == alice
