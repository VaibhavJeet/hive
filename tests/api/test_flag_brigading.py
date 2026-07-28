"""
Flag brigading tests (HIVE-008).

`POST /bots/{bot_id}/flag` auto-pauses a bot once it accumulates
`AUTO_PAUSE_THRESHOLD` (5) pending flags. Two defects made that a one-account
denial-of-service:

    1. nothing stopped the same reporter filing repeatedly, and
    2. the counter counted flag *rows*, not distinct reporters.

So five requests from one authenticated account silenced any bot in the
civilization until an admin cleared the flags. On an observation product, silencing
bots is the primary vandalism vector.

These tests exercise the service directly — the auto-pause rule lives there, and
routing it through HTTP would only add fixture noise.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from mind.blocking.flagging_service import AUTO_PAUSE_THRESHOLD, FlaggingService


class _Recorder:
    """Session stub that models one bot, one reporter, and a growing flag table."""

    def __init__(self, pending_for_reporter=None, distinct_reporters=0):
        self.pending_for_reporter = pending_for_reporter
        self.distinct_reporters = distinct_reporters
        self.added = []
        self.count_statements = []
        self.bot = SimpleNamespace(
            id=uuid4(), display_name="Bot", is_paused=False, paused_at=None
        )
        self.reporter = SimpleNamespace(id=uuid4())
        self._calls = 0

    async def execute(self, statement):
        self._calls += 1
        result = MagicMock()
        text = str(statement).lower()

        if "count" in text:
            self.count_statements.append(statement)
            result.scalar.return_value = self.distinct_reporters
            return result

        # Call order in flag_behavior: bot lookup, reporter lookup, duplicate probe.
        if self._calls == 1:
            result.scalar_one_or_none.return_value = self.bot
        elif self._calls == 2:
            result.scalar_one_or_none.return_value = self.reporter
        else:
            result.scalar_one_or_none.return_value = self.pending_for_reporter
        return result

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        pass

    async def refresh(self, obj):
        if not getattr(obj, "id", None):
            obj.id = uuid4()
        if not getattr(obj, "created_at", None):
            obj.created_at = datetime(2026, 1, 1)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def service_with(monkeypatch):
    def _factory(session):
        monkeypatch.setattr(
            "mind.blocking.flagging_service.async_session_factory", lambda: session
        )
        return FlaggingService()

    return _factory


@pytest.mark.asyncio
async def test_second_pending_flag_from_the_same_reporter_is_rejected(service_with):
    existing = SimpleNamespace(
        id=uuid4(), flag_type="spam", created_at=datetime(2026, 1, 1)
    )
    session = _Recorder(pending_for_reporter=existing)
    service = service_with(session)

    result = await service.flag_behavior(
        bot_id=session.bot.id, reporter_id=session.reporter.id, flag_type="spam"
    )

    assert result["status"] == "already_flagged"
    assert result["flag_id"] == str(existing.id)
    assert not session.added, "a duplicate flag row was written"


@pytest.mark.asyncio
async def test_first_flag_from_a_reporter_is_accepted(service_with):
    session = _Recorder(pending_for_reporter=None, distinct_reporters=1)
    service = service_with(session)

    result = await service.flag_behavior(
        bot_id=session.bot.id, reporter_id=session.reporter.id, flag_type="spam"
    )

    assert result["status"] == "flagged"
    assert len(session.added) == 1
    assert not session.bot.is_paused


@pytest.mark.asyncio
async def test_one_reporter_at_threshold_volume_cannot_auto_pause(service_with):
    """The brigading case: many pending rows, but only one distinct reporter."""
    session = _Recorder(pending_for_reporter=None, distinct_reporters=1)
    service = service_with(session)

    result = await service.flag_behavior(
        bot_id=session.bot.id, reporter_id=session.reporter.id, flag_type="spam"
    )

    assert not session.bot.is_paused, "a single reporter auto-paused a bot"
    assert "auto_paused" not in result


@pytest.mark.asyncio
async def test_enough_distinct_reporters_still_auto_pauses(service_with):
    """The fix must not disable the feature it protects."""
    session = _Recorder(
        pending_for_reporter=None, distinct_reporters=AUTO_PAUSE_THRESHOLD
    )
    service = service_with(session)

    result = await service.flag_behavior(
        bot_id=session.bot.id, reporter_id=session.reporter.id, flag_type="spam"
    )

    assert session.bot.is_paused
    assert result["auto_paused"] is True
    assert result["pending_flag_count"] == AUTO_PAUSE_THRESHOLD


@pytest.mark.asyncio
async def test_auto_pause_counts_distinct_reporters_in_sql(service_with):
    """Assert on the emitted SQL, not on the source text.

    An earlier version of this test grepped the method source for "distinct" and
    passed against reverted code, because the word survived in the docstring. The
    generated statement is the only thing that cannot lie.
    """
    session = _Recorder(pending_for_reporter=None, distinct_reporters=1)
    service = service_with(session)

    await service.flag_behavior(
        bot_id=session.bot.id, reporter_id=session.reporter.id, flag_type="spam"
    )

    assert session.count_statements, "no count query was issued"
    sql = str(session.count_statements[0].compile()).lower()
    assert "distinct" in sql, (
        f"auto-pause counts flag rows, not distinct reporters, so one account can "
        f"silence any bot (HIVE-008). SQL was: {sql}"
    )
    assert "reporter_id" in sql
