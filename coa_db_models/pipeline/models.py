from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from coa_db_models.base import Base

_VALID_SCOPES = (
    "'items','customers','vendors','locations','contacts','vehicles','equipment','fixed_assets'"
)
_VALID_RUN_STATUSES = "'pending','running','complete','failed','error'"


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    workstream_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workstreams.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending"
    )
    source_file_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    source_row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    field_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fields_processed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    run_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        CheckConstraint(
            f"scope IN ({_VALID_SCOPES})",
            name="ck_pipeline_runs_scope",
        ),
        CheckConstraint(
            f"status IN ({_VALID_RUN_STATUSES})",
            name="ck_pipeline_runs_status",
        ),
        # Prevents two active runs for the same workstream+scope simultaneously.
        Index(
            "uix_pipeline_runs_workstream_scope_active",
            "workstream_id",
            "scope",
            unique=True,
            postgresql_where=text("status NOT IN ('complete','failed','error')"),
        ),
        Index("ix_pipeline_runs_workstream_id", "workstream_id"),
        Index("ix_pipeline_runs_org_id", "org_id"),
        Index("ix_pipeline_runs_status", "status"),
        Index("ix_pipeline_runs_scope", "scope"),
    )


class FieldProfile(Base):
    __tablename__ = "field_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    # --- scalar dimensions (match analyse_column() return keys exactly) ---
    field_name: Mapped[str] = mapped_column(String(255), nullable=False)
    detected_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # format_detected: set for compact date formats (e.g. YYYYMMDD, DDMMYYYY); NULL for all others
    format_detected: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # user_override_type: what the user chose; NULL = use detected_type
    user_override_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # override_status: pending = ML re-analysis queued; complete = stats updated; NULL = no override
    override_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # audit: who requested the override and when
    overridden_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    overridden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    null_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distinct_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cardinality: Mapped[str | None] = mapped_column(String(20), nullable=True)
    duplicate_row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duplicate_group_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    invalid_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reference_failures: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_enumeration_candidate: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    pattern_anomalies: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anomaly_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    semantic_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    role_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # --- JSONB blobs ---
    stats: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    pattern_summary: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    anomaly_examples: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    enumeration_detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sample_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    value_distribution: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "severity IN ('blocker','warning','review','clean')",
            name="ck_field_profiles_severity",
        ),
        CheckConstraint(
            "cardinality IN ('near_empty','low','medium','high')",
            name="ck_field_profiles_cardinality",
        ),
        CheckConstraint(
            "detected_type IS NULL OR detected_type IN ('text','integer','decimal','date','boolean')",
            name="ck_field_profiles_detected_type",
        ),
        CheckConstraint(
            "user_override_type IS NULL OR user_override_type IN ('text','integer','decimal','date','boolean')",
            name="ck_field_profiles_override_type",
        ),
        CheckConstraint(
            "override_status IS NULL OR override_status IN ('pending','complete')",
            name="ck_field_profiles_override_status",
        ),
        CheckConstraint(
            "semantic_role IS NULL OR semantic_role IN "
            "('identifier_candidate','display_name','descriptive_text','measure','value_list','timestamp','ambiguous')",
            name="ck_field_profiles_semantic_role",
        ),
        Index("ix_field_profiles_run_id", "run_id"),
        Index("ix_field_profiles_run_field", "run_id", "field_name"),
        Index("ix_field_profiles_run_severity", "run_id", "severity"),
        # Used by the "block navigation if any override pending" gate
        Index("ix_field_profiles_run_override_status", "run_id", "override_status"),
    )
