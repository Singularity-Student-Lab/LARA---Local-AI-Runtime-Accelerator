"""Blueprint Testing table T-S5-04 through T-S5-09, using synthetic samples - exactly what the
blueprint's own test table calls for ("Game Dev mode, synthetic moderate/high/critical
pressure"). No GPU or container needed; this validates the algorithm, not a specific card."""

from app.modes.pressure import GpuSample, PressureEvaluator, PressureThresholds

THRESHOLDS = PressureThresholds(
    vram_moderate=60, vram_high=80, vram_critical=92,
    util_moderate=70, util_high=85, util_critical=95,
    temp_critical=85,
)


def _sample(util=10, vram_used=1000, vram_total=6144, temp=40):
    return GpuSample(util_pct=util, vram_used_mib=vram_used, vram_total_mib=vram_total, temp_c=temp)


def _evaluator(window=5, hysteresis=2):
    return PressureEvaluator(window_samples=window, hysteresis_samples=hysteresis, thresholds=THRESHOLDS)


def test_low_pressure_stays_low():
    ev = _evaluator()
    for _ in range(5):
        level = ev.ingest(_sample(util=10, vram_used=500))
    assert level == "LOW"


def test_moderate_pressure_after_hysteresis():
    """A single elevated sample already pushes the (1-element) median over threshold, making
    it a hysteresis *candidate* - but the level only actually changes once that candidate has
    persisted for `hysteresis_samples` consecutive evaluations."""
    ev = _evaluator(window=5, hysteresis=2)
    level = ev.ingest(_sample(util=75, vram_used=500))
    assert level == "LOW", "one sample over threshold is a candidate, not yet a transition"
    level = ev.ingest(_sample(util=75, vram_used=500))
    assert level == "MODERATE", "two consecutive samples at the candidate level should commit it"


def test_high_and_critical_pressure():
    ev = _evaluator(window=3, hysteresis=1)
    for _ in range(3):
        level = ev.ingest(_sample(util=90, vram_used=500))
    assert level == "HIGH"
    for _ in range(3):
        level = ev.ingest(_sample(util=98, vram_used=500))
    assert level == "CRITICAL"


def test_critical_temperature_overrides_low_util():
    ev = _evaluator(hysteresis=1)
    level = ev.ingest(_sample(util=5, vram_used=100, temp=90))
    assert level == "CRITICAL"


def test_vram_pct_drives_pressure_independent_of_util():
    ev = _evaluator(hysteresis=1)
    level = ev.ingest(_sample(util=5, vram_used=5800, vram_total=6144))  # ~94% VRAM
    assert level == "CRITICAL"


def test_hysteresis_prevents_flapping_on_oscillating_input():
    """A single sample crossing back below threshold must not immediately drop the level -
    only a sustained streak at the candidate level changes anything. window=1 isolates
    hysteresis specifically: with a 1-sample window the rolling median equals the raw sample,
    so this test exercises the hysteresis stage alone, not the median-smoothing stage."""
    ev = _evaluator(window=1, hysteresis=3)
    ev.ingest(_sample(util=10))
    ev.ingest(_sample(util=90))  # candidate HIGH, streak 1
    ev.ingest(_sample(util=10))  # back to matching current (LOW) - resets candidate
    level = ev.ingest(_sample(util=90))  # candidate HIGH again, streak restarts at 1
    assert level == "LOW", "a single oscillation must not have flipped the level"


def test_telemetry_loss_fails_safe_to_moderate_not_low():
    ev = _evaluator()
    assert ev.current_level == "LOW"
    level = ev.ingest(None)
    assert level == "MODERATE"
    assert ev.telemetry_healthy is False


def test_telemetry_loss_does_not_downgrade_an_already_higher_level():
    ev = _evaluator(hysteresis=1)
    ev.ingest(_sample(util=98))  # CRITICAL
    level = ev.ingest(None)
    assert level == "CRITICAL", "losing telemetry must never look safer than the last known state"
