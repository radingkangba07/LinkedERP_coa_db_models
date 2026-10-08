"""dab63: catalogue - ERP configuration versions (field groups, scope routes), shared baseline
and per-organisation account snapshots (account rows store only their differences), schema
models/fields, account discoveries, scope configurations and conversion scope models,
migration-plan bindings and the shared outbox.

Published catalogue rows and active ERP configurations are immutable, and tenant isolation
is enforced; triggers do both. catalog_effective_models/fields(snapshot) return the full
content of any snapshot.

Revision ID: dab63
Revises: dab62
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'dab63'
down_revision: Union[str, Sequence[str], None] = 'dab62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Frozen copies of coa_db_models.catalog.models IMMUTABILITY_DDL / EFFECTIVE_CONTENT_DDL / TRIGGER_DDL.
FUNCTION_DDL = (
    """
CREATE OR REPLACE FUNCTION catalog_snapshot_guard() RETURNS trigger AS $$
BEGIN
  IF OLD.status = 'published' THEN
    RAISE EXCEPTION 'catalog snapshot % is published and immutable', OLD.id USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql
""",
    """
CREATE OR REPLACE FUNCTION catalog_content_guard() RETURNS trigger AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM catalog_snapshots WHERE id = NEW.snapshot_id AND status = 'published') THEN
    RAISE EXCEPTION 'catalog snapshot % is published and immutable', NEW.snapshot_id USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql
""",
    """
CREATE OR REPLACE FUNCTION catalog_forbid_update() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION '% rows are immutable', TG_TABLE_NAME USING ERRCODE = 'check_violation';
END $$ LANGUAGE plpgsql
""",
    """
CREATE OR REPLACE FUNCTION plan_binding_guard() RETURNS trigger AS $$
BEGIN
  IF (to_jsonb(NEW) - 'status') <> (to_jsonb(OLD) - 'status')
     OR NOT (OLD.status = 'active' AND NEW.status = 'superseded') THEN
    RAISE EXCEPTION 'migration plan binding % is immutable', OLD.id USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql
""",
    """
CREATE OR REPLACE FUNCTION plan_binding_tenant_guard() RETURNS trigger AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM catalog_snapshots WHERE id IN (NEW.source_snapshot_id, NEW.target_snapshot_id)
             AND org_id IS NOT NULL AND org_id <> NEW.org_id) THEN
    RAISE EXCEPTION 'migration plan binding uses another organisation''s snapshot' USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql
""",
    """
CREATE OR REPLACE FUNCTION scope_configuration_tenant_guard() RETURNS trigger AS $$
BEGIN
  IF NEW.org_id IS DISTINCT FROM (SELECT org_id FROM catalog_snapshots WHERE id = NEW.snapshot_id) THEN
    RAISE EXCEPTION 'scope configuration owner differs from snapshot % owner', NEW.snapshot_id
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql
""",
    """
CREATE OR REPLACE FUNCTION erp_config_guard() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF OLD.status <> 'draft' THEN
      RAISE EXCEPTION 'ERP configuration % is not a draft', OLD.id USING ERRCODE = 'check_violation';
    END IF;
    RETURN OLD;
  END IF;
  IF OLD.status = 'draft' OR (OLD.status = 'active' AND NEW.status = 'retired'
                              AND (to_jsonb(NEW) - 'status') = (to_jsonb(OLD) - 'status')) THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'ERP configuration % is immutable', OLD.id USING ERRCODE = 'check_violation';
END $$ LANGUAGE plpgsql
""",
    """
CREATE OR REPLACE FUNCTION erp_config_child_guard() RETURNS trigger AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM catalog_erp_configs WHERE status <> 'draft' AND id IN (
               CASE WHEN TG_OP = 'DELETE' THEN OLD.config_id ELSE NEW.config_id END,
               CASE WHEN TG_OP = 'UPDATE' THEN OLD.config_id END)) THEN
    RAISE EXCEPTION 'ERP configuration is not a draft' USING ERRCODE = 'check_violation';
  END IF;
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql
""",
)

EFFECTIVE_CONTENT_DDL = (
    """
