import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql.expression import true as sa_true
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from coa_db_models.auth.models import User  # noqa: F401 — needed for FK resolution
from coa_db_models.base import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_system: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    target_system: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    organization: Mapped["Organization"] = relationship(back_populates="projects")
    access_list: Mapped[list["ProjectAccess"]] = relationship(back_populates="project", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_projects_status", "status"),)


class ProjectAccess(Base):
    __tablename__ = "project_access"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    permission: Mapped[str] = mapped_column(String(20), nullable=False, server_default="viewer")
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    project: Mapped["Project"] = relationship(back_populates="access_list")
    user: Mapped["User"] = relationship(foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("user_id", "project_id", name="uq_user_project"),
        Index("ix_project_access_user_id", "user_id"),
        Index("ix_project_access_project_id", "project_id"),
    )


from coa_db_models.auth.models import Organization  # noqa: E402, F811 — needed for relationship resolution


class ProjectMasterDataSelection(Base):
    __tablename__ = "project_master_data_selections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    org_project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    scope_name: Mapped[str] = mapped_column(String(100), nullable=False)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_true())

    __table_args__ = (
        CheckConstraint(
            "(project_id IS NOT NULL OR org_project_id IS NOT NULL)",
            name="ck_master_data_sel_at_least_one",
        ),
    )


class ProjectOpeningBalanceSelection(Base):
    __tablename__ = "project_opening_balance_selections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    org_project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    account_type: Mapped[str] = mapped_column(String(100), nullable=False)
    include: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_true())

    __table_args__ = (
        CheckConstraint(
            "(project_id IS NOT NULL AND org_project_id IS NULL) OR "
            "(project_id IS NULL AND org_project_id IS NOT NULL)",
            name="ck_opening_bal_sel_project_xor",
        ),
    )


class ProjectWizardFields(Base):
    __tablename__ = "project_wizard_fields"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    source_vendor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_vendor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_connection_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_connection_method: Mapped[str | None] = mapped_column(String(100), nullable=True)


class ProjectDisplayCode(Base):
    """Display code for either a COA project or an org project.

    Exactly one of project_id / org_project_id is set (XOR).
    Sequence is global per (org_part, source_part, target_part) prefix so
    codes are unique across both project types within an organisation.
    """

    __tablename__ = "project_display_codes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, unique=True
    )
    org_project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_projects.id", ondelete="CASCADE"), nullable=True, unique=True
    )
    display_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    org_part: Mapped[str] = mapped_column(String(10), nullable=False)
    source_part: Mapped[str] = mapped_column(String(10), nullable=False)
    target_part: Mapped[str] = mapped_column(String(10), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "(project_id IS NOT NULL AND org_project_id IS NULL) OR "
            "(project_id IS NULL AND org_project_id IS NOT NULL)",
            name="ck_display_codes_project_xor",
        ),
    )


class OrgProject(Base):
    """Umbrella project container for all non-COA migration scopes within an org."""

    __tablename__ = "org_projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_system: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    target_system: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_org_projects_status", "status"),)


class OrgProjectAccess(Base):
    __tablename__ = "org_project_access"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    org_project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_projects.id", ondelete="CASCADE"), nullable=False
    )
    permission: Mapped[str] = mapped_column(String(20), nullable=False, server_default="viewer")
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "org_project_id", name="uq_user_org_project"),
        Index("ix_org_project_access_user_id", "user_id"),
        Index("ix_org_project_access_org_project_id", "org_project_id"),
    )


class OrgProjectWizardFields(Base):
    __tablename__ = "org_project_wizard_fields"

    org_project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_projects.id", ondelete="CASCADE"), primary_key=True
    )
    source_vendor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_vendor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_connection_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_connection_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
