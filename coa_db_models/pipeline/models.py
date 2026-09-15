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
    UniqueConstraint,
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


# ---------------------------------------------------------------------------
# Target field catalogue
# ---------------------------------------------------------------------------
# Seeded from YAML for each (erp_id, scope). Replaced by MCP or uploaded
# templates when live ERP connections are available. Soft reference only —
# column_mappings stores denormalised label/dtype rather than a FK here so
# that confirmed mappings survive target catalogue refreshes.
# ---------------------------------------------------------------------------

_VALID_TARGET_SOURCES = "'seed','upload','mcp'"


class TargetField(Base):
    __tablename__ = "target_fields"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    erp_id: Mapped[str] = mapped_column(String(50), nullable=False)
    scope: Mapped[str] = mapped_column(String(100), nullable=False)
    field_id: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    dtype: Mapped[str] = mapped_column(String(50), nullable=False)
    relation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    read_only: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    identifier: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    # source tracks where this record came from — drives replacement strategy
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'seed'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            f"source IN ({_VALID_TARGET_SOURCES})",
            name="ck_target_fields_source",
        ),
        CheckConstraint(
            f"scope IN ({_VALID_SCOPES})",
            name="ck_target_fields_scope",
        ),
        # dab58 created this as a named UniqueConstraint (not a unique Index).
        # Use index_elements=[...] on ON CONFLICT — do NOT use constraint= here.
        UniqueConstraint("erp_id", "scope", "field_id", name="uix_target_fields_erp_scope_field"),
        Index("ix_target_fields_erp_scope", "erp_id", "scope"),
    )


# ---------------------------------------------------------------------------
# Column mappings  (wizard step 3)
# ---------------------------------------------------------------------------

_VALID_MAPPING_STATUSES = "'suggested','review_required','confirmed','excluded','no_safe_target'"
_VALID_MAPPING_SOURCES = "'ai','user'"
_VALID_MAPPING_VALIDATIONS = "'compatible','warning','format_conversion_required','incompatible'"


class ColumnMapping(Base):
    __tablename__ = "column_mappings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_field: Mapped[str] = mapped_column(String(255), nullable=False)
    # Soft reference — no FK on target_field_id so MCP catalogue refreshes
    # don't cascade-delete confirmed mappings.
    target_field_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_field_label: Mapped[str | None] = mapped_column(String(500), nullable=True)
    target_dtype: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'no_safe_target'"))
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    mapping_source: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'ai'"))
    validation: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # evidence: list of signal codes e.g. ['name', 'samples', 'datatype', 'prior']
    evidence: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            f"status IN ({_VALID_MAPPING_STATUSES})",
            name="ck_column_mappings_status",
        ),
        CheckConstraint(
            f"mapping_source IN ({_VALID_MAPPING_SOURCES})",
            name="ck_column_mappings_source",
        ),
        CheckConstraint(
            f"validation IS NULL OR validation IN ({_VALID_MAPPING_VALIDATIONS})",
            name="ck_column_mappings_validation",
        ),
        # dab58 created this as a named UniqueConstraint (not a unique Index).
        UniqueConstraint("run_id", "source_field", name="uix_column_mappings_run_field"),
        Index("ix_column_mappings_run_id", "run_id"),
        Index("ix_column_mappings_run_status", "run_id", "status"),
    )


class ColumnMappingHistory(Base):
    __tablename__ = "column_mapping_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    mapping_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("column_mappings.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Denormalised for direct querying without joining to column_mappings.
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    previous_target_field_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    new_target_field_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    previous_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            f"previous_status IS NULL OR previous_status IN ({_VALID_MAPPING_STATUSES})",
            name="ck_col_mapping_history_prev_status",
        ),
        CheckConstraint(
            f"new_status IS NULL OR new_status IN ({_VALID_MAPPING_STATUSES})",
            name="ck_col_mapping_history_new_status",
        ),
        Index("ix_col_mapping_history_mapping_id", "mapping_id"),
        Index("ix_col_mapping_history_run_id", "run_id"),
    )


# ---------------------------------------------------------------------------
# Org-level mapping bookmarks  (shared across column, value, and format steps)
# ---------------------------------------------------------------------------
# One row per (org_id, erp_id, scope, source_field, mapping_type).
# mapping_type discriminates the wizard step:
#   'column' — source_field → target_field
#              payload: {target_field_id, target_field_label, target_dtype}
#   'value'  — source_field + source_value → target_value
#              payload: {source_value, target_value}
#   'format' — source_field → transformation rule
#              payload: {source_format, rule}
# _auto_propose checks 'column' bookmarks first; bookmarked fields skip
# SequenceMatcher and are proposed with confidence=1.0, evidence=['prior'].
# ---------------------------------------------------------------------------

