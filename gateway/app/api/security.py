"""Abuse controls for Session 6 (blueprint section 6, "Abuse controls"): per-key request-rate
limiting and failed-authentication throttling. Both are in-process counters - a single
gateway process serving ~12 users needs no external store for this
(ENGINEERING RECOMMENDATION, blueprint section 6 point 4: "Do not introduce Redis for rate
limiting.")."""

from __future__ import annotations

import hashlib
import time
from collections import defaultdict, deque

from starlette.requests import Request


class RateLimiter:
    """Fixed-window counter per key. PRD 9.6: this limits request ARRIVALS, not a user's total
    useful work - no daily/monthly token quota exists anywhere in this codebase."""

    def __init__(self, *, max_requests: int, window_s: float) -> None:
        self.max_requests = max_requests
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key_id: str) -> bool:
        now = time.monotonic()
        hits = self._hits[key_id]
        while hits and now - hits[0] > self.window_s:
            hits.popleft()
        if len(hits) >= self.max_requests:
            return False
        hits.append(now)
        return True


class AuthFailThrottle:
    """Blocks a source after too many authentication failures in a window. Source is a salted
    hash of the client IP (blueprint section 3, "store a salted hash, not the raw address")."""

    def __init__(self, *, threshold: int, window_s: float, block_s: float) -> None:
        self.threshold = threshold
        self.window_s = window_s
        self.block_s = block_s
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._blocked_until: dict[str, float] = {}

    def is_blocked(self, source: str) -> bool:
        until = self._blocked_until.get(source)
        if until is None:
            return False
        if time.monotonic() >= until:
            del self._blocked_until[source]
            return False
        return True

    def record_failure(self, source: str) -> None:
        now = time.monotonic()
        fails = self._failures[source]
        fails.append(now)
        while fails and now - fails[0] > self.window_s:
            fails.popleft()
        if len(fails) >= self.threshold:
            self._blocked_until[source] = now + self.block_s
            fails.clear()


def client_source_hash(request: Request, *, trust_proxy_headers: bool, pepper: str) -> str:
    """Only trusts X-Forwarded-For when all public traffic arrives through a single known
    proxy (the tunnel) - otherwise a client could spoof the header to evade throttling
    (blueprint section 6 Security Considerations point 5)."""
    if trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"
    else:
        ip = request.client.host if request.client else "unknown"
    return hashlib.sha256(f"{pepper}:{ip}".encode()).hexdigest()
