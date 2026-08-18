#!/usr/bin/env bash
# Mints the first owner API key, once the gateway+database stack is up.
# See database/seed/bootstrap_owner.py for what this actually does and why it's out-of-band.
set -euo pipefail
docker compose exec lara-gateway python -m database.seed.bootstrap_owner "$@"
