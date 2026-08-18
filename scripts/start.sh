#!/usr/bin/env bash
# Brings up the stack for the profile set in COMPOSE_PROFILES (.env, default "dev").
# Usage: scripts/start.sh [extra docker compose up args]
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "No .env found. Run: cp .env.example .env, then fill in real values." >&2
  exit 1
fi

docker compose up -d --build "$@"
echo
echo "Waiting for lara-gateway to become healthy..."
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8080/health >/dev/null 2>&1; then
    echo "lara-gateway is up."
    exit 0
  fi
  sleep 1
done
echo "lara-gateway did not become healthy in time. Check: docker compose logs lara-gateway" >&2
exit 1
