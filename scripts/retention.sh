#!/usr/bin/env bash
# Runs the retention deletion pass once. Intended to be invoked on a schedule by the host's
# own scheduler (systemd timer / cron / Windows Task Scheduler on the beast) - no such
# schedule is configured by this repo (blueprint section 23.3, PRD 12.5).
set -euo pipefail
docker compose exec -T lara-gateway python -m database.maintenance.run_retention
