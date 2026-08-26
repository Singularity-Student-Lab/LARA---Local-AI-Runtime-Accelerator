"""SQLAlchemy ORM entities. Field lists follow blueprint section 21 exactly.

Tables are added incrementally, phase by phase, matching the session that introduces them:
roles/users/api_keys/inference_backends/models here (Phase C / Session 3); jobs (Phase E /
Session 4); operating_mode (Phase F / Session 5); audit_events (Phase C, used from Session 3
onward for admin actions); gpu_samples/gpu_samples_hourly/usage_daily (Phase H / Session 7).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    users: Mapped[list["User"]] = relationship(back_populates="role")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    role_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("roles.id"), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    role: Mapped["Role"] = relationship(back_populates="users")
    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="user")


class ApiKey(Base):
    __tablename__ = "api_keys"

    key_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    secret_hash: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="api_keys")

    __table_args__ = (
        Index("ix_api_keys_user_id", "user_id"),
        Index("ix_api_keys_active", "revoked_at", postgresql_where=(revoked_at.is_(None))),  # type: ignore[has-type]
    )


class InferenceBackend(Base):
    __tablename__ = "inference_backends"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    runtime: Mapped[str] = mapped_column(String(32), nullable=False)  # "vllm" or "ollama"
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ModelRegistry(Base):
    __tablename__ = "models"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alias: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    backend_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("inference_backends.id"), nullable=False)
    model_ref: Mapped[str] = mapped_column(Text, nullable=False)
    quantization: Mapped[str | None] = mapped_column(String(64), nullable=True)
    context_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    max_output_default: Mapped[int | None] = mapped_column(Integer, nullable=True)
    config_file: Mapped[str | None] = mapped_column(String(256), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    backend: Mapped["InferenceBackend"] = relationship()

    __table_args__ = (
        Index(
            "ix_models_single_default",
            "is_default",
            unique=True,
            postgresql_where=(is_default.is_(True)),  # type: ignore[has-type]
        ),
    )


class Job(Base):
    """One row per inference request (blueprint section 21.6). Never stores prompt, message,
    or response content - counts and timings only (PRD 12.4)."""

    __tablename__ = "jobs"

    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    key_id: Mapped[str] = mapped_column(String(32), ForeignKey("api_keys.key_id"), nullable=False)
    model_alias: Mapped[str] = mapped_column(String(128), nullable=False)
    backend_name: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_priority: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="RECEIVED")
    stream: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    queue_wait_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generation_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ttft_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    error_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_ip_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)

    __table_args__ = (
        Index("ix_jobs_user_received_at", "user_id", "received_at"),
        Index(
            "ix_jobs_active_status",
            "status",
            postgresql_where=(status.in_(["QUEUED", "RUNNING"])),  # type: ignore[has-type]
        ),
        Index("ix_jobs_received_at", "received_at"),
        Index("ix_jobs_alias_received_at", "model_alias", "received_at"),
    )


class OperatingMode(Base):
    """Single-row table: current mode, changed_at, changed_by, plus a `switching` flag used
    during model switches (blueprint section 21.7). History lives in audit_events."""

    __tablename__ = "operating_mode"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="SERVING")
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    changed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    switching: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class GpuSample(Base):
    """Periodic GPU and system telemetry (blueprint section 21.7). Fastest-growing table -
    retention and hourly aggregation are not optional (Phase H / Session 7)."""

    __tablename__ = "gpu_samples"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    gpu_util_pct: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    vram_used_mib: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    vram_total_mib: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    temp_c: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    power_w: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    # Recorded as the collector CONTAINER's view, not necessarily the true host view -
    # documented explicitly in docs/architecture/telemetry.md, per blueprint's own caveat
    # pattern for the WSL2-vs-Windows case (section 7 point 2).
    cpu_pct: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    ram_used_mib: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    active_jobs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    queue_depth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    telemetry_healthy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (Index("ix_gpu_samples_sampled_at", "sampled_at"),)


class GpuSampleHourly(Base):
    __tablename__ = "gpu_samples_hourly"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    hour: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    gpu_util_min: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    gpu_util_mean: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    gpu_util_max: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    gpu_util_p95: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    vram_used_mean: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    vram_used_max: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    temp_mean: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    temp_max: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (Index("ix_gpu_samples_hourly_hour", "hour", unique=True),)


class UsageDaily(Base):
    """Analytics and leaderboard rollups (blueprint section 21.8). Kept after `jobs` rows are
    deleted by retention - that's the point of the rollup."""

    __tablename__ = "usage_daily"

    day: Mapped[str] = mapped_column(String(10), primary_key=True)  # ISO date, e.g. 2026-08-12
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    model_alias: Mapped[str] = mapped_column(String(128), primary_key=True)

    requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancelled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    input_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    generation_ms_total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    queue_wait_ms_mean: Mapped[int | None] = mapped_column(Integer, nullable=True)
    queue_wait_ms_p95: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ttft_ms_mean: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ttft_ms_p95: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ENGINEERING RECOMMENDATION (blueprint section 21.8): a session is approximated as a run
    # of requests from one key with gaps below LARA_SESSION_IDLE_GAP_S. Recorded here so the
    # definition travels with the number.
    agent_sessions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str | None] = mapped_column(String(256), nullable=True)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    source_ip_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)

    __table_args__ = (
        Index("ix_audit_events_occurred_at", "occurred_at"),
        Index("ix_audit_events_type_occurred_at", "event_type", "occurred_at"),
    )
