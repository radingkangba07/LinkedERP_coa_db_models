from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from coa_db_models.base import Base


class OrgERPConnection(Base):
    __tablename__ = "org_erp_connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    erp_id: Mapped[str] = mapped_column(String(50), nullable=False)
    connection_role: Mapped[str] = mapped_column(String(20), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    auth_strategy: Mapped[str] = mapped_column(String(20), nullable=False)

    # Public config only — no secrets ever stored here.
    # oauth2:    {"client_id": "..."}
    # tba:       {"consumer_key": "...", "token_id": "..."}
    # tally_xml: {"port": 9000}
    # api_key:   {}
    erp_config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    # Credentials are never persisted — they are passed per-job by the
    # frontend and travel encrypted in the NATS message payload only.

    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'active'"))
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    health_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    catalogue_seeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Optimistic locking — 409 on concurrent admin edits.
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))

    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("erp_id IN ('odoo','netsuite','tally','generic')", name="ck_org_erp_connections_erp_id"),
        CheckConstraint("connection_role IN ('source','target')", name="ck_org_erp_connections_role"),
        CheckConstraint(
            "auth_strategy IN ('api_key','tba','oauth2','bearer','tally_xml')",
            name="ck_org_erp_connections_auth_strategy",
        ),
        CheckConstraint(
            "status IN ('active','broken','requires_reauth','tally_unreachable')",
            name="ck_org_erp_connections_status",
        ),
        Index("uix_org_erp_connections_org_label", "org_id", "label", unique=True),
        Index(
            "uix_org_erp_connections_active",
            "org_id", "erp_id", "connection_role",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )
