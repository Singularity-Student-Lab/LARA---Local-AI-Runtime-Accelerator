"""Runs retention deletion once (blueprint section 23.3 / Session 7 point 5).

No cron infrastructure exists in this codebase - run this on a schedule via the host's own
scheduler (systemd timer, cron, Task Scheduler on the eventual Windows beast), wrapped by
scripts/retention.sh. This keeps the deletion logic itself testable and versioned in
application code, without this repo inventing a job-scheduling system for one recurring task.

Usage: python -m database.maintenance.run_retention
"""

from __future__ import annotations

import asyncio

from app.analytics.retention import apply_retention
from app.config import get_settings
from app.db.session import SessionLocal


async def main() -> None:
    settings = get_settings()
    async with SessionLocal() as db:
        result = await apply_retention(
            db,
            jobs_days=settings.lara_retention_jobs_days,
            gpu_raw_days=settings.lara_retention_gpu_raw_days,
            audit_days=settings.lara_retention_audit_days,
        )
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