_VALID_BOOKMARK_TYPES = "'column','value','format'"


class OrgMappingBookmark(Base):
    __tablename__ = "org_mapping_bookmarks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    erp_id: Mapped[str] = mapped_column(String(50), nullable=False)
    scope: Mapped[str] = mapped_column(String(100), nullable=False)
    source_field: Mapped[str] = mapped_column(String(255), nullable=False)
    mapping_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Type-specific data — shape varies by mapping_type (see header comment).
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    bookmarked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    bookmarked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            f"mapping_type IN ({_VALID_BOOKMARK_TYPES})",
            name="ck_org_mapping_bookmarks_type",
        ),
        CheckConstraint(
            f"scope IN ({_VALID_SCOPES})",
            name="ck_org_mapping_bookmarks_scope",
        ),
        UniqueConstraint("org_id", "erp_id", "scope", "source_field", "mapping_type", name="uix_org_mapping_bookmarks"),
        Index("ix_org_mapping_bookmarks_org_erp_scope_type", "org_id", "erp_id", "scope", "mapping_type"),
    )


# ---------------------------------------------------------------------------
# Value mappings  (wizard step 4)
# ---------------------------------------------------------------------------
# One row per (run, source_field, source_value).
# Serves both the "Allowed Values" tab (Selection/Boolean target fields) and
# the "Related Records" tab (Many2one/Many2many).
# mapping_subtype is set by the ML service when posting proposals and drives
# which UI tab a row appears on.
# ---------------------------------------------------------------------------

_VALID_VALUE_TRANSFORMATION_TYPES = (
    "'replace','replace_preserve','apply_default','normalise','no_legal_target'"
)
_VALID_VALUE_EVIDENCE_TYPES = (
    "'exact_match','alias','coa_mapping','no_match','no_coa_entry','no_legal_target'"
)
_VALID_VALUE_STATUSES = "'suggested','unresolved','confirmed','blocked','excluded'"
_VALID_VALUE_MAPPING_SOURCES = "'ai','user','bookmark','coa_mapping'"
_VALID_VALUE_MAPPING_SUBTYPES = "'allowed_value','related_record'"


class ValueMapping(Base):
    __tablename__ = "value_mappings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False
    )
    source_field: Mapped[str] = mapped_column(String(255), nullable=False)
    source_value: Mapped[str] = mapped_column(Text, nullable=False)
    # Drives which tab this row appears on in the UI.
    mapping_subtype: Mapped[str] = mapped_column(String(20), nullable=False)
    records_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    records_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    # For Allowed Values tab: the crosswalked string value.
    # For Related Records tab: the display name of the resolved record.
    target_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Populated only for Related Records (Many2one/Many2many target fields).
    target_record_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    transformation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    evidence_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    evidence_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="unresolved")
    mapping_source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="ai")
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            f"mapping_subtype IN ({_VALID_VALUE_MAPPING_SUBTYPES})",
            name="ck_value_mappings_mapping_subtype",
        ),
        CheckConstraint(
            f"transformation_type IN ({_VALID_VALUE_TRANSFORMATION_TYPES})",
            name="ck_value_mappings_transformation_type",
        ),
        CheckConstraint(
            f"evidence_type IS NULL OR evidence_type IN ({_VALID_VALUE_EVIDENCE_TYPES})",
            name="ck_value_mappings_evidence_type",
        ),
        CheckConstraint(
            f"status IN ({_VALID_VALUE_STATUSES})",
            name="ck_value_mappings_status",
        ),
        CheckConstraint(
            f"mapping_source IN ({_VALID_VALUE_MAPPING_SOURCES})",
            name="ck_value_mappings_mapping_source",
        ),
        UniqueConstraint("run_id", "source_field", "source_value", name="uix_value_mappings_run_field_value"),
        Index("ix_value_mappings_run_id", "run_id"),
        Index("ix_value_mappings_run_field", "run_id", "source_field"),
        Index("ix_value_mappings_run_status", "run_id", "status"),
    )


class ValueMappingHistory(Base):
    __tablename__ = "value_mapping_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    mapping_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("value_mappings.id", ondelete="CASCADE"), nullable=False
    )
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    previous_transformation_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    previous_target_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_target_record_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    previous_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    __table_args__ = (Index("ix_value_mapping_history_mapping_id", "mapping_id"),)
