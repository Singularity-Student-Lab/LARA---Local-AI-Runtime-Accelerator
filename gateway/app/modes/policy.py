"""Mode policy as configuration, not branching logic (blueprint section 5.3.2 / PRD 8.4,
master task 27). A new mode should be a row plus configuration, not a new `if` - so this is a
plain dict of dataclasses, not a chain of `if mode == "SERVING": ...`.

All numeric defaults here are seeds. Real values come from Session 7 production benchmarking
(Phase H in this repo) - see .env.example for the NOT YET MEASURED markers."""

from __future__ import annotations

import dataclasses

from app.config import Settings

MODES = ("SERVING", "PERSONAL", "GAMEDEV")


@dataclasses.dataclass(frozen=True)
class ModePolicy:
    max_active_jobs: int
    per_user_max_active: int
    owner_priority_bonus: int
    pressure_policy_enabled: bool


def build_mode_policies(settings: Settings) -> dict[str, ModePolicy]:
    return {
        "SERVING": ModePolicy(
            max_active_jobs=settings.lara_max_active_jobs,
            per_user_max_active=settings.lara_per_user_max_active,
            owner_priority_bonus=0,
            pressure_policy_enabled=False,
        ),
        "PERSONAL": ModePolicy(
            max_active_jobs=settings.lara_max_active_jobs,
            # ENGINEERING RECOMMENDATION: "owner unlimited up to the ceiling" (blueprint
            # section 5.3.2) is approximated as a large per-user cap rather than a true
            # per-role override, since the scheduler's per-user cap is currently a single
            # process-wide value, not per-user. Documented rather than silently narrowed.
            per_user_max_active=max(settings.lara_per_user_max_active, settings.lara_max_active_jobs),
            owner_priority_bonus=1000,
            pressure_policy_enabled=False,
        ),
        "GAMEDEV": ModePolicy(
            max_active_jobs=settings.lara_max_active_jobs,
            per_user_max_active=settings.lara_per_user_max_active,
            owner_priority_bonus=0,
            pressure_policy_enabled=True,
        ),
    }


# Effect of GPU pressure level on the GAMEDEV mode's effective ceiling (blueprint section
# 5.3.3 point 6). LOW: no change. MODERATE: reduced. HIGH/CRITICAL: admit nothing new -
# running jobs still finish, because this only affects the ADMISSION ceiling, never cancels
# what's already RUNNING (blueprint section 5.3.2: preemption is not implemented in V1).
def pressure_adjusted_ceiling(base_ceiling: int, pressure_level: str) -> int:
    if pressure_level == "LOW":
        return base_ceiling
    if pressure_level == "MODERATE":
        return max(1, base_ceiling - 1)
    return 0  # HIGH or CRITICAL
