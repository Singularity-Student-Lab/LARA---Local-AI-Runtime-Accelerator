#!/usr/bin/env bash
# Model switch, registry portion (blueprint section 22.4 / diagram 10, steps 9, 12, 13).
#
# What this script actually does today: smoke-tests the target backend+model, then registers
# or updates the alias and (optionally) makes it the default - the parts of the switch runbook
# that are real without a container to recreate. Steps 5-8 (drain, recreate lara-inference,
# roll back on failure) only apply once a real vLLM container exists to switch
# (docs/operations/model-switch.md has the full runbook, including those still-manual steps).
#
# Usage:
#   scripts/model.sh <alias> <backend_name> <model_ref> <context_limit> [--default] <api-key>
#
# Example (this dev machine):
#   scripts/model.sh campus-coder ollama-dev llama3:8b-instruct-q4_K_M 4096 --default "$LARA_ADMIN_KEY"
set -euo pipefail

BASE_URL="${LARA_BASE_URL:-http://127.0.0.1:8080}"

ALIAS="${1:?usage: model.sh <alias> <backend_name> <model_ref> <context_limit> [--default] <api-key>}"
BACKEND_NAME="${2:?missing backend_name}"
MODEL_REF="${3:?missing model_ref}"
CONTEXT_LIMIT="${4:?missing context_limit}"
shift 4

IS_DEFAULT=false
if [ "${1:-}" = "--default" ]; then
  IS_DEFAULT=true
  shift
fi
KEY="${1:?missing api key (or set LARA_ADMIN_KEY)}"

echo "== 1-2. Compatibility preflight and memory feasibility: manual, see docs/operations/inference-runtime.md =="

echo "== 9. Generation smoke test =="
# The registry API does not expose raw backend base_urls (by design - clients never see them).
# Pass LARA_BACKEND_URL explicitly for the smoke test itself.
SMOKE_URL="${LARA_BACKEND_URL:?set LARA_BACKEND_URL to the backend base URL for the smoke test, e.g. http://localhost:11434}"
"$(dirname "$0")/../inference/scripts/smoke.sh" "$SMOKE_URL" "$MODEL_REF"

echo "== 12. Update the registry =="
EXISTING=$(curl -fsS -H "Authorization: Bearer $KEY" "$BASE_URL/admin/models" | \
  python3 -c "
import sys, json
rows = json.load(sys.stdin)
match = [r for r in rows if r['alias'] == '$ALIAS']
print('yes' if match else 'no')
")

if [ "$EXISTING" = "yes" ]; then
  curl -fsS -X PATCH -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
    -d "{\"enabled\": true, \"context_limit\": $CONTEXT_LIMIT, \"is_default\": $IS_DEFAULT}" \
    "$BASE_URL/admin/models/$ALIAS"
else
  curl -fsS -X POST -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
    -d "{\"alias\":\"$ALIAS\",\"backend_name\":\"$BACKEND_NAME\",\"model_ref\":\"$MODEL_REF\",\"context_limit\":$CONTEXT_LIMIT,\"enabled\":true,\"is_default\":$IS_DEFAULT}" \
    "$BASE_URL/admin/models"
fi
echo

echo "== 13. Resume admission: nothing to do, admission was never paused for a registry-only switch =="
echo "Done. Alias '$ALIAS' -> backend '$BACKEND_NAME' -> model '$MODEL_REF'."
