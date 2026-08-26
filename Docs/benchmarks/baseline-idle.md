# Idle Resource Baseline

## 1. Development machine — 2026-08-12

**Not a production measurement.** This is the dev PC (`docs/operations/dev-environment.md`),
with normal desktop use in progress (browser, editor, this session's tooling running) — not a
true idle state, and recorded as such rather than presented as clean idle.

| Metric | Source | Recorded value |
| --- | --- | --- |
| GPU utilization | `nvidia-smi` | 40% (Xorg desktop compositor active; not a clean idle sample) |
| VRAM used | `nvidia-smi` | 92 MiB / 6144 MiB |
| GPU temperature | `nvidia-smi` | 39°C |
| GPU power draw | `nvidia-smi` | 8.70 W |
| Host RAM used | `free -h` | 9.3Gi / 14Gi (5.6Gi available) |
| CPU logical processors | `nproc` | 12 |
| CPU load average (1/5/15m) | `top` | 1.13 / 1.12 / 0.87 |
| Free disk on the repo's filesystem | `df -h` | **3.7G free of 119G (97% used)** |

**Finding, not a guess:** this machine's disk is nearly full. It has enough headroom for the
gateway/database containers and this repository's own code, but not for a second large model
download or a sustained telemetry retention window at real scale. This is noted here rather
than silently assumed away; if model experimentation is needed on this box, free space first.

## 2. Production — the beast (RTX 5060 Ti 16GB, Windows 11 + WSL2)

**NOT YET MEASURED.** No such machine exists in this development context. Record here, in a
new dated subsection, per `docs/operations/host-setup-beast.md` section 4, the first time that
runbook is executed. Nothing from section 1 above may be substituted or extrapolated for this
section — different OS, different GPU, different memory class entirely.

| Metric | Idle | Normal desktop use |
| --- | --- | --- |
| VRAM used | NOT YET MEASURED | NOT YET MEASURED |
| GPU utilization | NOT YET MEASURED | NOT YET MEASURED |
| GPU temperature | NOT YET MEASURED | NOT YET MEASURED |
| GPU power draw | NOT YET MEASURED | NOT YET MEASURED |
| Host RAM used | NOT YET MEASURED | NOT YET MEASURED |
| CPU utilization | NOT YET MEASURED | NOT YET MEASURED |
| Free disk on the model-storage volume | NOT YET MEASURED | NOT YET MEASURED |
