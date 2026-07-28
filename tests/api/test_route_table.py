"""
Route table integrity tests (HIVE-133, HIVE-135).

FastAPI matches routes in registration order. A literal path registered *after* a
same-shape parameterised path is therefore unreachable — the parameterised route wins
and the request fails on type coercion instead, usually as a 422 that looks like a
client error.

Nothing in this repo guarded against that, and it had happened four times:

    GET    /users/blocked            <- /users/{user_id}              (HIVE-133)
    DELETE /notifications/subscribe  <- /notifications/{notification_id}
    GET    /moderation/reports/counts<- /moderation/reports/{report_id}
    GET    /admin/bots/retired       <- /admin/bots/{bot_id}  (across two routers)

All four were dead endpoints nobody noticed, because the portal did not build
(HIVE-131) and no test exercised them. These tests make the next one fail loudly.
"""

import pytest

from mind.api.main import app
from tests.api.test_auth_coverage import _iter_api_routes


def _segments(path):
    return path.strip("/").split("/")


def _shadowing_pairs():
    """(later, earlier) pairs where an earlier parameterised route swallows a literal."""
    routes = list(_iter_api_routes(app.router))
    pairs = []

    for index, later in enumerate(routes):
        for earlier in routes[:index]:
            if not (later.methods & earlier.methods):
                continue
            if earlier.path == later.path:
                continue
            earlier_segments = _segments(earlier.path)
            later_segments = _segments(later.path)
            if len(earlier_segments) != len(later_segments):
                continue

            matches = True
            param_covers_literal = False
            for a, b in zip(earlier_segments, later_segments):
                if a == b:
                    continue
                if a.startswith("{") and not b.startswith("{"):
                    param_covers_literal = True
                    continue
                matches = False
                break

            if matches and param_covers_literal:
                pairs.append((later, earlier))
                break

    return pairs


def _duplicate_registrations():
    """(path, methods) registered more than once — every registration after the first is dead."""
    seen = {}
    duplicates = []
    for route in _iter_api_routes(app.router):
        for method in route.methods - {"HEAD", "OPTIONS"}:
            key = (method, route.path)
            if key in seen:
                duplicates.append(key)
            else:
                seen[key] = route
    return duplicates


# Duplicate registrations that are known and tracked, with the task that owns them.
# This is an allowlist, not an exemption: shrink it, never grow it.
KNOWN_DUPLICATES = {
    # HIVE-050 — report_system.py and reporting.py both register these paths, so the
    # second implementation is unreachable. Resolving it means choosing which of the
    # two overlapping report systems survives, which is a design decision, not a
    # reordering. Deliberately not silently "fixed" here.
    ("GET", "/moderation/reports"),
    ("GET", "/moderation/reports/{report_id}"),
}


def test_no_route_is_shadowed_by_an_earlier_parameterised_path():
    offenders = [
        f"{','.join(sorted(later.methods - {'HEAD'}))} {later.path}"
        f"  (unreachable — matched first by {earlier.path})"
        for later, earlier in _shadowing_pairs()
    ]
    assert not offenders, (
        "these routes can never be reached; register the literal path before the "
        "parameterised one:\n  " + "\n  ".join(offenders)
    )


def test_no_unexpected_duplicate_registrations():
    duplicates = {(method, path) for method, path in _duplicate_registrations()}
    unexpected = duplicates - KNOWN_DUPLICATES
    assert not unexpected, (
        "the second registration of each of these is dead code:\n  "
        + "\n  ".join(f"{m} {p}" for m, p in sorted(unexpected))
    )


def test_known_duplicates_still_exist():
    """Stops the allowlist from rotting once HIVE-050 lands."""
    duplicates = {(method, path) for method, path in _duplicate_registrations()}
    resolved = KNOWN_DUPLICATES - duplicates
    assert not resolved, (
        f"these duplicates are gone — remove them from KNOWN_DUPLICATES: {sorted(resolved)}"
    )


# ============================================================================
# HEALTH PROBES (HIVE-135)
# ============================================================================

def test_liveness_probe_is_the_cheap_one():
    """`/health` must be a liveness probe, not a readiness probe.

    metrics_router registered its component check at `/health` and, being included
    before the app-level route, shadowed it. A liveness probe pointed at `/health`
    therefore queried Postgres and the LLM on every poll and returned 503 whenever
    either was down — turning a dependency blip into a container restart loop.
    """
    from fastapi.testclient import TestClient

    response = TestClient(app, raise_server_exceptions=False).get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    # A liveness probe reports process health only — no component fan-out.
    assert "checks" not in body, "/health is running component checks; that is readiness"


def test_health_endpoints_do_not_500_without_lifespan():
    """A health endpoint must report unhealthy, never crash."""
    from fastapi.testclient import TestClient

    client = TestClient(app, raise_server_exceptions=False)
    for path in ("/health", "/health/detailed"):
        assert client.get(path).status_code != 500, f"{path} crashed"
