# Development Environment Record

**Status:** Current and verified. **Not the production target.**

This document records the actual, verified facts about the machine LARA is being developed
on, per blueprint section 2.4 ("Only discovered values may be written into `docs/` or into
the model registry seed data"). Nothing here is a production claim — see
`host-setup-beast.md` for the production runbook and `docs/benchmarks/baseline-idle.md`
section 2 for why no number here may be quoted as a LARA performance result.

## Verified 2026-08-12

```text
Machine:        Ashwath-Raj-Nitro-ANV15-41
OS:             Linux 7.0.0-28-generic (Ubuntu 24.04 base) - native, NOT WSL2
Docker:         29.6.1
Docker Compose: v5.3.0
Ollama:         0.16.3
Python:         3.12.3
Git remote:     github.com/Singularity-Student-Lab/LARA---Local-AI-Runtime-Accelerator
```

GPU (`nvidia-smi`):

```text
GPU:            NVIDIA GeForce RTX 3050 Laptop, 6144 MiB
Driver:         595.84
CUDA:           13.2
```

This is **not** the production RTX 5060 Ti 16GB. It is a real, physical NVIDIA GPU usable for
developing and correctness-testing GPU-facing code (the telemetry sampler, the pressure
evaluator), but it cannot host the target 7-8B class production model and no throughput,
VRAM, or latency figure measured here may be quoted as a LARA production result (blueprint
section 24.1).

Ollama model discovered (`ollama list`):

```text
NAME                         ID              SIZE      MODIFIED
llama3:8b-instruct-q4_K_M    9b8f3f3385bf    4.9 GB    5 months ago
```

This is the only model this document assumes exists. It was discovered, not assumed, per
blueprint section 2.4. See `docs/operations/dev-backend.md` for the endpoint-support matrix
run against it.

## Why this machine is not WSL2

The blueprint's production target is Windows 11 + WSL2 + Docker. This development machine is
native Linux. Two consequences, both resolved and recorded rather than assumed:

1. **Container-to-host reachability.** `host.docker.internal` is not automatically resolvable
   on native Linux Docker the way it is on Docker Desktop / WSL2. LARA resolves this with an
   explicit `extra_hosts: ["host.docker.internal:host-gateway"]` entry on `lara-gateway`
   (Docker 20.10+ feature), verified with a real container-to-host curl — see
   `docs/operations/dev-backend.md`. On the beast, this must be re-verified independently
   (blueprint's open unknown U-08); the WSL2 answer may differ.
2. **GPU chain verification (blueprint Session 1, section 2.2).** The Windows → WSL2 → Docker →
   NVIDIA Container Toolkit → CUDA container chain does not apply here and has not been run.
   `docs/operations/host-setup-beast.md` is the runbook for that chain, to be executed when the
   beast is available. Nothing in this document substitutes for it.

## What this environment is used for

Everything that is genuinely software, not hardware-scale-dependent: the gateway, database,
auth, scheduler, operating-mode logic, model registry, telemetry collection code, analytics,
and the full application-layer test suite (`tests/unit`, `tests/integration`, `tests/load`),
all run against the real Ollama backend above. See `LARA_7_Session_Implementation_Reference.md`
section 24.1 for the two-suite testing rule this repository follows.
