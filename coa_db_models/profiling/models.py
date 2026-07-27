import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from coa_db_models.base import Base


class ItemProfileRun(Base):
    __tablename__ = "item_profile_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    source_file_ref: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    field_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    migration_key_field: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fields_processed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    duplicate_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    cross_subsidiary_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    invalid_uom_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    missing_product_type_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interpretation_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_actions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    field_profiles: Mapped[list["ItemFieldProfile"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    decisions: Mapped[list["ItemProfileDecision"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_item_profile_runs_status", "status"),)


class ItemFieldProfile(Base):
    __tablename__ = "item_field_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("item_profile_runs.id", ondelete="CASCADE"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(255), nullable=False)
    detected_type: Mapped[str] = mapped_column(String(50), nullable=False, server_default="string")
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    null_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    distinct_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cardinality: Mapped[str | None] = mapped_column(String(10), nullable=True)
    pattern_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    anomaly_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anomaly_examples: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    semantic_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    stats: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    odoo_target: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    run: Mapped["ItemProfileRun"] = relationship(back_populates="field_profiles")

    __table_args__ = (
        UniqueConstraint("run_id", "field_name", name="uq_field_profile_run_field"),
        Index("ix_item_field_profiles_run_id", "run_id"),
    )


class ItemProfileDecision(Base):
    __tablename__ = "item_profile_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("item_profile_runs.id", ondelete="CASCADE"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False, server_default="review")
    fix_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    transformation_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    run: Mapped["ItemProfileRun"] = relationship(back_populates="decisions")
    audit_log: Mapped[list["ItemProfileAudit"]] = relationship(
        back_populates="decision", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_item_profile_decisions_run_id", "run_id"),)


class ItemProfileAudit(Base):
    __tablename__ = "item_profile_audit"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("item_profile_decisions.id", ondelete="CASCADE"), nullable=False
    )
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    previous_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_state: Mapped[dict] = mapped_column(JSONB, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    decision: Mapped["ItemProfileDecision"] = relationship(back_populates="audit_log")

    __table_args__ = (Index("ix_item_profile_audit_decision_id", "decision_id"),)
