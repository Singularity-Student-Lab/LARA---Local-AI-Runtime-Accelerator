# Cloudflare Tunnel

Implements blueprint section 6. **Status: service defined, not yet connected.** No Cloudflare
account or tunnel token exists in this development context (`CLOUDFLARE_TUNNEL_TOKEN` is empty
in `.env.example` by design). This document is the setup procedure and the honest record of
what has and has not been verified.

## Service definition (done)

`compose.yaml`'s `lara-cloudflared` service, under the `tunnel` profile so it never starts by
accident:

```yaml
lara-cloudflared:
  image: cloudflare/cloudflared:2024.12.2
  profiles: ["tunnel"]
  command: tunnel --no-autoupdate run
  environment:
    TUNNEL_TOKEN: ${CLOUDFLARE_TUNNEL_TOKEN}
  networks: [lara_edge]
```

It attaches only to `lara_edge`, the same network `lara-gateway` is on - it has no route to
`lara_core` (internal-only) and therefore cannot reach `lara-inference` or `lara-database` even
if misconfigured to try. This is the enforcement mechanism for "route only the gateway"
(blueprint section 6 point 1.3), not a policy statement alone.

## Setup procedure (to run when a Cloudflare account exists)

1. Create a tunnel in the Cloudflare dashboard (Zero Trust -> Networks -> Tunnels), obtain its
   token.
2. Set `CLOUDFLARE_TUNNEL_TOKEN` in `.env` (never commit it).
3. `docker compose --profile tunnel up -d lara-cloudflared`
4. In the Cloudflare dashboard, configure the tunnel's public hostname to route to
   `http://lara-gateway:8080` - and only that. Do not add a second public hostname pointing at
   any other internal service.
5. Verify: `curl https://<public-hostname>/health` from a network other than this one.

## Hostname strategy (blueprint section 6 point 2)

| Option | Cost | Status |
| --- | --- | --- |
| Provider-assigned quick-tunnel hostname | Free | **UNKNOWN - MUST BE VERIFIED**: whether it persists across tunnel restarts has not been tested here (no live tunnel exists). Verify before depending on it for client configuration. |
| Custom domain routed through Cloudflare | Domain registration cost only, optional | Not required for core operation - documented as optional per the zero-mandatory-cost requirement (blueprint section 25). |

## Testing status

| Test | Status |
| --- | --- |
| T-S6-01 `/health` reachable externally | **Not run** - no live tunnel |
| T-S6-02 unauthenticated `/v1/models` external | **Not run** |
| T-S6-03/04 authenticated completion, streaming, external | **Not run** |
| T-S6-05 three networks | **Not run** |
| T-S6-06 coding agent, external | **Not run** |
| T-S6-13 rate limiting | Verified functionally on this machine (loopback), not against real external traffic - see `docs/security/exposure.md` |
| T-S6-14 auth-fail throttling | **Verified for real** - see `docs/security/exposure.md` |
| T-S6-15 tunnel reconnection | **Not run** - no live tunnel |
| T-S6-17 secret hygiene | Verified: `CLOUDFLARE_TUNNEL_TOKEN` is empty in the committed `.env.example`, real value only ever in git-ignored `.env` |

## Cost

No paid Cloudflare feature is required for this setup (blueprint section 25.2). A custom
domain is optional and never presented as mandatory.
