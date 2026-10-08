"""Shared transactional outbox.

A service writes an OutboxEvent in the same transaction as the state change
it announces. A relay publishes pending events to NATS JetStream with
dedup_key as the Nats-Msg-Id header, so a retried publish is de-duplicated by
the stream, and consumers de-duplicate by the same key. Any module can use
this table; it is not specific to one subject.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from coa_db_models.base import Base


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    dedup_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('pending','published','dead')", name="ck_outbox_events_status"),
        Index("ix_outbox_events_pending", "available_at", postgresql_where=text("status = 'pending'")),
        Index("ix_outbox_events_aggregate", "aggregate_type", "aggregate_id"),
    )
