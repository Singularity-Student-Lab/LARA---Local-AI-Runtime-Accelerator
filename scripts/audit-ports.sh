#!/usr/bin/env bash
# Exposure audit (blueprint section 6, Session 6, "Exposure audit"). Checks and records what
# the blueprint calls the session's negative tests - each one is a MUST FAIL for the service
# to be considered safe. Evidence goes to docs/security/exposure.md; this script is what
# produces it, dated and reproducible.
set -uo pipefail

cd "$(dirname "$0")/.."

STATUS=0
pass() { printf '  [PASS] %s\n' "$1"; }
fail() { printf '  [FAIL] %s\n' "$1"; STATUS=1; }

echo "LARA exposure audit - $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo

echo "== 1. Published ports: only lara-gateway, only loopback =="
PORTS_JSON=$(docker compose ps --format json 2>/dev/null)
BAD_PUBLISH=0
while IFS= read -r line; do
  [ -z "$line" ] && continue
  SERVICE=$(echo "$line" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('Service',''))" 2>/dev/null || true)
  PUBLISHERS=$(echo "$line" | python3 -c "
import sys, json
d = json.loads(sys.stdin.read())
for p in d.get('Publishers') or []:
    if p.get('PublishedPort'):
        print(f\"{p.get('URL','')}:{p['PublishedPort']}\")
" 2>/dev/null || true)
  if [ -n "$PUBLISHERS" ]; then
    if [ "$SERVICE" = "lara-gateway" ]; then
      if echo "$PUBLISHERS" | grep -qv '^127\.0\.0\.1:'; then
        fail "lara-gateway published on a non-loopback address: $PUBLISHERS"
        BAD_PUBLISH=1
      else
        pass "lara-gateway published on loopback only: $PUBLISHERS"
      fi
    else
      fail "$SERVICE has a published port ($PUBLISHERS) - only lara-gateway may publish anything"
      BAD_PUBLISH=1
    fi
  fi
done <<< "$PORTS_JSON"
[ "$BAD_PUBLISH" -eq 0 ] && pass "no unexpected published ports found"

echo
echo "== 2. lara-inference has no ports: entry in compose.yaml =="
if grep -A3 '^  lara-inference:' compose.yaml 2>/dev/null | grep -q 'ports:'; then
  fail "lara-inference has a ports: entry in compose.yaml"
else
  pass "lara-inference has no ports: entry (or the service does not exist yet)"
fi

echo
echo "== 3. lara-database has no ports: entry in compose.yaml =="
if grep -A5 '^  lara-database:' compose.yaml | grep -q '^\s*ports:'; then
  fail "lara-database has a ports: entry in compose.yaml"
else
  pass "lara-database has no ports: entry"
fi

echo
echo "== 4. Docker daemon not listening on TCP =="
if ss -tlnp 2>/dev/null | grep -qE ':(2375|2376)\b'; then
  fail "Docker daemon appears to be listening on TCP (2375/2376)"
else
  pass "Docker daemon not listening on TCP"
fi

echo
echo "== 5. Raw host-port probing (informational only, NOT authoritative) =="
# A real finding from running this on this dev machine: port 5432 IS reachable on
# 127.0.0.1, but NOT because lara-database leaked - this host already runs an unrelated
# native PostgreSQL 16 service (systemd unit `postgresql`) that happens to occupy the same
# port number, entirely independent of Docker. Raw TCP probing cannot distinguish "our
# container is exposed" from "something else on this machine uses that port" - so it is not
# used as a pass/fail signal here. Check 1 (Docker's own Publishers list) is the actual
# ground truth for container port exposure and is what this audit's PASS/FAIL is based on.
for PORT in 8000 5432; do
  if timeout 2 bash -c "echo > /dev/tcp/127.0.0.1/$PORT" 2>/dev/null; then
    echo "  [INFO] something answers on 127.0.0.1:$PORT (see the caveat above before assuming it's LARA)"
  else
    echo "  [INFO] nothing answers on 127.0.0.1:$PORT"
  fi
done

echo
if [ "$STATUS" -eq 0 ]; then
  echo "Exposure audit PASSED. Record this output, dated, in docs/security/exposure.md."
else
  echo "Exposure audit FAILED. Do not consider Session 6 (or a V1 freeze) closed until this passes."
fi
exit "$STATUS"
