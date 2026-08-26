"""Leaderboard scoring (blueprint section 21.8 / PRD 13.3-13.4 / Appendix D rule 9). Never
ranks by raw token generation alone, never rewards spam.

Score components, matching the blueprint's Engineering Recommendation table exactly:
  - successful (COMPLETED) requests - failed/cancelled/rejected score nothing
  - distinct active days - cannot be farmed in one burst
  - agent sessions - approximates real tasks, not raw call volume
  - diminishing returns per day - caps single-day burst farming
  - token volume - included with a small weight, never the primary term

Weights are configuration (LARA_LEADERBOARD_WEIGHTS), tunable without a deployment."""

from __future__ import annotations

import dataclasses
import json
import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UsageDaily, User


@dataclasses.dataclass(frozen=True)
class LeaderboardWeights:
    successful_requests: float
    active_days: float
    agent_sessions: float
    tokens: float


def parse_weights(raw_json: str) -> LeaderboardWeights:
    data = json.loads(raw_json)
    return LeaderboardWeights(
        successful_requests=float(data.get("successful_requests", 1.0)),
        active_days=float(data.get("active_days", 5.0)),
        agent_sessions=float(data.get("agent_sessions", 3.0)),
        tokens=float(data.get("tokens", 0.001)),
    )


async def compute_leaderboard(db: AsyncSession, weights: LeaderboardWeights, *, limit: int = 50) -> list[dict]:
    rows = list((await db.execute(select(UsageDaily))).scalars().all())

    per_user: dict = {}
    for row in rows:
        agg = per_user.setdefault(
            row.user_id,
            {"successful": 0, "days": set(), "sessions": 0, "tokens": 0, "daily_successful": {}},
        )
        agg["successful"] += row.completed
        agg["days"].add(row.day)
        agg["sessions"] += row.agent_sessions
        agg["tokens"] += row.input_tokens + row.output_tokens
        # Diminishing returns per day: sqrt caps how much a single burst day can contribute,
        # without a hard cap that would zero out a legitimately busy day entirely.
        agg["daily_successful"][row.day] = agg["daily_successful"].get(row.day, 0) + row.completed

    scored = []
    for user_id, agg in per_user.items():
        diminished_successful = sum(math.sqrt(n) for n in agg["daily_successful"].values())
        score = (
            weights.successful_requests * diminished_successful
            + weights.active_days * len(agg["days"])
            + weights.agent_sessions * agg["sessions"]
            + weights.tokens * agg["tokens"]
        )
        scored.append({"user_id": user_id, "score": round(score, 2)})

    scored.sort(key=lambda x: x["score"], reverse=True)
    scored = scored[:limit]

    user_ids = [s["user_id"] for s in scored]
    if user_ids:
        users = {
            u.id: u.display_name
            for u in (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
        }
    else:
        users = {}

    # Privacy (blueprint section 21.8 / PRD 13.5): display name and score only, never keys,
    # prompts, source code, responses, or authentication data.
    return [{"display_name": users.get(s["user_id"], "unknown"), "score": s["score"]} for s in scored]