CREATE OR REPLACE FUNCTION catalog_effective_models(p_snapshot uuid) RETURNS SETOF schema_models AS $$
  SELECT o.* FROM schema_models o WHERE o.snapshot_id = p_snapshot AND o.overlay_op IS DISTINCT FROM 'remove'
  UNION ALL
  SELECT b.* FROM catalog_snapshots s JOIN schema_models b ON b.snapshot_id = s.parent_snapshot_id
  WHERE s.id = p_snapshot AND s.kind = 'account'
    AND NOT EXISTS (SELECT 1 FROM schema_models x WHERE x.snapshot_id = p_snapshot AND x.logical_id = b.logical_id)
$$ LANGUAGE sql STABLE
""",
    """
CREATE OR REPLACE FUNCTION catalog_effective_fields(p_snapshot uuid) RETURNS SETOF schema_fields AS $$
  SELECT o.* FROM schema_fields o WHERE o.snapshot_id = p_snapshot AND o.overlay_op IS DISTINCT FROM 'remove'
  UNION ALL
  SELECT b.* FROM catalog_snapshots s JOIN schema_fields b ON b.snapshot_id = s.parent_snapshot_id
  WHERE s.id = p_snapshot AND s.kind = 'account'
    AND NOT EXISTS (SELECT 1 FROM schema_fields x WHERE x.snapshot_id = p_snapshot AND x.logical_id = b.logical_id)
