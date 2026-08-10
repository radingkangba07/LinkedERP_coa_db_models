import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.sql.expression import true as sa_true

from coa_db_models.base import Base


class MasterDataEntity(Base):
    __tablename__ = "master_data_entities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_true())


class WorkstreamCategory(Base):
    __tablename__ = "workstream_categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    display_code_prefix: Mapped[str] = mapped_column(String(10), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Workstream(Base):
    __tablename__ = "workstreams"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    org_project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_projects.id", ondelete="CASCADE"), nullable=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workstream_categories.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_code: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="not_started")
    current_stage: Mapped[str] = mapped_column(String(50), nullable=False, server_default="erp_select")
    is_included: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_true())
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("master_data_entities.id", ondelete="RESTRICT"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "(project_id IS NOT NULL AND org_project_id IS NULL) OR "
            "(project_id IS NULL AND org_project_id IS NOT NULL)",
            name="ck_workstream_project_xor",
        ),
        UniqueConstraint("project_id", "display_code", name="uq_workstream_project_display_code"),
        UniqueConstraint("org_project_id", "display_code", name="uq_workstream_org_project_display_code"),
        UniqueConstraint("project_id", "entity_id", name="uq_workstream_project_entity"),
        UniqueConstraint("org_project_id", "entity_id", name="uq_workstream_org_project_entity"),
        Index("ix_workstreams_org_id", "org_id"),
        Index("ix_workstreams_project_id", "project_id"),
        Index("ix_workstreams_org_project_id", "org_project_id"),
        Index("ix_workstreams_status", "status"),
        Index("ix_workstreams_entity_id", "entity_id"),
    )


class WorkstreamStage(Base):
    __tablename__ = "workstream_stages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    workstream_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workstreams.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (Index("ix_workstream_stages_workstream_id", "workstream_id"),)


class EntityPack(Base):
    __tablename__ = "entity_packs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    workstream_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workstreams.id", ondelete="CASCADE"), nullable=False
    )
    pack: Mapped[dict] = mapped_column(JSONB, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(50), nullable=False)
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_files.id", ondelete="SET NULL"), nullable=True
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_entity_packs_workstream_id", "workstream_id"),
        Index("ix_entity_packs_workstream_current", "workstream_id", "is_current"),
        Index(
            "uq_entity_packs_workstream_current",
            "workstream_id",
            unique=True,
            postgresql_where=text("is_current = true"),
        ),
    )


class FieldDecision(Base):
    __tablename__ = "field_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    workstream_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workstreams.id", ondelete="CASCADE"), nullable=False
    )
    field_id: Mapped[str] = mapped_column(String(100), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    target_field_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    previous_target_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    decision_source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="user")
    approval_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_true())
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_field_decisions_workstream_id", "workstream_id"),
        Index("ix_field_decisions_workstream_field_active", "workstream_id", "field_id", "is_active"),
    )


class WorkstreamStatusLog(Base):
    __tablename__ = "workstream_status_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    workstream_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workstreams.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    previous_status: Mapped[str] = mapped_column(String(50), nullable=False)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (Index("ix_workstream_status_logs_workstream_id", "workstream_id"),)
