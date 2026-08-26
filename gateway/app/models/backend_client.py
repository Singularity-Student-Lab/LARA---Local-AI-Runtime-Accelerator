"""Pooled HTTP client for talking to inference backends (blueprint section 3, Session 3
point 7: "one long-lived HTTP client with a connection pool rather than a new connection per
request"). One instance, created at gateway startup, reused for every proxied request."""

from __future__ import annotations

import httpx

from app.config import Settings


def build_backend_client(settings: Settings) -> httpx.AsyncClient:
    timeout = httpx.Timeout(
        connect=settings.lara_connect_timeout_s,
        read=settings.lara_request_timeout_s,
        write=settings.lara_connect_timeout_s,
        pool=settings.lara_connect_timeout_s,
    )
    return httpx.AsyncClient(timeout=timeout)
