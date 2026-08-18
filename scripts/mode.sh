#!/usr/bin/env bash
# Wraps GET/POST /admin/mode (blueprint section 5.3.1 point 5).
#
# Usage:
#   scripts/mode.sh                       - show current mode
#   scripts/mode.sh serving|personal|gamedev <api-key>   - switch mode
set -euo pipefail

BASE_URL="${LARA_BASE_URL:-http://127.0.0.1:8080}"

if [ $# -eq 0 ]; then
  KEY="${LARA_ADMIN_KEY:?set LARA_ADMIN_KEY or pass a key as the second argument}"
  curl -fsS -H "Authorization: Bearer $KEY" "$BASE_URL/admin/mode"
  echo
  exit 0
fi

MODE_ARG="$1"
KEY="${2:-${LARA_ADMIN_KEY:?set LARA_ADMIN_KEY or pass a key as the second argument}}"
MODE_UPPER=$(printf '%s' "$MODE_ARG" | tr '[:lower:]' '[:upper:]')

case "$MODE_UPPER" in
  SERVING|PERSONAL|GAMEDEV) ;;
  *) echo "Unknown mode '$MODE_ARG'. Valid: serving, personal, gamedev" >&2; exit 1 ;;
esac

curl -fsS -X POST -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d "{\"mode\":\"$MODE_UPPER\"}" "$BASE_URL/admin/mode"
echo
