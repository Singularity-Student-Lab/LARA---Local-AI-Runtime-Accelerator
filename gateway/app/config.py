"""Environment-only settings. No secret ever has a default value here (blueprint section 23.1)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Session 1
    lara_env: str = Field(default="dev", alias="LARA_ENV")
    lara_log_level: str = Field(default="info", alias="LARA_LOG_LEVEL")

    # Session 2
    lara_vllm_base_url: str = Field(default="http://lara-inference:8000", alias="LARA_VLLM_BASE_URL")
    lara_ollama_base_url: str = Field(default="http://host.docker.internal:11434", alias="LARA_OLLAMA_BASE_URL")

    # Session 3
    database_url: str = Field(alias="DATABASE_URL")
    lara_api_key_pepper: str = Field(alias="LARA_API_KEY_PEPPER")
    lara_default_backend: str = Field(default="ollama-dev", alias="LARA_DEFAULT_BACKEND")
    lara_default_model_alias: str = Field(default="campus-coder", alias="LARA_DEFAULT_MODEL_ALIAS")
    lara_max_request_bytes: int = Field(default=2_097_152, alias="LARA_MAX_REQUEST_BYTES")
    lara_connect_timeout_s: float = Field(default=5.0, alias="LARA_CONNECT_TIMEOUT_S")
    lara_ttft_timeout_s: float = Field(default=60.0, alias="LARA_TTFT_TIMEOUT_S")
    lara_request_timeout_s: float = Field(default=300.0, alias="LARA_REQUEST_TIMEOUT_S")
    lara_transcript_logging: bool = Field(default=False, alias="LARA_TRANSCRIPT_LOGGING")

    # Session 4
    lara_max_active_jobs: int = Field(default=3, alias="LARA_MAX_ACTIVE_JOBS")
    lara_per_user_max_active: int = Field(default=1, alias="LARA_PER_USER_MAX_ACTIVE")
    lara_queue_max_depth: int = Field(default=50, alias="LARA_QUEUE_MAX_DEPTH")
    lara_queue_timeout_s: float = Field(default=120.0, alias="LARA_QUEUE_TIMEOUT_S")
    lara_sse_keepalive_s: float = Field(default=5.0, alias="LARA_SSE_KEEPALIVE_S")

    # Session 5
    lara_mode_default: str = Field(default="SERVING", alias="LARA_MODE_DEFAULT")
    lara_gpu_sample_interval_s: float = Field(default=5.0, alias="LARA_GPU_SAMPLE_INTERVAL_S")
    lara_pressure_window_samples: int = Field(default=12, alias="LARA_PRESSURE_WINDOW_SAMPLES")
    lara_pressure_hysteresis_samples: int = Field(default=3, alias="LARA_PRESSURE_HYSTERESIS_SAMPLES")
    lara_pressure_vram_moderate: float = Field(default=60.0, alias="LARA_PRESSURE_VRAM_MODERATE")
    lara_pressure_vram_high: float = Field(default=80.0, alias="LARA_PRESSURE_VRAM_HIGH")
    lara_pressure_vram_critical: float = Field(default=92.0, alias="LARA_PRESSURE_VRAM_CRITICAL")
    lara_pressure_util_moderate: float = Field(default=70.0, alias="LARA_PRESSURE_UTIL_MODERATE")
    lara_pressure_util_high: float = Field(default=85.0, alias="LARA_PRESSURE_UTIL_HIGH")
    lara_pressure_util_critical: float = Field(default=95.0, alias="LARA_PRESSURE_UTIL_CRITICAL")
    lara_pressure_temp_critical: float = Field(default=85.0, alias="LARA_PRESSURE_TEMP_CRITICAL")
    lara_drain_timeout_s: float = Field(default=60.0, alias="LARA_DRAIN_TIMEOUT_S")

    # Session 6
    lara_public_base_url: str = Field(default="", alias="LARA_PUBLIC_BASE_URL")
    lara_rate_limit_requests: int = Field(default=60, alias="LARA_RATE_LIMIT_REQUESTS")
    lara_rate_limit_window_s: float = Field(default=60.0, alias="LARA_RATE_LIMIT_WINDOW_S")
    lara_auth_fail_threshold: int = Field(default=10, alias="LARA_AUTH_FAIL_THRESHOLD")
    lara_auth_fail_window_s: float = Field(default=60.0, alias="LARA_AUTH_FAIL_WINDOW_S")
    lara_auth_fail_block_s: float = Field(default=300.0, alias="LARA_AUTH_FAIL_BLOCK_S")
    lara_trusted_proxy_headers: bool = Field(default=False, alias="LARA_TRUSTED_PROXY_HEADERS")

    # Session 7
    lara_retention_jobs_days: int = Field(default=90, alias="LARA_RETENTION_JOBS_DAYS")
    lara_retention_gpu_raw_days: int = Field(default=14, alias="LARA_RETENTION_GPU_RAW_DAYS")
    lara_retention_audit_days: int = Field(default=365, alias="LARA_RETENTION_AUDIT_DAYS")
    lara_log_max_gb: float = Field(default=20.0, alias="LARA_LOG_MAX_GB")
    lara_leaderboard_enabled: bool = Field(default=True, alias="LARA_LEADERBOARD_ENABLED")
    lara_leaderboard_weights: str = Field(
        default='{"successful_requests": 1.0, "active_days": 5.0, "agent_sessions": 3.0, "tokens": 0.001}',
        alias="LARA_LEADERBOARD_WEIGHTS",
    )

    @property
    def is_prod(self) -> bool:
        return self.lara_env == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()
