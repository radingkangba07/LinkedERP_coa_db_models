"""dab68: add import run tables (wizard step 7 — sandbox ERP import)

Adds four tables that power the controlled sandbox import UI:
  import_runs          — one per ERP sandbox import triggered from a pipeline_run
  import_records       — one row per source record, tracks outcome and target ERP id
  connector_requests   — full audit log of every ERP API call (request + response)
  import_errors        — per-failure detail with deterministic + AI classification

All four cascade-delete from import_runs; import_runs cascades from pipeline_runs,
so deleting a pipeline run cleans up the full import history.

Revision ID: dab69
Revises: dab67
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "dab69"
down_revision: Union[str, Sequence[str], None] = "dab68"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Each table is guarded independently so a partial failure on a prior run
    # can be recovered by re-running upgrade — only the missing tables are created.

    # ── import_runs ──────────────────────────────────────────────────────────
    if not inspector.has_table("import_runs"):
        op.create_table(
            "import_runs",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("triggered_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
            sa.Column("run_code", sa.String(50), nullable=True),
            sa.Column("batch_size", sa.Integer, nullable=False, server_default=sa.text("20")),
            sa.Column("req_per_sec", sa.Integer, nullable=False, server_default=sa.text("4")),
            sa.Column("rows_attempted", sa.Integer, nullable=True),
            sa.Column("rows_imported", sa.Integer, nullable=True),
            sa.Column("rows_failed", sa.Integer, nullable=True),
            sa.Column("rows_skipped", sa.Integer, nullable=True),
            sa.Column("rows_reconciled", sa.Integer, nullable=True),
            sa.Column("duration_ms", sa.Integer, nullable=True),
            sa.Column("error_detail", sa.Text, nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint(
                "status IN ('pending','running','complete','failed')",
                name="ck_import_runs_status",
            ),
        )
        op.create_index("ix_import_runs_run_id", "import_runs", ["run_id"])
        op.create_index("ix_import_runs_status", "import_runs", ["status"])
        op.create_index(
            "uix_import_runs_run_active",
            "import_runs",
            ["run_id"],
            unique=True,
            postgresql_where=sa.text("status IN ('pending', 'running')"),
        )

    else:
        # Backfill: add updated_at to environments that created import_runs before this column existed.
        existing_cols = {c["name"] for c in inspector.get_columns("import_runs")}
        if "updated_at" not in existing_cols:
            op.add_column("import_runs", sa.Column(
                "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
            ))

    # ── import_records ───────────────────────────────────────────────────────
    if not inspector.has_table("import_records"):
        op.create_table(
            "import_records",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("import_run_id", UUID(as_uuid=True), sa.ForeignKey("import_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_row_index", sa.Integer, nullable=False),
            sa.Column("internal_id", sa.String(255), nullable=True),
            sa.Column("display_name", sa.String(500), nullable=True),
            sa.Column("batch_code", sa.String(50), nullable=False),
            sa.Column("outcome", sa.String(20), nullable=False),
            sa.Column("target_id", sa.String(255), nullable=True),
            sa.Column("latency_ms", sa.Integer, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint(
                "outcome IN ('imported','failed','skipped')",
                name="ck_import_records_outcome",
            ),
            sa.UniqueConstraint("import_run_id", "source_row_index", name="uix_import_records_run_row"),
        )
        op.create_index("ix_import_records_import_run_id", "import_records", ["import_run_id"])
        op.create_index("ix_import_records_batch_code", "import_records", ["import_run_id", "batch_code"])
        op.create_index("ix_import_records_outcome", "import_records", ["import_run_id", "outcome"])

    # ── connector_requests ───────────────────────────────────────────────────
    if not inspector.has_table("connector_requests"):
        op.create_table(
            "connector_requests",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("import_run_id", UUID(as_uuid=True), sa.ForeignKey("import_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("request_code", sa.String(50), nullable=False),
            sa.Column("operation", sa.String(50), nullable=False),
            sa.Column("erp_model", sa.String(255), nullable=True),
            sa.Column("record_ref", sa.String(255), nullable=True),
            sa.Column("batch_code", sa.String(50), nullable=False),
            sa.Column("http_status", sa.Integer, nullable=True),
            sa.Column("latency_ms", sa.Integer, nullable=True),
            sa.Column("retries", sa.Integer, nullable=False, server_default=sa.text("0")),
            sa.Column("request_payload", JSONB, nullable=True),
            sa.Column("response_payload", JSONB, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("import_run_id", "request_code", name="uix_connector_requests_run_code"),
            sa.CheckConstraint(
                "operation IN ('create','update','delete','validate')",
                name="ck_connector_requests_operation",
            ),
        )
        op.create_index("ix_connector_requests_import_run_id", "connector_requests", ["import_run_id"])
        op.create_index("ix_connector_requests_batch_code", "connector_requests", ["import_run_id", "batch_code"])
    else:
        # Backfill: widen the operation CHECK constraint to include 'validate' on pre-existing tables.
        # Guard the drop: the constraint may not exist if the table was created without it.
        existing_ck_names = {c["name"] for c in inspector.get_check_constraints("connector_requests")}
        if "ck_connector_requests_operation" in existing_ck_names:
            op.drop_constraint("ck_connector_requests_operation", "connector_requests", type_="check")
        op.create_check_constraint(
            "ck_connector_requests_operation",
            "connector_requests",
            "operation IN ('create','update','delete','validate')",
        )

    # ── import_errors ────────────────────────────────────────────────────────
    if not inspector.has_table("import_errors"):
        op.create_table(
            "import_errors",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("import_run_id", UUID(as_uuid=True), sa.ForeignKey("import_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("connector_request_id", UUID(as_uuid=True), sa.ForeignKey("connector_requests.id", ondelete="SET NULL"), nullable=True),
            sa.Column("source_row_index", sa.Integer, nullable=False),
            sa.Column("record_ref", sa.String(255), nullable=True),
            sa.Column("batch_code", sa.String(50), nullable=False),
            sa.Column("error_title", sa.String(500), nullable=False),
            sa.Column("error_detail", sa.Text, nullable=True),
            sa.Column("retry_class", sa.String(20), nullable=False),
            sa.Column("parsed_by", sa.String(20), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'open'")),
            sa.Column("idempotency_key", sa.String(255), nullable=True),
            sa.Column("source_field", sa.String(255), nullable=True),
            sa.Column("raw_value", sa.Text, nullable=True),
            sa.Column("written_to", sa.String(255), nullable=True),
            sa.Column("value_sent", sa.Text, nullable=True),
            sa.Column("erp_response", sa.Text, nullable=True),
            sa.Column("deterministic_rule", sa.String(255), nullable=True),
            sa.Column("ai_analysis", sa.Text, nullable=True),
            sa.Column("ai_likely_cause", sa.Text, nullable=True),
            sa.Column("ai_cause_category", sa.String(100), nullable=True),
            sa.Column("ai_fix_suggestion", sa.Text, nullable=True),
            sa.Column("ai_fix_step", sa.String(50), nullable=True),
            sa.Column("ai_model", sa.String(100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint(
                "retry_class IN ('permanent','transient')",
                name="ck_import_errors_retry_class",
            ),
            sa.CheckConstraint(
                "parsed_by IN ('deterministic','ai')",
                name="ck_import_errors_parsed_by",
            ),
            sa.CheckConstraint(
                "status IN ('open','resolved')",
                name="ck_import_errors_status",
            ),
        )
        op.create_index("ix_import_errors_import_run_id", "import_errors", ["import_run_id"])
        op.create_index("ix_import_errors_batch_code", "import_errors", ["import_run_id", "batch_code"])
        op.create_index("ix_import_errors_status", "import_errors", ["import_run_id", "status"])
        op.create_index("ix_import_errors_run_row", "import_errors", ["import_run_id", "source_row_index"])
        op.create_index(
            "uix_import_errors_idempotency",
            "import_errors",
            ["import_run_id", "idempotency_key"],
            unique=True,
            postgresql_where=sa.text("idempotency_key IS NOT NULL"),
        )
    else:
        # Backfill: add new indexes to environments that created import_errors before these existed.
        existing_indexes = {i["name"] for i in inspector.get_indexes("import_errors")}
        if "ix_import_errors_run_row" not in existing_indexes:
            op.create_index("ix_import_errors_run_row", "import_errors", ["import_run_id", "source_row_index"])
        if "uix_import_errors_idempotency" not in existing_indexes:
            op.create_index(
                "uix_import_errors_idempotency",
                "import_errors",
                ["import_run_id", "idempotency_key"],
                unique=True,
                postgresql_where=sa.text("idempotency_key IS NOT NULL"),
            )


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("import_runs"):
        return

    op.drop_index("uix_import_errors_idempotency", table_name="import_errors")
    op.drop_index("ix_import_errors_run_row", table_name="import_errors")
    op.drop_index("ix_import_errors_status", table_name="import_errors")
    op.drop_index("ix_import_errors_batch_code", table_name="import_errors")
    op.drop_index("ix_import_errors_import_run_id", table_name="import_errors")
    op.drop_table("import_errors")

    op.drop_index("ix_connector_requests_batch_code", table_name="connector_requests")
    op.drop_index("ix_connector_requests_import_run_id", table_name="connector_requests")
    op.drop_constraint("uix_connector_requests_run_code", "connector_requests", type_="unique")
    op.drop_table("connector_requests")

    op.drop_index("ix_import_records_outcome", table_name="import_records")
    op.drop_index("ix_import_records_batch_code", table_name="import_records")
    op.drop_index("ix_import_records_import_run_id", table_name="import_records")
    op.drop_constraint("uix_import_records_run_row", "import_records", type_="unique")
    op.drop_table("import_records")

    op.drop_index("uix_import_runs_run_active", table_name="import_runs")
    op.drop_index("ix_import_runs_status", table_name="import_runs")
    op.drop_index("ix_import_runs_run_id", table_name="import_runs")
    op.drop_table("import_runs")
