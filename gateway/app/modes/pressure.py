"""GPU pressure evaluator (blueprint section 5.3.3, Session 5). Pressure is derived from a
rolling window of samples, not a single reading, so a one-frame spike cannot pause the
service. Hysteresis requires the level to hold for several consecutive evaluations before
changing, using a lower threshold to exit a level than to enter it conceptually - implemented
here as "N consecutive samples at the new level" per blueprint section 5.3.3 point 5.

Sampling itself shells out to `nvidia-smi` (works with or without the NVIDIA Container Toolkit
configured for this container - see docs/operations/dev-environment.md: this dev container has
no GPU passthrough, so sampling here returns None and the evaluator correctly fails safe,
which is itself a real exercise of that failure path, not a mock). Full productionized
sampling into a persistent gpu_samples table is Phase H (Session 7); this is the
"prototype form" the blueprint says Session 5 needs at minimum (Session 5 prerequisites)."""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import statistics
from collections import deque

logger = logging.getLogger("lara.gateway.pressure")

LEVELS = ("LOW", "MODERATE", "HIGH", "CRITICAL")


@dataclasses.dataclass(frozen=True)
class GpuSample:
    util_pct: float
    vram_used_mib: float
    vram_total_mib: float
    temp_c: float

    @property
    def vram_pct(self) -> float:
        return 100.0 * self.vram_used_mib / self.vram_total_mib if self.vram_total_mib else 0.0


@dataclasses.dataclass(frozen=True)
class PressureThresholds:
    vram_moderate: float
    vram_high: float
    vram_critical: float
    util_moderate: float
    util_high: float
    util_critical: float
    temp_critical: float


async def sample_gpu() -> GpuSample | None:
    try:
        proc = await asyncio.create_subprocess_exec(
            "nvidia-smi",
            "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
            "--format=csv,noheader,nounits",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        if proc.returncode != 0:
            return None
        util, used, total, temp = (float(x.strip()) for x in stdout.decode().strip().split(","))
        return GpuSample(util_pct=util, vram_used_mib=used, vram_total_mib=total, temp_c=temp)
    except (FileNotFoundError, asyncio.TimeoutError, ValueError, OSError):
        return None


def _level_from_sample(median: GpuSample, thresholds: PressureThresholds) -> str:
    if median.temp_c >= thresholds.temp_critical:
        return "CRITICAL"
    if median.vram_pct >= thresholds.vram_critical or median.util_pct >= thresholds.util_critical:
        return "CRITICAL"
    if median.vram_pct >= thresholds.vram_high or median.util_pct >= thresholds.util_high:
        return "HIGH"
    if median.vram_pct >= thresholds.vram_moderate or median.util_pct >= thresholds.util_moderate:
        return "MODERATE"
    return "LOW"


class PressureEvaluator:
    def __init__(self, *, window_samples: int, hysteresis_samples: int, thresholds: PressureThresholds) -> None:
        self.window_samples = window_samples
        self.hysteresis_samples = hysteresis_samples
        self.thresholds = thresholds

        self._window: deque[GpuSample] = deque(maxlen=window_samples)
        self._current_level = "LOW"
        self._candidate_level: str | None = None
        self._candidate_streak = 0
        self.telemetry_healthy = False
        self.last_sample: GpuSample | None = None

    @property
    def current_level(self) -> str:
        return self._current_level

    def ingest(self, sample: GpuSample | None) -> str:
        if sample is None:
            # Fail safe: unknown pressure is never treated as LOW (blueprint section 5.3.3
            # failure table). Telemetry loss escalates to MODERATE, alert-worthy, and logged.
            self.telemetry_healthy = False
            if self._current_level == "LOW":
                logger.warning("telemetry unavailable, failing safe to MODERATE pressure")
                self._current_level = "MODERATE"
            self._candidate_level = None
            self._candidate_streak = 0
            return self._current_level

        self.telemetry_healthy = True
        self.last_sample = sample
        self._window.append(sample)

        median = GpuSample(
            util_pct=statistics.median(s.util_pct for s in self._window),
            vram_used_mib=statistics.median(s.vram_used_mib for s in self._window),
            vram_total_mib=sample.vram_total_mib,
            temp_c=statistics.median(s.temp_c for s in self._window),
        )
        candidate = _level_from_sample(median, self.thresholds)

        if candidate == self._current_level:
            self._candidate_level = None
            self._candidate_streak = 0
            return self._current_level

        if candidate == self._candidate_level:
            self._candidate_streak += 1
        else:
            self._candidate_level = candidate
            self._candidate_streak = 1

        if self._candidate_streak >= self.hysteresis_samples:
            logger.info(
                "pressure level transition",
                extra={
                    "from": self._current_level,
                    "to": candidate,
                    "util_pct": median.util_pct,
                    "vram_pct": median.vram_pct,
                    "temp_c": median.temp_c,
                },
            )
            self._current_level = candidate
            self._candidate_level = None
            self._candidate_streak = 0

        return self._current_level
