#!/usr/bin/env bash
# Host-level health checks, adapted for this dev machine (native Linux, not WSL2).
# Prints pass/fail per layer. Does not check WSL2 or the NVIDIA Container Toolkit here -
# this host has no WSL2 layer. See docs/operations/host-setup-beast.md for the beast's
# equivalent chain (Windows -> WSL2 -> Docker -> NVIDIA Container Toolkit -> CUDA -> GPU).
set -uo pipefail

pass() { printf '  [PASS] %s\n' "$1"; }
fail() { printf '  [FAIL] %s\n' "$1"; STATUS=1; }
STATUS=0

echo "== Docker =="
if docker info >/dev/null 2>&1; then
  pass "Docker daemon reachable ($(docker --version))"
else
  fail "Docker daemon not reachable"
fi

echo "== Docker Compose =="
if docker compose version >/dev/null 2>&1; then
  pass "Compose available ($(docker compose version --short 2>/dev/null || docker compose version))"
else
  fail "docker compose not available"
fi

echo "== NVIDIA GPU (dev card, not production) =="
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
  pass "nvidia-smi reports a GPU: $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader)"
else
  fail "nvidia-smi not available or no GPU visible"
fi

echo "== GPU visible inside a container =="
if docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi >/dev/null 2>&1; then
  pass "GPU visible inside a Docker container"
else
  fail "GPU not visible inside a Docker container (image pull or toolkit issue - not fatal for dev-only work, since lara-inference is prod-profile-only)"
fi

echo "== Ollama (dev inference backend) =="
if curl -fsS --max-time 3 http://localhost:11434/v1/models >/dev/null 2>&1; then
  pass "Ollama reachable on localhost:11434"
else
  fail "Ollama not reachable on localhost:11434"
fi

echo "== Repository hygiene =="
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if [ -f .gitignore ] && grep -q '^\.env$' .gitignore; then
    pass ".gitignore present and excludes .env"
  else
    fail ".gitignore missing or does not exclude .env"
  fi
else
  fail "not inside a git work tree"
fi

echo
if [ "$STATUS" -eq 0 ]; then
  echo "All checks passed."
else
  echo "One or more checks failed. See [FAIL] lines above."
fi
exit "$STATUS"
