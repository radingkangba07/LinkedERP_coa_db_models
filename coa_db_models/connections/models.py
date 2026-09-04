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
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, UUID
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

    # ERP-specific public metadata — no hardcoded ERP columns.
    # netsuite oauth2/tba: {"account_id":"...", "client_id":"..."}
    # tally:               {"port": 9000}
    # odoo:                {}
    erp_config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    # OAuth2 only — Fernet-encrypted {client_secret, refresh_token}.
    # Null for all non-OAuth2 strategies.
    encrypted_oauth_data: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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
        CheckConstraint("erp_id IN ('odoo','netsuite','tally')", name="ck_org_erp_connections_erp_id"),
        CheckConstraint("connection_role IN ('source','target')", name="ck_org_erp_connections_role"),
        CheckConstraint(
            "auth_strategy IN ('api_key','tba','oauth2','bearer','tally_xml')",
            name="ck_org_erp_connections_auth_strategy",
        ),
        CheckConstraint(
            "status IN ('active','pending_oauth','broken','credential_error','requires_reauth','tally_unreachable','version_mismatch')",
            name="ck_org_erp_connections_status",
        ),
        # No two connections with the same label in one org.
        Index("uix_org_erp_connections_org_label", "org_id", "label", unique=True),
        # Only one active connection per org per erp per role.
        Index(
            "uix_org_erp_connections_active",
            "org_id", "erp_id", "connection_role",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )


class ConnectionCredentials(Base):
    """Ephemeral credential store for import jobs.

    A row exists only for the duration of a NATS import job.
    Deleted immediately in the worker finally block.
    Background task cleans up anything past expires_at (24h TTL).
    """

    __tablename__ = "connection_credentials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("org_erp_connections.id", ondelete="CASCADE"), nullable=False, index=True)
    import_job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    encrypted_blob: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
