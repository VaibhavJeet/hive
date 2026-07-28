"""
Civilization authorization tests (HIVE-013).

The civilization router is the observation product: 85 endpoints, none of which had
any auth. 57 of them are reads and are *meant* to be public — VISION.md is explicit
that watching is the point, and the queen portal browses them anonymously.

The other 28 mutate. Anonymous callers could declare a new era, propose and perform
rituals, write beliefs into bots, record life events, reset the civilization's
configuration, or re-run `initialize`. Eleven of them also invoke the LLM, so they were
an unmetered spend endpoint as well as a vandalism one.

This test pins the split by *shape* rather than by listing paths, so a new endpoint
inherits the rule instead of quietly escaping it.
"""

import pytest
from fastapi.testclient import TestClient

from mind.api.main import app
from tests.api.test_auth_coverage import _iter_api_routes, classify

MUTATING = {"POST", "PUT", "DELETE", "PATCH"}


def _civilization_routes():
    return [r for r in _iter_api_routes(app.router) if (r.tags or [""])[0] == "civilization"]


def test_every_mutating_endpoint_requires_admin():
    offenders = [
        f"{','.join(sorted(r.methods - {'HEAD'}))} {r.path}"
        for r in _civilization_routes()
        if (r.methods & MUTATING) and classify(r) != "REQUIRED"
    ]
    assert not offenders, (
        "these civilization endpoints change state without authentication:\n  "
        + "\n  ".join(sorted(offenders))
    )


def test_reads_stay_public():
    """Observation is the product. Gating reads would break the portal and the vision."""
    gated = [
        r.path
        for r in _civilization_routes()
        if not (r.methods & MUTATING) and classify(r) == "REQUIRED"
    ]
    assert not gated, (
        "civilization reads must stay anonymous — this is an observation portal:\n  "
        + "\n  ".join(sorted(gated))
    )


def test_the_split_is_what_we_expect():
    """A count assertion, so adding an endpoint forces a conscious decision."""
    routes = _civilization_routes()
    reads = [r for r in routes if not (r.methods & MUTATING)]
    writes = [r for r in routes if r.methods & MUTATING]

    assert (len(reads), len(writes)) == (57, 28), (
        f"civilization is now {len(reads)} reads / {len(writes)} writes (was 57/28). "
        "Confirm the new endpoint is on the right side of the line, then update this."
    )


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/civilization/initialize"),
        ("post", "/civilization/eras/declare"),
        ("post", "/civilization/eras/propose"),
        ("post", "/civilization/rituals/propose"),
        ("post", "/civilization/rituals/perform"),
        ("put", "/civilization/config"),
        ("post", "/civilization/config/reset"),
        ("post", "/civilization/culture/recognize-pattern"),
        ("post", "/civilization/events/perceive"),
    ],
)
def test_high_impact_mutations_reject_anonymous_callers(method, path):
    """Spot-check the endpoints that rewrite history or reset configuration."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.request(method, path, json={})

    assert response.status_code == 401, (
        f"{method.upper()} {path} returned {response.status_code}, expected 401"
    )


@pytest.mark.parametrize(
    "path",
    [
        "/civilization/stats",
        "/civilization/eras",
        "/civilization/timeline",
        "/civilization/world-map",
        "/civilization/generations",
        "/civilization/social-circles",
    ],
)
def test_observation_endpoints_remain_anonymous(path):
    """These back the public portal; a 401 here is a product regression."""
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get(path).status_code != 401, f"GET {path} now requires auth"