$$ LANGUAGE sql STABLE
""",
)

TRIGGER_DDL = (
    'CREATE TRIGGER trg_catalog_erp_configs_guard BEFORE UPDATE OR DELETE ON catalog_erp_configs FOR EACH ROW EXECUTE FUNCTION erp_config_guard()',
    'CREATE TRIGGER trg_catalog_field_groups_guard BEFORE INSERT OR UPDATE OR DELETE ON catalog_field_groups FOR EACH ROW EXECUTE FUNCTION erp_config_child_guard()',
    'CREATE TRIGGER trg_catalog_scope_routes_guard BEFORE INSERT OR UPDATE OR DELETE ON catalog_scope_routes FOR EACH ROW EXECUTE FUNCTION erp_config_child_guard()',
    'CREATE TRIGGER trg_catalog_snapshots_guard BEFORE UPDATE ON catalog_snapshots FOR EACH ROW EXECUTE FUNCTION catalog_snapshot_guard()',
    'CREATE TRIGGER trg_schema_models_guard BEFORE INSERT OR UPDATE ON schema_models FOR EACH ROW EXECUTE FUNCTION catalog_content_guard()',
    'CREATE TRIGGER trg_schema_fields_guard BEFORE INSERT OR UPDATE ON schema_fields FOR EACH ROW EXECUTE FUNCTION catalog_content_guard()',
    'CREATE TRIGGER trg_account_discoveries_guard BEFORE UPDATE ON account_discoveries FOR EACH ROW EXECUTE FUNCTION catalog_forbid_update()',
    'CREATE TRIGGER trg_catalog_scope_configurations_guard BEFORE UPDATE ON catalog_scope_configurations FOR EACH ROW EXECUTE FUNCTION catalog_forbid_update()',
    'CREATE TRIGGER trg_catalog_scope_configurations_tenant BEFORE INSERT ON catalog_scope_configurations FOR EACH ROW EXECUTE FUNCTION scope_configuration_tenant_guard()',
    'CREATE TRIGGER trg_conversion_scope_models_guard BEFORE UPDATE ON conversion_scope_models FOR EACH ROW EXECUTE FUNCTION catalog_forbid_update()',
    'CREATE TRIGGER trg_migration_plan_bindings_guard BEFORE UPDATE ON migration_plan_bindings FOR EACH ROW EXECUTE FUNCTION plan_binding_guard()',
    'CREATE TRIGGER trg_migration_plan_bindings_tenant BEFORE INSERT ON migration_plan_bindings FOR EACH ROW EXECUTE FUNCTION plan_binding_tenant_guard()',
)

TRIGGERS = (
    ('catalog_erp_configs', 'trg_catalog_erp_configs_guard'),
    ('catalog_field_groups', 'trg_catalog_field_groups_guard'),
    ('catalog_scope_routes', 'trg_catalog_scope_routes_guard'),
    ('catalog_snapshots', 'trg_catalog_snapshots_guard'),
    ('schema_models', 'trg_schema_models_guard'),
    ('schema_fields', 'trg_schema_fields_guard'),
    ('account_discoveries', 'trg_account_discoveries_guard'),
    ('catalog_scope_configurations', 'trg_catalog_scope_configurations_guard'),
    ('catalog_scope_configurations', 'trg_catalog_scope_configurations_tenant'),
    ('conversion_scope_models', 'trg_conversion_scope_models_guard'),
    ('migration_plan_bindings', 'trg_migration_plan_bindings_guard'),
    ('migration_plan_bindings', 'trg_migration_plan_bindings_tenant'),
)

FUNCTIONS = ('catalog_snapshot_guard', 'catalog_content_guard', 'catalog_forbid_update', 'plan_binding_guard', 'plan_binding_tenant_guard', 'scope_configuration_tenant_guard', 'erp_config_guard', 'erp_config_child_guard')


def upgrade() -> None:
    op.create_table('catalog_erp_configs',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('erp', sa.String(length=20), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'draft'"), nullable=False),
    sa.Column('authority_interface', sa.String(length=50), nullable=False),
    sa.Column('discovery_interface', sa.String(length=50), nullable=True),
    sa.Column('custom_prefixes', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('discovery_type_families', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("erp ~ '^[a-z][a-z0-9_]*$'", name='ck_catalog_erp_configs_erp'),
    sa.CheckConstraint("status IN ('draft','active','retired')", name='ck_catalog_erp_configs_status'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('erp', 'version', name='uix_catalog_erp_configs_version')
    )
    op.create_index('uix_catalog_erp_configs_active', 'catalog_erp_configs', ['erp'], unique=True, postgresql_where=sa.text("status = 'active'"))
    op.create_table('outbox_events',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('subject', sa.String(length=255), nullable=False),
    sa.Column('aggregate_type', sa.String(length=100), nullable=False),
    sa.Column('aggregate_id', sa.UUID(), nullable=False),
    sa.Column('dedup_key', sa.String(length=255), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
    sa.Column('attempts', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('available_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('pending','published','dead')", name='ck_outbox_events_status'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('dedup_key')
    )
    op.create_index('ix_outbox_events_aggregate', 'outbox_events', ['aggregate_type', 'aggregate_id'], unique=False)
    op.create_index('ix_outbox_events_pending', 'outbox_events', ['available_at'], unique=False, postgresql_where=sa.text("status = 'pending'"))
    op.create_table('account_discoveries',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('connection_id', sa.UUID(), nullable=False),
    sa.Column('connection_version', sa.Integer(), nullable=False),
    sa.Column('erp', sa.String(length=20), nullable=False),
    sa.Column('account_scope', sa.String(length=255), nullable=False),
    sa.Column('discovery_version', sa.Integer(), nullable=False),
    sa.Column('source_kind', sa.String(length=20), nullable=False),
    sa.Column('erp_version_reported', sa.String(length=100), nullable=True),
    sa.Column('connection_context', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('interfaces', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('requested_models', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('completeness', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('evidence_sha256', sa.String(length=64), nullable=False),
    sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("erp ~ '^[a-z][a-z0-9_]*$'", name='ck_account_discoveries_erp'),
    sa.CheckConstraint("source_kind IN ('live','fixture')", name='ck_account_discoveries_source_kind'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('connection_id', 'discovery_version', name='uix_account_discoveries_version'),
    sa.UniqueConstraint('org_id', 'connection_id', 'evidence_sha256', name='uix_account_discoveries_evidence')
    )
    op.create_table('catalog_field_groups',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('config_id', sa.UUID(), nullable=False),
    sa.Column('group_key', sa.String(length=100), nullable=False),
    sa.Column('modules', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('names', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('relations', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['config_id'], ['catalog_erp_configs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('config_id', 'group_key', name='uix_catalog_field_groups_key')
    )
    op.create_table('catalog_scope_routes',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('config_id', sa.UUID(), nullable=False),
    sa.Column('scope', sa.String(length=100), nullable=False),
    sa.Column('model', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('route_key', sa.String(length=100), server_default=sa.text("'default'"), nullable=False),
    sa.Column('subtype_routing', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('filters', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('child_paths', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('exclude_field_groups', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('optional_field_groups', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('account_specific', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.CheckConstraint("role IN ('primary','child','reference')", name='ck_catalog_scope_routes_role'),
    sa.CheckConstraint("scope IN ('items','customers','vendors','locations','contacts','vehicles','equipment','fixed_assets')", name='ck_catalog_scope_routes_scope'),
    sa.ForeignKeyConstraint(['config_id'], ['catalog_erp_configs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('config_id', 'scope', 'model', 'route_key', name='uix_catalog_scope_routes')
    )
    op.create_table('catalog_snapshots',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=True),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('scope_level', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'staging'"), nullable=False),
    sa.Column('erp', sa.String(length=20), nullable=False),
    sa.Column('erp_version', sa.String(length=50), nullable=False),
    sa.Column('erp_edition', sa.String(length=50), nullable=True),
    sa.Column('account_scope', sa.String(length=255), nullable=True),
    sa.Column('connection_id', sa.UUID(), nullable=True),
    sa.Column('catalog_contract_version', sa.String(length=20), nullable=False),
    sa.Column('projection_version', sa.String(length=20), nullable=False),
    sa.Column('graph_contract_version', sa.String(length=20), nullable=True),
    sa.Column('graph_snapshot_id', sa.String(length=255), nullable=True),
    sa.Column('parent_snapshot_id', sa.UUID(), nullable=True),
    sa.Column('previous_snapshot_id', sa.UUID(), nullable=True),
    sa.Column('discovery_id', sa.UUID(), nullable=True),
    sa.Column('overlay_policy_version', sa.String(length=20), nullable=True),
    sa.Column('lineage_key', sa.String(length=500), nullable=False),
    sa.Column('identity_sha256', sa.String(length=64), nullable=False),
    sa.Column('content_sha256', sa.String(length=64), nullable=True),
    sa.Column('manifest', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('completeness', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('diagnostics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('change_report', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('counts', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('attempts', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('error_detail', sa.Text(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('validated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("(kind = 'baseline' AND org_id IS NULL) OR (kind = 'account' AND org_id IS NOT NULL)", name='ck_catalog_snapshots_owner'),
    sa.CheckConstraint("(scope_level = 'global' AND account_scope IS NULL) OR (scope_level = 'account' AND account_scope IS NOT NULL AND connection_id IS NOT NULL)", name='ck_catalog_snapshots_account_scope'),
    sa.CheckConstraint("erp ~ '^[a-z][a-z0-9_]*$'", name='ck_catalog_snapshots_erp'),
    sa.CheckConstraint("kind = 'account' OR graph_snapshot_id IS NOT NULL", name='ck_catalog_snapshots_baseline_inputs'),
    sa.CheckConstraint("kind = 'baseline' OR (scope_level = 'account' AND parent_snapshot_id IS NOT NULL AND discovery_id IS NOT NULL AND overlay_policy_version IS NOT NULL)", name='ck_catalog_snapshots_account_inputs'),
    sa.CheckConstraint("kind IN ('baseline','account')", name='ck_catalog_snapshots_kind'),
    sa.CheckConstraint("scope_level IN ('global','account')", name='ck_catalog_snapshots_scope_level'),
    sa.CheckConstraint("status IN ('staging','validated','published','failed')", name='ck_catalog_snapshots_status'),
    sa.CheckConstraint("status NOT IN ('validated','published') OR content_sha256 IS NOT NULL", name='ck_catalog_snapshots_content_hash'),
    sa.ForeignKeyConstraint(['discovery_id'], ['account_discoveries.id'], ),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['parent_snapshot_id'], ['catalog_snapshots.id'], ),
    sa.ForeignKeyConstraint(['previous_snapshot_id'], ['catalog_snapshots.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_catalog_snapshots_org_lineage', 'catalog_snapshots', ['org_id', 'lineage_key', 'published_at'], unique=False)
    op.create_index('ix_catalog_snapshots_org_status', 'catalog_snapshots', ['org_id', 'status'], unique=False)
    op.create_index('uix_catalog_snapshots_identity_live', 'catalog_snapshots', ['identity_sha256'], unique=True, postgresql_where=sa.text("status <> 'failed'"))
    op.create_table('catalog_scope_configurations',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=True),
    sa.Column('snapshot_id', sa.UUID(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('erp_config_id', sa.UUID(), nullable=False),
    sa.Column('review_status', sa.String(length=20), nullable=False),
    sa.Column('content_sha256', sa.String(length=64), nullable=False),
    sa.Column('unresolved', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('provenance', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("review_status IN ('draft','reviewed','retired')", name='ck_catalog_scope_configurations_review'),
    sa.ForeignKeyConstraint(['erp_config_id'], ['catalog_erp_configs.id'], ),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['snapshot_id'], ['catalog_snapshots.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'snapshot_id', name='uix_catalog_scope_configurations_id_snapshot'),
    sa.UniqueConstraint('snapshot_id', 'content_sha256', name='uix_catalog_scope_configurations_content'),
    sa.UniqueConstraint('snapshot_id', 'revision', name='uix_catalog_scope_configurations_revision')
    )
    op.create_table('schema_models',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('snapshot_id', sa.UUID(), nullable=False),
    sa.Column('logical_id', sa.String(length=512), nullable=False),
    sa.Column('native_model', sa.String(length=255), nullable=False),
    sa.Column('label', sa.String(length=500), nullable=True),
    sa.Column('model_kind', sa.String(length=50), nullable=True),
    sa.Column('evidence_status', sa.String(length=20), nullable=False),
    sa.Column('is_custom', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('definition', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('bindings', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('constraints', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('relations', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('provenance', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('conflicts', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('content_sha256', sa.String(length=64), nullable=False),
    sa.Column('overlay_op', sa.String(length=10), nullable=True),
    sa.CheckConstraint("evidence_status IN ('verified','inferred','conflicting','reviewed','proposed','rejected','unknown')", name='ck_schema_models_evidence'),
    sa.CheckConstraint("overlay_op IS NULL OR overlay_op IN ('add','replace','remove')", name='ck_schema_models_overlay_op'),
    sa.ForeignKeyConstraint(['snapshot_id'], ['catalog_snapshots.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('snapshot_id', 'logical_id', name='uix_schema_models_snapshot_logical')
    )
    op.create_table('conversion_scope_models',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('configuration_id', sa.UUID(), nullable=False),
    sa.Column('snapshot_id', sa.UUID(), nullable=False),
    sa.Column('model_logical_id', sa.String(length=512), nullable=False),
    sa.Column('scope', sa.String(length=100), nullable=False),
    sa.Column('route_key', sa.String(length=100), server_default=sa.text("'default'"), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('subtype_routing', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('filters', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('child_paths', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('field_rules', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('review_status', sa.String(length=20), nullable=False),
    sa.Column('provenance', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.CheckConstraint("review_status IN ('proposed','reviewed','rejected')", name='ck_conversion_scope_models_review'),
    sa.CheckConstraint("role IN ('primary','child','reference')", name='ck_conversion_scope_models_role'),
    sa.CheckConstraint("scope IN ('items','customers','vendors','locations','contacts','vehicles','equipment','fixed_assets')", name='ck_conversion_scope_models_scope'),
    sa.ForeignKeyConstraint(['configuration_id', 'snapshot_id'], ['catalog_scope_configurations.id', 'catalog_scope_configurations.snapshot_id'], name='fk_conversion_scope_models_configuration', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('configuration_id', 'scope', 'model_logical_id', 'route_key', name='uix_conversion_scope_models')
    )
    op.create_index('ix_conversion_scope_models_config_scope', 'conversion_scope_models', ['configuration_id', 'scope'], unique=False)
    op.create_index('ix_conversion_scope_models_snapshot_model', 'conversion_scope_models', ['snapshot_id', 'model_logical_id'], unique=False)
    op.create_table('migration_plan_bindings',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('org_id', sa.UUID(), nullable=False),
    sa.Column('workstream_id', sa.UUID(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'active'"), nullable=False),
    sa.Column('scope', sa.String(length=100), nullable=False),
    sa.Column('source_snapshot_id', sa.UUID(), nullable=True),
    sa.Column('source_snapshot_sha256', sa.String(length=64), nullable=True),
    sa.Column('source_connection_id', sa.UUID(), nullable=True),
    sa.Column('source_connection_context', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('source_interface', sa.String(length=50), nullable=True),
    sa.Column('target_snapshot_id', sa.UUID(), nullable=False),
    sa.Column('target_snapshot_sha256', sa.String(length=64), nullable=False),
    sa.Column('target_connection_id', sa.UUID(), nullable=True),
    sa.Column('target_connection_context', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('target_interface', sa.String(length=50), nullable=False),
    sa.Column('target_operation', sa.String(length=20), nullable=False),
    sa.Column('source_scope_configuration_id', sa.UUID(), nullable=True),
    sa.Column('target_scope_configuration_id', sa.UUID(), nullable=False),
    sa.Column('selected_routes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('field_groups', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('eligibility', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('rebased_from_id', sa.UUID(), nullable=True),
    sa.Column('change_report', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('revalidation', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("scope IN ('items','customers','vendors','locations','contacts','vehicles','equipment','fixed_assets')", name='ck_migration_plan_bindings_scope'),
    sa.CheckConstraint("(source_snapshot_id IS NULL) = (source_snapshot_sha256 IS NULL) AND (source_snapshot_id IS NULL) = (source_interface IS NULL) AND (source_snapshot_id IS NULL) = (source_scope_configuration_id IS NULL)", name='ck_migration_plan_bindings_source_side'),
    sa.CheckConstraint("status IN ('active','superseded')", name='ck_migration_plan_bindings_status'),
    sa.CheckConstraint("target_operation IN ('create','update')", name='ck_migration_plan_bindings_operation'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['rebased_from_id'], ['migration_plan_bindings.id'], ),
    sa.ForeignKeyConstraint(['source_scope_configuration_id', 'source_snapshot_id'], ['catalog_scope_configurations.id', 'catalog_scope_configurations.snapshot_id'], name='fk_migration_plan_bindings_source_configuration'),
    sa.ForeignKeyConstraint(['source_snapshot_id'], ['catalog_snapshots.id'], name='fk_migration_plan_bindings_source_snapshot'),
    sa.ForeignKeyConstraint(['target_scope_configuration_id', 'target_snapshot_id'], ['catalog_scope_configurations.id', 'catalog_scope_configurations.snapshot_id'], name='fk_migration_plan_bindings_target_configuration'),
    sa.ForeignKeyConstraint(['target_snapshot_id'], ['catalog_snapshots.id'], name='fk_migration_plan_bindings_target_snapshot'),
    sa.ForeignKeyConstraint(['workstream_id'], ['workstreams.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('workstream_id', 'revision', name='uix_migration_plan_bindings_revision')
    )
    op.create_index('uix_migration_plan_bindings_active', 'migration_plan_bindings', ['workstream_id'], unique=True, postgresql_where=sa.text("status = 'active'"))
    op.create_table('schema_fields',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('snapshot_id', sa.UUID(), nullable=False),
    sa.Column('model_logical_id', sa.String(length=512), nullable=False),
    sa.Column('logical_id', sa.String(length=768), nullable=False),
    sa.Column('pipeline_ids', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('owner_logical_id', sa.String(length=768), nullable=False),
    sa.Column('native_path', sa.String(length=500), nullable=False),
    sa.Column('qualified_path', sa.String(length=768), nullable=False),
    sa.Column('label', sa.String(length=500), nullable=True),
    sa.Column('native_type', sa.String(length=100), nullable=True),
    sa.Column('type_family', sa.String(length=20), server_default=sa.text("'unknown'"), nullable=False),
    sa.Column('cardinality', sa.String(length=20), nullable=True),
    sa.Column('required', sa.Boolean(), nullable=True),
    sa.Column('readonly', sa.Boolean(), nullable=True),
    sa.Column('stored', sa.Boolean(), nullable=True),
    sa.Column('conditional_requirements', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True),
    sa.Column('relation', sa.String(length=255), nullable=True),
    sa.Column('enum_values', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True),
    sa.Column('evidence_status', sa.String(length=20), nullable=False),
    sa.Column('is_custom', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('definition', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('bindings', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('relations', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('provenance', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('conflicts', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('content_sha256', sa.String(length=64), nullable=False),
    sa.Column('overlay_op', sa.String(length=10), nullable=True),
    sa.CheckConstraint("cardinality IS NULL OR cardinality IN ('many_to_one','one_to_many','many_to_many','one_to_one')", name='ck_schema_fields_cardinality'),
    sa.CheckConstraint("evidence_status IN ('verified','inferred','conflicting','reviewed','proposed','rejected','unknown')", name='ck_schema_fields_evidence'),
    sa.CheckConstraint("kind IN ('field','sublist','search_join')", name='ck_schema_fields_kind'),
    sa.CheckConstraint("overlay_op IS NULL OR overlay_op IN ('add','replace','remove')", name='ck_schema_fields_overlay_op'),
    sa.CheckConstraint("type_family IN ('text','boolean','number','datetime','enum','reference','binary','complex','unknown')", name='ck_schema_fields_type_family'),
    sa.ForeignKeyConstraint(['snapshot_id', 'model_logical_id'], ['schema_models.snapshot_id', 'schema_models.logical_id'], name='fk_schema_fields_model', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['snapshot_id'], ['catalog_snapshots.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('snapshot_id', 'logical_id', name='uix_schema_fields_snapshot_logical')
    )
    op.create_index('ix_schema_fields_snapshot_model', 'schema_fields', ['snapshot_id', 'model_logical_id'], unique=False)
    for stmt in FUNCTION_DDL + EFFECTIVE_CONTENT_DDL + TRIGGER_DDL:
        op.execute(stmt)


def downgrade() -> None:
    for table, trigger in TRIGGERS:
        op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
    op.execute("DROP FUNCTION IF EXISTS catalog_effective_models(uuid)")
    op.execute("DROP FUNCTION IF EXISTS catalog_effective_fields(uuid)")
    for fn in FUNCTIONS:
        op.execute(f"DROP FUNCTION IF EXISTS {fn}()")
    op.drop_index('ix_schema_fields_snapshot_model', table_name='schema_fields')
    op.drop_table('schema_fields')
    op.drop_index('uix_migration_plan_bindings_active', table_name='migration_plan_bindings', postgresql_where=sa.text("status = 'active'"))
    op.drop_table('migration_plan_bindings')
    op.drop_index('ix_conversion_scope_models_snapshot_model', table_name='conversion_scope_models')
    op.drop_index('ix_conversion_scope_models_config_scope', table_name='conversion_scope_models')
    op.drop_table('conversion_scope_models')
    op.drop_table('schema_models')
    op.drop_table('catalog_scope_configurations')
    op.drop_index('uix_catalog_snapshots_identity_live', table_name='catalog_snapshots', postgresql_where=sa.text("status <> 'failed'"))
    op.drop_index('ix_catalog_snapshots_org_status', table_name='catalog_snapshots')
    op.drop_index('ix_catalog_snapshots_org_lineage', table_name='catalog_snapshots')
    op.drop_table('catalog_snapshots')
    op.drop_table('catalog_scope_routes')
    op.drop_table('catalog_field_groups')
    op.drop_table('account_discoveries')
    op.drop_index('ix_outbox_events_pending', table_name='outbox_events', postgresql_where=sa.text("status = 'pending'"))
    op.drop_index('ix_outbox_events_aggregate', table_name='outbox_events')
    op.drop_table('outbox_events')
    op.drop_index('uix_catalog_erp_configs_active', table_name='catalog_erp_configs', postgresql_where=sa.text("status = 'active'"))
    op.drop_table('catalog_erp_configs')
