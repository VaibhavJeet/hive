"""
Rate limiter tests (HIVE-026).

The original lived in `main.py` as a `defaultdict(list)` of timestamps keyed by client
IP. Three defects:

    per-process   with API_WORKERS=4 the effective limit was 4x the configured one,
                  and which worker you hit decided whether you were throttled
    unbounded     entries were pruned only for an IP making a *new* request, so any IP
                  seen once kept its list forever — a scan grew the dict without limit
    volatile      a deploy reset everyone's budget

It also trusted `X-Forwarded-For` unconditionally, so a caller could spoof the header
and reset their own budget — which made the limiter optional for anyone who read the
source.
"""

import time

import pytest

from mind.core.rate_limit import RateLimiter, _LocalWindow


@pytest.fixture
def limiter(monkeypatch):
    """A limiter with Redis forced off, exercising the local fallback."""
    rl = RateLimiter(requests_per_minute=5, burst_limit=3)

    async def _no_redis():
        return None

    monkeypatch.setattr(rl, "_redis", _no_redis)
    return rl


# ============================================================================
# The fallback is bounded — the original was not
# ============================================================================

def test_local_window_evicts_least_recently_used():
    window = _LocalWindow(max_clients=10)
    now = time.time()

    for i in range(50):
        window.record(f"client-{i}", now, 60.0)

    assert len(window._hits) <= 10, (
        f"tracked {len(window._hits)} clients with a cap of 10 — an unbounded dict is "
        "how the original grew without limit"
    )


def test_local_window_keeps_recent_clients():
    window = _LocalWindow(max_clients=3)
    now = time.time()

    window.record("keep", now, 60.0)
    for i in range(3):
        window.record(f"filler-{i}", now, 60.0)
        window.record("keep", now, 60.0)  # keeps it recently-used

    assert "keep" in window._hits


def test_old_timestamps_leave_the_window():
    window = _LocalWindow()
    now = time.time()

    window.record("c", now - 120, 60.0)
    count = window.record("c", now, 60.0)

    assert count == 1, "a timestamp older than the window was still counted"


# ============================================================================
# Limits are enforced
# ============================================================================

@pytest.mark.asyncio
async def test_requests_under_the_limit_are_allowed(monkeypatch):
    """Burst and per-minute are separate limits, so isolate them.

    My first version used the shared fixture (burst 3) and sent 5 requests in the same
    second — the burst limit tripped first. That was the test conflating two controls,
    not the limiter misbehaving.
    """
    rl = RateLimiter(requests_per_minute=5, burst_limit=100)

    async def _no_redis():
        return None

    monkeypatch.setattr(rl, "_redis", _no_redis)

    for _ in range(5):
        allowed, _, _ = await rl.check("1.2.3.4")
        assert allowed


@pytest.mark.asyncio
async def test_per_minute_limit_trips(monkeypatch):
    """With burst effectively disabled, the minute window is what stops the sixth."""
    rl = RateLimiter(requests_per_minute=5, burst_limit=100)

    async def _no_redis():
        return None

    monkeypatch.setattr(rl, "_redis", _no_redis)

    results = [await rl.check("1.2.3.4") for _ in range(7)]
    assert any(not allowed for allowed, _, _ in results)
    _, reason, retry_after = next(r for r in results if not r[0])
    assert "rate limit" in reason.lower()
    assert retry_after == 60


@pytest.mark.asyncio
async def test_burst_limit_trips(limiter):
    results = [await limiter.check("1.2.3.4") for _ in range(6)]
    assert any(not allowed for allowed, _, _ in results)

    _, reason, retry_after = next(r for r in results if not r[0])
    assert "slow down" in reason.lower()
    assert retry_after == 1


@pytest.mark.asyncio
async def test_clients_are_counted_separately(limiter):
    for _ in range(5):
        await limiter.check("1.1.1.1")

    allowed, _, _ = await limiter.check("2.2.2.2")
    assert allowed, "one client's traffic throttled another"


@pytest.mark.asyncio
async def test_a_rejection_carries_retry_after(limiter):
    for _ in range(20):
        allowed, reason, retry_after = await limiter.check("1.2.3.4")
        if not allowed:
            assert retry_after > 0
            assert reason
            return
    pytest.fail("limit never tripped")


# ============================================================================
# X-Forwarded-For is not trusted by default
# ============================================================================

def test_forwarded_header_is_ignored_unless_explicitly_trusted(monkeypatch):
    from mind.api.main import RateLimitMiddleware
    from mind.config.settings import settings

    middleware = RateLimitMiddleware(app=None)

    class _Request:
        headers = {"X-Forwarded-For": "9.9.9.9"}

        class client:
            host = "10.0.0.1"

    monkeypatch.setattr(settings, "TRUSTED_PROXY_HEADERS", False)
    assert middleware._identity(_Request()) == "10.0.0.1", (
        "a spoofed X-Forwarded-For would let a caller reset their own budget"
    )

    monkeypatch.setattr(settings, "TRUSTED_PROXY_HEADERS", True)
    assert middleware._identity(_Request()) == "9.9.9.9"


def test_the_default_is_not_to_trust_proxies():
    from mind.config.settings import settings

    assert settings.TRUSTED_PROXY_HEADERS is False


# ============================================================================
# Liveness must not be throttled
# ============================================================================

def test_health_is_exempt():
    """Throttling /health makes an overloaded server look dead and get restarted."""
    from mind.api.main import RateLimitMiddleware

    assert "/health" in RateLimitMiddleware.EXEMPT_PATHS
    assert "/health/detailed" in RateLimitMiddleware.EXEMPT_PATHS
