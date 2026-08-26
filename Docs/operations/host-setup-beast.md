# Production Host Setup Runbook — the Beast (Windows 11 + WSL2 + RTX 5060 Ti 16GB)

**Status: NOT YET EXECUTED.** This machine does not exist in this development context. This
document is the checklist to run, in order, the first time it does. It is derived directly
from `Docs/LARA_7_Session_Implementation_Reference.md` Session 1, adapted into an executable
runbook. Every value below is `UNKNOWN — MUST BE VERIFIED`; none may be filled in from
assumption, guess, or by copying a number from the dev environment (`dev-environment.md`),
which is a different machine, a different OS, and a different GPU.

Do not write application logic while running this runbook. Its only job is to prove the chain:

```text
Windows 11 -> WSL2 -> Docker -> NVIDIA Container Toolkit -> CUDA container -> RTX 5060 Ti
```

survives a cold reboot, before any Session 2+ inference work resumes on this hardware.

## Prerequisites

- [ ] Physical/administrator access to the workstation confirmed.
- [ ] Working outbound Internet (`curl` to a package registry succeeds).
- [ ] Git installed, remote push works from this host.
- [ ] Free disk space recorded (model cache sizing is unknown until a candidate model is chosen).

## 1. Windows layer

- [ ] NVIDIA driver version: `_______` (record from `nvidia-smi` on Windows)
- [ ] CUDA version reported: `_______`
- [ ] GPU name and total memory reported: `_______` (must read "NVIDIA GeForce RTX 5060 Ti" and
      approximately 16,311 MiB — the informal "5060 Ti Super" label is wrong and must not appear
      anywhere else in this repository if it shows up here)
- [ ] Power plan set: never sleep, never hibernate, disk never powers down, USB selective
      suspend off if it affects the network adapter. Recorded: `_______`
- [ ] Wi-Fi power-saving disabled; adapter reconnect-after-outage behavior recorded: `_______`
- [ ] Windows update policy decided and recorded (an unattended driver update/restart takes the
      service down): `_______`

## 2. WSL2 layer

- [ ] WSL2 + Linux distribution installed. Distribution and kernel version: `_______`
- [ ] `nvidia-smi` inside WSL2 reports the same GPU as Windows: yes/no
- [ ] CUDA runtime visible inside WSL2: yes/no
- [ ] `.wslconfig` memory/swap limits set (leave headroom for Windows + a game engine on the
      64GB host). Values chosen and why: `_______`
- [ ] WSL2 restarts cleanly; GPU visibility returns without manual intervention: yes/no

## 3. Docker layer

- [ ] Docker installed with WSL2 integration. Version and install method: `_______`
- [ ] NVIDIA Container Toolkit installed and configured.
- [ ] `docker run --rm --gpus all <cuda-image>:<tag> nvidia-smi` reports the GPU. Image/tag used: `_______`
- [ ] Working GPU-request syntax for this host determined (`--gpus all` CLI form, and either
      `deploy.resources.reservations.devices` or `gpus:` in Compose). Chosen form: `_______`
      — use only this form thereafter in `compose.yaml`.
- [ ] Same result reproduced through `docker compose up` on a throwaway GPU smoke-test service
      (CLI and Compose GPU access fail differently; both must be proven).

## 4. Resource baseline

Record at idle (nothing else running) and again with the desktop in normal use. This becomes
`docs/benchmarks/baseline-idle.md` section "Production (the beast)" — do not overwrite the dev
machine's baseline; add a new dated section.

| Metric | Idle | Normal desktop use |
| --- | --- | --- |
| VRAM used | | |
| GPU utilization | | |
| GPU temperature | | |
| GPU power draw | | |
| Host RAM used | | |
| CPU utilization | | |
| Free disk on the model-storage volume | | |

## 5. Model storage location

- [ ] Host directory chosen for `LARA_MODEL_DIR`, outside the repository, on a volume with room
      to grow: `_______`
- [ ] Windows-volume vs WSL2-native-filesystem choice recorded, with the reasoning (cross-mount
      access can materially slow model load and therefore model-switch downtime): `_______`
- [ ] `.env` on this host sets `LARA_MODEL_DIR` to the chosen path; container mount is read-only
      at `/models`.

## 6. Repository on this host

- [ ] `git clone` the LARA repository.
- [ ] `.gitignore` present and correct before anything else is added (never commit a real `.env`
      or model weights from this host).
- [ ] `cp .env.example .env`, fill in real values, especially `LARA_ENV=prod`,
      `LARA_INFERENCE_IMAGE` (see step 7), and every secret.

## 7. The single highest-risk unknown: GPU-generation runtime support

Before attempting Session 2's production vLLM container, resolve and record, against current
official documentation and this actual machine:

- [ ] Compute capability reported by the driver for this specific card: `_______`
- [ ] Minimum NVIDIA driver version required on Windows 11 for CUDA under WSL2 on this card: `_______`
- [ ] Minimum CUDA runtime version required: `_______`
- [ ] Which published vLLM container image tag contains kernels built for this GPU architecture: `_______`
- [ ] Which quantization kernels (AWQ, GPTQ, FP8, bitsandbytes, etc.) are actually supported on
      this architecture by that pinned vLLM version: `_______`

If the pinned image does not support the GPU, the fallback ladder (in order): pin a newer vLLM
image; build vLLM from source against a matching CUDA/PyTorch; or, as a documented temporary
measure only, continue on the Ollama development backend while investigating. The fallback must
never become the permanent production architecture.

## Exit criteria (blueprint Session 1 exit gate)

- [ ] The chain works reliably after a cold reboot with no ad-hoc fixes.
- [ ] Exact driver/CUDA/WSL2/Docker/NVIDIA-Container-Toolkit versions recorded above.
- [ ] Idle baseline recorded in `docs/benchmarks/baseline-idle.md`.
- [ ] Working GPU-request syntax recorded and standardized.
- [ ] This document updated in place (not copied) with real values, dated, and the exit gate
      signed in `docs/operations/exit-gates.md`.

Only after this is closed should `inference/configs/vllm-prod.yaml` be filled in and
`LARA_INFERENCE_IMAGE` pinned to a real tag (see `docs/operations/inference-runtime.md`).
