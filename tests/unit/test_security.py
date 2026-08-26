"""Unit tests for the abuse-control primitives (blueprint section 6). Deliberately not
integration tests against the live gateway: tripping AuthFailThrottle for real blocks the
test-runner's own source IP for LARA_AUTH_FAIL_BLOCK_S, which would break every subsequent
integration test run from this machine - see docs/security/exposure.md for how that was
actually exercised once, on purpose, manually."""

import time

from app.api.security import AuthFailThrottle, RateLimiter


def test_rate_limiter_allows_up_to_the_limit():
    rl = RateLimiter(max_requests=3, window_s=60)
    assert rl.allow("key-a") is True
    assert rl.allow("key-a") is True
    assert rl.allow("key-a") is True
    assert rl.allow("key-a") is False


def test_rate_limiter_is_per_key():
    rl = RateLimiter(max_requests=1, window_s=60)
    assert rl.allow("key-a") is True
    assert rl.allow("key-b") is True, "a different key must not share key-a's budget"
    assert rl.allow("key-a") is False


def test_rate_limiter_window_expires():
    rl = RateLimiter(max_requests=1, window_s=0.05)
    assert rl.allow("key-a") is True
    assert rl.allow("key-a") is False
    time.sleep(0.06)
    assert rl.allow("key-a") is True, "requests older than the window should no longer count"


def test_auth_fail_throttle_blocks_after_threshold():
    t = AuthFailThrottle(threshold=3, window_s=60, block_s=60)
    assert t.is_blocked("src-a") is False
    t.record_failure("src-a")
    t.record_failure("src-a")
    assert t.is_blocked("src-a") is False, "below threshold, not yet blocked"
    t.record_failure("src-a")
    assert t.is_blocked("src-a") is True


def test_auth_fail_throttle_blocks_by_source_not_by_key():
    """A throttled source is blocked entirely, not just for the key that failed - matches the
    real behavior observed manually (docs/security/exposure.md): even a subsequently-valid
    key from a throttled source gets rejected, since AuthFailThrottle only knows about
    sources, never keys."""
    t = AuthFailThrottle(threshold=1, window_s=60, block_s=60)
    t.record_failure("src-a")
    assert t.is_blocked("src-a") is True
    assert t.is_blocked("src-b") is False, "a different source must be unaffected"


def test_auth_fail_throttle_unblocks_after_block_duration():
    t = AuthFailThrottle(threshold=1, window_s=60, block_s=0.05)
    t.record_failure("src-a")
    assert t.is_blocked("src-a") is True
    time.sleep(0.06)
    assert t.is_blocked("src-a") is False


def test_auth_fail_throttle_old_failures_do_not_accumulate_forever():
    t = AuthFailThrottle(threshold=3, window_s=0.05, block_s=60)
    t.record_failure("src-a")
    t.record_failure("src-a")
    time.sleep(0.06)
    t.record_failure("src-a")
    assert t.is_blocked("src-a") is False, "the first two failures should have aged out of the window"
