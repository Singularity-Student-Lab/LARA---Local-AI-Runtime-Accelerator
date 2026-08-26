#!/usr/bin/env bash
# Backend smoke test: models, non-streaming, streaming, tool-call-if-supported.
# One command, pass or fail, per blueprint section 3.5 (inference/scripts/smoke.sh).
#
# Usage: inference/scripts/smoke.sh <base_url> <model_id>
# Example (dev, direct to Ollama): inference/scripts/smoke.sh http://localhost:11434 llama3:8b-instruct-q4_K_M
set -uo pipefail

BASE_URL="${1:?usage: smoke.sh <base_url> <model_id>}"
MODEL="${2:?usage: smoke.sh <base_url> <model_id>}"

STATUS=0
pass() { printf '  [PASS] %s\n' "$1"; }
fail() { printf '  [FAIL] %s\n' "$1"; STATUS=1; }

echo "Smoke testing $BASE_URL model=$MODEL"

echo "== GET /v1/models =="
MODELS_JSON=$(curl -fsS --max-time 10 "$BASE_URL/v1/models" 2>&1)
if [ $? -eq 0 ] && echo "$MODELS_JSON" | grep -q "$MODEL"; then
  pass "model listed"
else
  fail "model not listed or endpoint unreachable: $MODELS_JSON"
fi

echo "== POST /v1/chat/completions (non-streaming) =="
NS_JSON=$(curl -fsS --max-time 60 "$BASE_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: OK\"}],\"stream\":false,\"max_tokens\":10}" 2>&1)
if [ $? -eq 0 ] && echo "$NS_JSON" | grep -q '"usage"'; then
  pass "non-streaming completion returned usage"
else
  fail "non-streaming completion failed: $NS_JSON"
fi

echo "== POST /v1/chat/completions (stream=true) =="
STREAM_OUT=$(curl -fsS --no-buffer --max-time 60 "$BASE_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"count to 3\"}],\"stream\":true,\"max_tokens\":20}" 2>&1)
if echo "$STREAM_OUT" | grep -q "^data: \[DONE\]"; then
  pass "streaming terminated with [DONE]"
else
  fail "streaming did not terminate as expected"
fi

echo "== POST /v1/responses (support may vary by backend) =="
RESP_CODE=$(curl -s -o /tmp/lara-smoke-responses.json -w '%{http_code}' --max-time 30 "$BASE_URL/v1/responses" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$MODEL\",\"input\":\"Reply with exactly: OK\"}")
if [ "$RESP_CODE" = "200" ]; then
  pass "/v1/responses supported (200)"
else
  echo "  [INFO] /v1/responses returned $RESP_CODE - recorded as unsupported, not a smoke-test failure"
fi
rm -f /tmp/lara-smoke-responses.json

echo "== Tool calling (support may vary by model+backend) =="
TOOL_JSON=$(curl -fsS --max-time 30 "$BASE_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"What is the weather in Paris?\"}],\"tools\":[{\"type\":\"function\",\"function\":{\"name\":\"get_weather\",\"description\":\"Get weather\",\"parameters\":{\"type\":\"object\",\"properties\":{\"city\":{\"type\":\"string\"}},\"required\":[\"city\"]}}}],\"stream\":false}" 2>&1)
if echo "$TOOL_JSON" | grep -q 'tool_calls'; then
  pass "tool call emitted"
else
  echo "  [INFO] no tool_calls in response - recorded as unsupported for this model+backend, not a smoke-test failure"
fi

echo
if [ "$STATUS" -eq 0 ]; then
  echo "Smoke test passed (core endpoints). See [INFO] lines for optional-capability results."
else
  echo "Smoke test FAILED on a core endpoint."
fi
exit "$STATUS"
