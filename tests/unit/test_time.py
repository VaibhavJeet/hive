"""
Time helper tests (HIVE-036).

`datetime.utcnow()` is deprecated from 3.12 and appeared 360 times across 70 files.
The obvious swap to `datetime.now(timezone.utc)` would have been actively harmful: all
65 DateTime columns in the schema are naive, so half-migrated code raises
`TypeError: can't compare offset-naive and offset-aware datetimes` wherever the two
meet.

These tests pin the property that makes the current step safe — the helper returns the
same naive value the deprecated call did — and the property that makes the next step
possible: there is exactly one place to change.
"""

from datetime import datetime, timezone

from mind.core.time import aware_utcnow, utcnow


def test_utcnow_is_naive():
    """Naive on purpose: it must stay comparable with the legacy columns."""
    assert utcnow().tzinfo is None


def test_utcnow_matches_the_deprecated_call():
    delta = abs((utcnow() - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds())
    assert delta < 5, "helper drifted from the value datetime.utcnow() produced"


def test_utcnow_is_utc_not_local():
    """The bug this prevents: swapping in datetime.now() and silently storing local time."""
    delta = abs((utcnow() - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds())
    assert delta < 5


def test_aware_variant_is_aware():
    assert aware_utcnow().tzinfo is not None
    assert aware_utcnow().utcoffset().total_seconds() == 0


def test_the_two_agree_on_the_instant():
    delta = abs((aware_utcnow().replace(tzinfo=None) - utcnow()).total_seconds())
    assert delta < 5


def test_no_deprecated_calls_remain_in_the_package():
    """The migration is only safe if it is complete — a stray call reintroduces the
    deprecation and, worse, a second source of truth for 'now'."""
    import os
    import re

    offenders = []
    for root, dirs, files in os.walk("mind"):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name).replace(os.sep, "/")
            if path == "mind/core/time.py":
                continue  # documents the old call by name
            source = open(path, encoding="utf-8").read()
            # Ignore matches inside comments and docstrings.
            code = re.sub(r'(""".*?"""|\'\'\'.*?\'\'\'|#[^\n]*)', "", source, flags=re.S)
            if "datetime.utcnow()" in code:
                offenders.append(path)

    assert not offenders, f"datetime.utcnow() still called in: {offenders}"
