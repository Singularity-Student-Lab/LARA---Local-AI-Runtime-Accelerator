"""API key generation and verification (blueprint section 3.4 point 4 / section 21.4).

Format: lara_<key_id>.<secret>
  key_id  12-char url-safe random identifier, stored in plaintext, unique, indexed.
  secret  32 bytes of CSPRNG entropy, url-safe encoded, never stored.

The separator between key_id and secret is "." rather than "_", deliberately: both key_id and
secret come from secrets.token_urlsafe(), whose alphabet [A-Za-z0-9-_] itself includes "_".
Splitting on "_" would misparse any key whose id or secret happens to contain one (found via
a real failing integration test, not by inspection) - "." is disjoint from that alphabet, so
splitting on the first "." after the "lara_" prefix is unambiguous.

Verification uses HMAC-SHA256 with a server-side pepper (LARA_API_KEY_PEPPER), not a slow
password KDF: the secret already has full entropy, so a slow KDF would add per-request
latency without adding protection (blueprint section 3.4, Engineering Note). Comparison is
constant-time via hmac.compare_digest.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

KEY_PREFIX = "lara"


def generate_key_id() -> str:
    return secrets.token_urlsafe(9)  # 12 chars, url-safe


def generate_secret() -> str:
    return secrets.token_urlsafe(32)


def hash_secret(secret: str, pepper: str) -> str:
    return hmac.new(pepper.encode("utf-8"), secret.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_secret(secret: str, secret_hash: str, pepper: str) -> bool:
    computed = hash_secret(secret, pepper)
    return hmac.compare_digest(computed, secret_hash)


def format_key(key_id: str, secret: str) -> str:
    return f"{KEY_PREFIX}_{key_id}.{secret}"


def parse_key(raw_key: str) -> tuple[str, str] | None:
    """Returns (key_id, secret) or None if the format is invalid. Never raises on bad input -
    malformed keys must fail auth uniformly, not with a stack trace (blueprint section 5,
    Testing table T-S3-03)."""
    prefix = f"{KEY_PREFIX}_"
    if not raw_key.startswith(prefix):
        return None
    rest = raw_key[len(prefix) :]
    key_id, sep, secret = rest.partition(".")
    if not sep or not key_id or not secret:
        return None
    return key_id, secret


def issue_key() -> tuple[str, str, str]:
    """Returns (key_id, secret, raw_key). The raw_key is shown exactly once by the caller."""
    key_id = generate_key_id()
    secret = generate_secret()
    return key_id, secret, format_key(key_id, secret)
