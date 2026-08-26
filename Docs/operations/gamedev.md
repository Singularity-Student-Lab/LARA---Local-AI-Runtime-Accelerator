# Game Dev Mode — Operator Notes

## What Game Dev Mode actually does

Per blueprint section 5.3.3's Engineering Note (repeated because it is the crux of this mode):
vLLM reserves its share of VRAM at container start. LARA cannot hand VRAM back to a game
engine at runtime by throttling requests. The two honest levers that exist:

1. **Admission control** (implemented, `gateway/app/modes/policy.py`'s
   `pressure_adjusted_ceiling`): as GPU pressure rises, GAMEDEV mode reduces the number of new
   jobs admitted - `LOW` unaffected, `MODERATE` reduces the ceiling by 1, `HIGH`/`CRITICAL`
   admit nothing new. Running jobs are never killed (PRD 8.2, no preemption in V1).
2. **An explicit operational action, not automated**: restart `lara-inference` with a smaller
   memory fraction using a dedicated `gamedev` model profile
   (`inference/configs/<model>-gamedev.yaml`), accepting a service interruption of the
   model-load duration. This profile does not exist yet - it gets created once a production
   model is selected (Session 7 / Phase H).

Anything claiming continuous VRAM rebalancing between a game engine and a running vLLM
instance would be fiction. This is why.

## Switching to Game Dev Mode

```bash
scripts/mode.sh gamedev "$LARA_ADMIN_KEY"
```

## What's verified vs. what's pending

Verified on this dev machine (`tests/integration/test_modes.py`,
`docs/architecture/modes.md`): mode switch and audit, `pressure_policy_enabled=true` under
GAMEDEV, effective ceiling reduction under (fail-safe) `MODERATE` pressure.

Pending, requires the beast and a real game workload (blueprint Session 7 exit criteria):
threshold tuning against real Unity/Unreal GPU usage, validation that the game workload stays
usable at each pressure level, and creation of the `gamedev` model profile once a production
model exists. `docs/benchmarks/` will record these once measured - nothing here is a
substitute for that measurement.
