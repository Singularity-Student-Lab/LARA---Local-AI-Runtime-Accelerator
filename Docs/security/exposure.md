# Exposure Audit

Implements blueprint section 6, Session 6's exposure audit. Run `scripts/audit-ports.sh`
before every release and re-run at V1 freeze (Session 7 exit gate re-runs it explicitly).

## Result: 2026-08-12, this dev machine

```
LARA exposure audit - 2026-08-12T16:57:21Z

== 1. Published ports: only lara-gateway, only loopback ==
  [PASS] lara-gateway published on loopback only: 127.0.0.1:8080
  [PASS] no unexpected published ports found

== 2. lara-inference has no ports: entry in compose.yaml ==
  [PASS] lara-inference has no ports: entry (or the service does not exist yet)

== 3. lara-database has no ports: entry in compose.yaml ==
  [PASS] lara-database has no ports: entry

== 4. Docker daemon not listening on TCP ==
  [PASS] Docker daemon not listening on TCP

== 5. Raw host-port probing (informational only, NOT authoritative) ==
  [INFO] nothing answers on 127.0.0.1:8000
  [INFO] something answers on 127.0.0.1:5432 (see the caveat below)

Exposure audit PASSED.
```

## A real finding worth recording: port 5432 is misleading on this machine

The first version of `scripts/audit-ports.sh` raw-probed `127.0.0.1:5432` and failed the
audit, because *something* answers there. Investigation
(`ss -tlnp`, `systemctl status postgresql`, `ps aux`) showed it is an unrelated, pre-existing
**native PostgreSQL 16** systemd service on this dev machine (`postgresql.service`), entirely
independent of Docker and of `lara-database`. Confirmed independent by testing: it rejects a
throwaway password for `postgres`, while `docker compose exec lara-database psql ...` reaches
our actual container over the internal Docker network without issue - two separate databases
that happen to share a conventional port number.

**Consequence for the audit methodology**, not just this one result: raw TCP port-probing from
the host cannot distinguish "our container leaked" from "an unrelated host service happens to
use that port." It's kept as an `[INFO]` line for visibility, but the actual PASS/FAIL
authority is Docker's own published-port list (`docker compose ps` Publishers, check 1), which
is ground truth for whether *our* container is reachable outside Docker - not vulnerable to
this false-positive class. This is now documented in the script itself, not just here.

## What's still open

- **T-S6-05, T-S6-06 (three networks, external coding agent)**: needs a real Cloudflare
  account and tunnel token, neither of which exist in this development context. See
  `docs/operations/tunnel.md`.
- **T-S6-13, T-S6-14 (rate limit / auth-fail throttling under real traffic patterns)**:
  verified functionally on this machine (see `docs/security/auth.md` follow-up note below),
  not yet tuned against real agent retry behavior - that requires the beast and real users
  (blueprint section 6 point 4, `LARA_RATE_LIMIT_*` marked `NOT YET MEASURED`).
- **Once `lara-inference` exists**: re-run this audit. Its compose service definition must
  never gain a `ports:` entry - check 2 exists specifically to keep catching that.

## Abuse controls, verified for real (not simulated)

`gateway/app/api/security.py`'s `AuthFailThrottle` was exercised by circumstance: repeated
`401`-triggering requests sent throughout this development session (both manual `curl` testing
and `tests/integration/test_auth.py` running multiple times) accumulated past the default
threshold (10 failures / 60s window) and the source was genuinely blocked for the configured
300s, including rejecting a **subsequently-valid** key from the same source with `429
auth_fail_throttled` - proving the throttle blocks by source, not by key, exactly as intended.
State is in-process and cleared by a gateway restart (a documented, acceptable tradeoff for
not needing Redis at this scale).
