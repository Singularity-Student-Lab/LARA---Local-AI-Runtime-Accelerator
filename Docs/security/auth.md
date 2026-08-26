# Authentication and Authorization

Implements blueprint Session 3. Verified for real against the running compose stack on this
dev machine on 2026-08-12 (`tests/integration/test_auth.py`, 13/13 passing).

## Key format

```text
lara_<key_id>.<secret>
```

`key_id` is a 12-char url-safe random identifier (plaintext, indexed). `secret` is 32 bytes of
CSPRNG entropy, url-safe encoded, never stored — only its HMAC-SHA256(pepper) hash is.

**A real bug was found and fixed while building this**, not merely by inspection: the
original format used `_` as the delimiter between `key_id` and `secret`. Both come from
Python's `secrets.token_urlsafe()`, whose own alphabet includes `_` — so a key whose id or
secret happened to contain an underscore was silently misparsed, causing valid keys to be
rejected as unauthenticated. A generated integration-test key hit this within the first test
run. Fixed by switching the internal separator to `.`, which is disjoint from
`token_urlsafe`'s alphabet (`gateway/app/auth/keys.py`, regression test in
`tests/unit/test_auth_keys.py::test_parse_handles_underscore_in_key_id_or_secret`).

## Verification: HMAC, not a slow KDF

`hash_secret()` uses HMAC-SHA256 with a server-side pepper (`LARA_API_KEY_PEPPER`), not
Argon2/bcrypt. The secret already has full CSPRNG entropy, so a slow KDF would add per-request
latency to every inference call without adding protection — the slow-KDF budget is reserved for
human passwords (which this repo does not implement a login flow for in V1; see below).
Comparison is constant-time (`hmac.compare_digest`).

## Denial uniformity

Every authentication failure — missing header, malformed key, unknown `key_id`, wrong secret,
revoked key — returns the identical `401` body shape, verified by
`test_all_denial_bodies_identical_shape`. This prevents an attacker from distinguishing "this
key doesn't exist" from "this key exists but the secret is wrong" (no enumeration surface).
A disabled account with an otherwise-valid key gets `403`, distinguishable on purpose (blueprint
section 3.4 point 5) since it's not a secrecy boundary.

## No password/session portal in V1

Every route, including `/admin/*`, authenticates the same way: `Authorization: Bearer
lara_<key_id>.<secret>`, checked against the caller's role. There is no separate
username/password login endpoint. `users.password_hash` exists in the schema (for a possible
future portal) but nothing in this codebase writes or reads it. This matches the blueprint's
own guidance: "Password login is not required for V1 inference to work, so keep the portal
minimal" (Session 3 point 3).

## Bootstrap: the first key

Every `/admin/*` endpoint requires an admin-role key — including the endpoint that issues
keys. The very first key is therefore minted out-of-band, directly against the database, by
`database/seed/bootstrap_owner.py` (wrapped by `scripts/bootstrap-owner.sh`), not through the
API. It creates the `owner` user if missing and prints a freshly issued raw key exactly once.
Verified for real: `./scripts/bootstrap-owner.sh` against the running stack produced a working
owner key on the first try.

## Coarse `last_used_at`

Updated only if more than 60 seconds have passed since the last update, so key usage doesn't
add a database write to every single inference request (blueprint section 3.4 point 3).

## What's still open

- Rate limiting and auth-failure throttling: Phase G (Session 6).
- Mode-aware authorization (admission policy per operating mode): Phase F (Session 5).
- `/admin/models`, `/admin/mode`: Phase F.
