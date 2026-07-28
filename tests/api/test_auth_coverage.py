"""
Auth coverage tests (HIVE-004…016).

Gives the project one honest, permanent number for "how much of the API requires
authentication", and locks in per-router expectations so coverage can only move
deliberately.

Three classifications, because the distinction matters and the OpenAPI `security`
field does not make it. An endpoint depending on `get_optional_user` is listed as
secured in the schema but still serves anonymous callers — counting those as
"secured" overstates coverage:

    REQUIRED  rejects anonymous callers (get_current_user / require_admin)
    OPTIONAL  serves anonymous callers, personalises for signed-in ones
    OPEN      no auth in the dependency tree at all
"""

import pytest

from mind.api.dependencies import get_current_user, get_optional_user
from mind.api.main import app
from mind.api.routes.admin import get_current_admin_user, require_admin

REQUIRING = {get_current_user, require_admin, get_current_admin_user}


def _iter_api_routes(router, _seen=None):
    """Walk nested routers.

    This FastAPI version does not flatten `include_router` into `app.routes`; it
    inserts a `_IncludedRouter` wrapper that holds the real router on
    `.original_router`. Walking only `app.routes` finds 9 of ~250 endpoints, which is
    exactly the kind of undercount that makes a coverage metric worse than none.
    """
    if _seen is None:
        _seen = set()
    if id(router) in _seen:
        return
    _seen.add(id(router))

    for route in getattr(router, "routes", []):
        if hasattr(route, "dependant") and hasattr(route, "methods"):
            yield route
        for attr in ("original_router", "router", "app"):
            inner = getattr(route, attr, None)
            if inner is not None and hasattr(inner, "routes"):
                yield from _iter_api_routes(inner, _seen)


def _dependency_calls(dependant):
    seen, stack, found = set(), [dependant], set()
    while stack:
        node = stack.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        if node.call is not None:
            found.add(node.call)
        stack.extend(node.dependencies)
    return found


def classify(route):
    calls = _dependency_calls(route.dependant)
    if calls & REQUIRING:
        return "REQUIRED"
    if get_optional_user in calls:
        return "OPTIONAL"
    return "OPEN"


def coverage_by_tag():
    result = {}
    for route in _iter_api_routes(app.router):
        tag = (route.tags or ["untagged"])[0]
        bucket = result.setdefault(tag, {"REQUIRED": 0, "OPTIONAL": 0, "OPEN": 0})
        bucket[classify(route)] += 1
    return result


# Baseline recorded 28-07-2026, after HIVE-003 and HIVE-004.
#
# `open_max` is a ratchet: a router may only ever have FEWER open endpoints than
# this. Lower the number when you close a task; the test fails if it drifts up,
# and also if it drifts down without the number being updated — so progress has to
# be recorded rather than silently absorbed.
EXPECTED_OPEN = {
    # Fully closed by HIVE-003 / HIVE-004 — these must never go up.
    "admin": 0,
    "blocking": 0,
    "chat": 0,
    "feed": 0,
    "moderation": 0,
    "settings": 0,
    "stories": 0,
    # Intentionally open.
    "auth": 4,               # register / login / refresh / logout
    "health": 6,             # liveness / readiness / component probes
    "notifications": 1,      # /push/config serves the public VAPID key
    # Open by task, with the owning task noted. Lower these as each one closes.
    "hashtags": 3,           # HIVE-016
    "media": 3,              # HIVE-011 — public file serving
    "users": 4,              # register + bot/community browsing (public by design)
    "analytics": 1,          # HIVE-015
    "analytics-dashboard": 1,
    "system": 3,             # HIVE-015
    "search": 5,             # HIVE-016
    "platform": 7,           # HIVE-015
    "evolution": 8,          # HIVE-014
    "civilization": 57,      # reads are the observation product; 28 writes closed by HIVE-013
}


def test_every_router_is_accounted_for():
    """A new router must be added to the ratchet deliberately, not appear unnoticed."""
    unknown = set(coverage_by_tag()) - set(EXPECTED_OPEN)
    assert not unknown, f"routers missing from EXPECTED_OPEN: {sorted(unknown)}"


@pytest.mark.parametrize("tag", sorted(EXPECTED_OPEN))
def test_open_endpoint_count_matches_the_ratchet(tag):
    counts = coverage_by_tag().get(tag)
    if counts is None:
        pytest.skip(f"router '{tag}' is not mounted")

    expected = EXPECTED_OPEN[tag]
    actual = counts["OPEN"]

    assert actual <= expected, (
        f"'{tag}' gained unauthenticated endpoints: {actual} open, expected <= {expected}"
    )
    assert actual == expected, (
        f"'{tag}' now has {actual} open endpoints (was {expected}) — good, "
        f"lower EXPECTED_OPEN['{tag}'] to {actual} to lock it in"
    )


def test_fully_closed_routers_stay_closed():
    """Routers closed by HIVE-003/004 must never regain an anonymous endpoint.

    `notifications` is deliberately excluded: /push/config serves the public VAPID
    key, which every client needs before it can subscribe.
    """
    coverage = coverage_by_tag()
    for tag in ("admin", "blocking", "chat", "feed", "moderation", "settings", "stories"):
        counts = coverage.get(tag)
        if counts is None:
            continue
        assert counts["OPEN"] == 0, (
            f"'{tag}' has {counts['OPEN']} unauthenticated endpoints; it was fully closed"
        )


def test_overall_coverage_is_reported(capsys):
    """Not an assertion — prints the table so `pytest -s` gives the current picture."""
    coverage = coverage_by_tag()
    totals = {"REQUIRED": 0, "OPTIONAL": 0, "OPEN": 0}

    lines = ["", "%-22s %9s %9s %6s" % ("router", "required", "optional", "open")]
    for tag, counts in sorted(coverage.items()):
        for key in totals:
            totals[key] += counts[key]
        lines.append(
            "%-22s %9d %9d %6d" % (tag, counts["REQUIRED"], counts["OPTIONAL"], counts["OPEN"])
        )
    lines.append(
        "%-22s %9d %9d %6d"
        % ("TOTAL", totals["REQUIRED"], totals["OPTIONAL"], totals["OPEN"])
    )
    print("\n".join(lines))

    assert totals["REQUIRED"] + totals["OPTIONAL"] + totals["OPEN"] > 0
