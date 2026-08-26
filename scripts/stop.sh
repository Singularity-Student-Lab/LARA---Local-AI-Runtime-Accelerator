#!/usr/bin/env bash
# Stops the stack. Data (Postgres volume) is preserved - use `docker compose down -v` manually
# if a full reset including data is actually intended (destructive, not wrapped here on purpose).
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose down
