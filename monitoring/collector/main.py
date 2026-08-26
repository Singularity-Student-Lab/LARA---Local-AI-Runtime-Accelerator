"""lara-telemetry: periodic GPU and system sampler (blueprint section 21.7, Session 7).

Must never crash the stack (blueprint requirement, section 7 point 4): every sampling
iteration is wrapped so a single failed sample logs and retries rather than killing the loop.
Reuses app.modes.pressure.sample_gpu() rather than duplicating the nvidia-smi logic - one
sampling implementation, used by both the live pressure evaluator (Phase F) and this durable
collector (Phase H).
"""

from __future__ import annotations

import asyncio
import logging
import os

from app.config import get_settings
from app.db.models import GpuSample as GpuSampleRow
from app.db.session import SessionLocal
from app.modes.pressure import sample_gpu

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("lara.telemetry")


def _read_loadavg_pct() -> float | None:
    """1-minute load average as a rough CPU-pressure percentage (load / core count * 100).
    This is the collector CONTAINER's view of the kernel's load average - not necessarily
    identical to a bare-metal reading if cgroup CPU limits differ (documented, not assumed
    equivalent, per docs/architecture/telemetry.md)."""
    try:
        with open("/proc/loadavg") as f:
            load1 = float(f.read().split()[0])
        cores = os.cpu_count() or 1
        return round(100.0 * load1 / cores, 2)
    except OSError:
        return None


def _read_ram_used_mib() -> float | None:
    try:
        with open("/proc/meminfo") as f:
            lines = {line.split(":")[0]: line for line in f}
        total_kib = int(lines["MemTotal"].split()[1])
        avail_kib = int(lines["MemAvailable"].split()[1])
        return round((total_kib - avail_kib) / 1024, 2)
    except (OSError, KeyError, ValueError, IndexError):
        return None


async def sample_once() -> None:
    settings = get_settings()
    gpu = await sample_gpu()
    cpu_pct = _read_loadavg_pct()
    ram_used_mib = _read_ram_used_mib()

    async with SessionLocal() as db:
        db.add(
            GpuSampleRow(
                gpu_util_pct=gpu.util_pct if gpu else None,
                vram_used_mib=gpu.vram_used_mib if gpu else None,
                vram_total_mib=gpu.vram_total_mib if gpu else None,
                temp_c=gpu.temp_c if gpu else None,
                power_w=None,  # UNKNOWN - MUST BE VERIFIED whether nvidia-smi reports power on
                                # the target hardware; not parsed by sample_gpu() today.
                cpu_pct=cpu_pct,
                ram_used_mib=ram_used_mib,
                active_jobs=None,  # populated when the collector runs alongside a reachable
                queue_depth=None,  # gateway; left null for the standalone collector for now.
                telemetry_healthy=gpu is not None,
            )
        )
        await db.commit()

    if gpu is None:
        logger.warning("gpu sample unavailable this cycle (expected on a container without GPU passthrough)")


async def main() -> None:
    settings = get_settings()
    logger.info("lara-telemetry starting, interval=%ss", settings.lara_gpu_sample_interval_s)
    while True:
        try:
            await sample_once()
        except Exception:
            logger.exception("sampling iteration failed, will retry")
        await asyncio.sleep(settings.lara_gpu_sample_interval_s)


if __name__ == "__main__":
    asyncio.run(main())
