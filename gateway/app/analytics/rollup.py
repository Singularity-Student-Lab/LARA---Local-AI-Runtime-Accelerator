"""Daily usage rollups (blueprint section 21.8 / Session 7 point 3). Rolls up `jobs` into
`usage_daily` per user/day/model, so the leaderboard and analytics stay cheap and `jobs`
retention can be shorter than analytics retention (blueprint section 7 point 3
Engineering Recommendation).

No cron scheduler exists in this codebase (ENGINEERING RECOMMENDATION, matching the
blueprint's own "do not over-engineer for hypothetical scale" - PRD 1.3 principle 13): rollup
is idempotent and safe to re-run for the same day, triggered by POST /admin/analytics/rollup
(scripts/retention.sh wraps it). Wiring it to an actual cron/systemd timer is an operational
choice for whoever deploys this, not application code."""

from __future__ import annotations

import statistics
from datetime import date, datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job, UsageDaily

# Approximates an "agent session" as a run of requests from one key with a gap below this
# threshold (blueprint section 21.8 Engineering Recommendation - the definition travels with
# the number, recorded here and in the UsageDaily model docstring).
SESSION_IDLE_GAP_S = 300


def _percentile(values: list[int], pct: float) -> int | None:
    if not values:
        return None
    values = sorted(values)
    idx = min(len(values) - 1, int(len(values) * pct))
    return values[idx]


def _count_sessions(received_ats: list[datetime]) -> int:
    if not received_ats:
        return 0
    ordered = sorted(received_ats)
    sessions = 1
    for prev, cur in zip(ordered, ordered[1:]):
        if (cur - prev).total_seconds() > SESSION_IDLE_GAP_S:
            sessions += 1
    return sessions


async def rollup_day(db: AsyncSession, day: date) -> int:
    """Idempotent: re-running for the same day recomputes and overwrites that day's rows."""
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    end = datetime.combine(day, time.max, tzinfo=timezone.utc)
    day_str = day.isoformat()

    jobs = list(
        (
            await db.execute(
                select(Job).where(Job.received_at >= start, Job.received_at <= end)
            )
        )
        .scalars()
        .all()
    )

    groups: dict[tuple, list[Job]] = {}
    for job in jobs:
        groups.setdefault((job.user_id, job.model_alias), []).append(job)

    # Clear any existing rows for this day first, so users/models with zero jobs today
    # (e.g. after a job was later deleted by retention) don't leave stale rows behind.
    existing = (await db.execute(select(UsageDaily).where(UsageDaily.day == day_str))).scalars().all()
    for row in existing:
        await db.delete(row)
    await db.flush()

    for (user_id, model_alias), group in groups.items():
        completed = [j for j in group if j.status == "COMPLETED"]
        failed = [j for j in group if j.status == "FAILED"]
        cancelled = [j for j in group if j.status == "CANCELLED"]
        rejected = [j for j in group if j.status == "REJECTED"]

        queue_waits = [j.queue_wait_ms for j in group if j.queue_wait_ms is not None]
        ttfts = [j.ttft_ms for j in group if j.ttft_ms is not None]

        db.add(
            UsageDaily(
                day=day_str,
                user_id=user_id,
                model_alias=model_alias,
                requests=len(group),
                completed=len(completed),
                failed=len(failed),
                cancelled=len(cancelled),
                rejected=len(rejected),
                input_tokens=sum(j.input_tokens or 0 for j in group),
                output_tokens=sum(j.output_tokens or 0 for j in group),
                generation_ms_total=sum(j.generation_ms or 0 for j in group),
                queue_wait_ms_mean=round(statistics.mean(queue_waits)) if queue_waits else None,
                queue_wait_ms_p95=_percentile(queue_waits, 0.95),
                ttft_ms_mean=round(statistics.mean(ttfts)) if ttfts else None,
                ttft_ms_p95=_percentile(ttfts, 0.95),
                agent_sessions=_count_sessions([j.received_at for j in group]),
            )
        )

    await db.commit()
    return len(groups)
