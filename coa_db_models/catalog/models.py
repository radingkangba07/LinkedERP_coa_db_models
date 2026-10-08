"""Versioned application catalogue: per-ERP configuration, baseline and account
snapshots, account discovery evidence, the scope registry and migration-plan bindings.

PostgreSQL is the authoritative catalogue. Graph snapshots produced by the
erp-schema-graph package are loaded into schema_models / schema_fields and
referenced by (catalog snapshot id, logical id).

Baseline snapshots (standard ERP content) are shared by every organisation
(org_id NULL). Account snapshots belong to one organisation and store only the
rows that differ from their baseline (overlay_op); catalog_effective_models()
and catalog_effective_fields() return the full content of any snapshot.

Published snapshots, active ERP configurations, discovery evidence and
plan-binding revisions are immutable; the triggers in IMMUTABILITY_DDL enforce
that, and tenant isolation, in the database, not only in application code.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DDL,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from coa_db_models.base import Base
from coa_db_models.pipeline.models import _VALID_SCOPES

# ERP ids are not enumerated here: the set of ERPs is the rows of catalog_erp_configs.
# The database only enforces the id format.
_ERP_ID_CHECK = "erp ~ '^[a-z][a-z0-9_]*$'"
_EVIDENCE = "'verified','inferred','conflicting','reviewed','proposed','rejected','unknown'"
# Account snapshots: how a row changes the baseline. NULL on baseline rows.
_OVERLAY_OP_CHECK = "overlay_op IS NULL OR overlay_op IN ('add','replace','remove')"


class CatalogErpConfig(Base):
    """One version of an ERP's catalogue configuration: ERP-level settings plus
    its field groups and scope routes (child tables). Shared by all organisations.

    A draft version is editable; activating it retires the previous active
    version of the same ERP. Active and retired versions are immutable (only
    active -> retired is allowed), so scope configurations built from a
    version never change underneath a saved plan.
    """

    __tablename__ = "catalog_erp_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    erp: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'draft'"))
    # Interface whose account evidence may replace node-level operational facts.
    authority_interface: Mapped[str] = mapped_column(String(50), nullable=False)
    # Interface the live discovery adapter observes; NULL = no live discovery.
    discovery_interface: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # {"model": ["x_"], "field": ["x_"]}: name prefixes that mark account-specific models / fields.
    custom_prefixes: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    # Native type -> normalised type family, for fields added from account discovery.
    discovery_type_families: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(_ERP_ID_CHECK, name="ck_catalog_erp_configs_erp"),
        CheckConstraint("status IN ('draft','active','retired')", name="ck_catalog_erp_configs_status"),
        UniqueConstraint("erp", "version", name="uix_catalog_erp_configs_version"),
        Index("uix_catalog_erp_configs_active", "erp", unique=True, postgresql_where=text("status = 'active'")),
    )


class CatalogFieldGroup(Base):
    """A named group of fields that a scope route can exclude, or switch on per project.
    A field belongs to the group when its module, its name, or the model it references
    matches one of the glob patterns."""

    __tablename__ = "catalog_field_groups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalog_erp_configs.id", ondelete="CASCADE"), nullable=False
    )
    group_key: Mapped[str] = mapped_column(String(100), nullable=False)
    modules: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    names: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    relations: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("config_id", "group_key", name="uix_catalog_field_groups_key"),)


class CatalogScopeRoute(Base):
    """One model of one business scope in an ERP configuration version, e.g.
    items -> product.template (primary). Resolved against each snapshot into
    conversion_scope_models."""

    __tablename__ = "catalog_scope_routes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalog_erp_configs.id", ondelete="CASCADE"), nullable=False
    )
    scope: Mapped[str] = mapped_column(String(100), nullable=False)
    # Native model name, e.g. "product.template".
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    route_key: Mapped[str] = mapped_column(String(100), nullable=False, server_default=text("'default'"))
    # Discriminator for the route, e.g. {"discriminator": "is_company", "value": true}.
    subtype_routing: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    # Record filter in the ERP's own syntax, e.g. an Odoo domain.
    filters: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    child_paths: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    # Group keys of this configuration: always excluded / excluded unless the project switches them on.
    exclude_field_groups: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    optional_field_groups: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    # Model exists only in some accounts (e.g. an Enterprise module); absent from baselines.
    account_specific: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(f"scope IN ({_VALID_SCOPES})", name="ck_catalog_scope_routes_scope"),
        CheckConstraint("role IN ('primary','child','reference')", name="ck_catalog_scope_routes_role"),
        UniqueConstraint("config_id", "scope", "model", "route_key", name="uix_catalog_scope_routes"),
    )


class CatalogSnapshot(Base):
    """One catalogue version. kind='baseline' is loaded from a graph snapshot
    and shared by every organisation (org_id NULL). kind='account' overlays a
    published baseline with versioned account-discovery evidence under a
    versioned policy; it belongs to one organisation and stores only the rows
    that differ from the baseline.

    scope_level describes the content: 'global' (not tied to a customer
    account) or 'account'.
    """

    __tablename__ = "catalog_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    # NULL for shared baselines; the owning organisation for account snapshots.
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    scope_level: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'staging'"))
    erp: Mapped[str] = mapped_column(String(20), nullable=False)
    erp_version: Mapped[str] = mapped_column(String(50), nullable=False)
    erp_edition: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # External account identifier (NetSuite account id, Odoo database); NULL for global content.
    account_scope: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Soft reference: connection rows may be deleted, snapshots must survive.
    connection_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    catalog_contract_version: Mapped[str] = mapped_column(String(20), nullable=False)
    # Version of the graph -> catalogue projection code (separate from the row-format contract).
    projection_version: Mapped[str] = mapped_column(String(20), nullable=False)
    graph_contract_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Pipeline input / graph snapshot version (content-addressed graph snapshot id).
    graph_snapshot_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parent_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalog_snapshots.id"), nullable=True
    )
    previous_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalog_snapshots.id"), nullable=True
    )
    discovery_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("account_discoveries.id"), nullable=True
    )
    overlay_policy_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Snapshots with the same lineage_key succeed each other on refresh.
    lineage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    # Hash of the inputs; the idempotency key for repeated ingestion.
    identity_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # Hash of the materialised content; set when validated.
    content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    completeness: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    diagnostics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    change_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    counts: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("kind IN ('baseline','account')", name="ck_catalog_snapshots_kind"),
        CheckConstraint(
            "(kind = 'baseline' AND org_id IS NULL) OR (kind = 'account' AND org_id IS NOT NULL)",
            name="ck_catalog_snapshots_owner",
        ),
        CheckConstraint("scope_level IN ('global','account')", name="ck_catalog_snapshots_scope_level"),
        CheckConstraint(
            "status IN ('staging','validated','published','failed')", name="ck_catalog_snapshots_status"
        ),
        CheckConstraint(_ERP_ID_CHECK, name="ck_catalog_snapshots_erp"),
        CheckConstraint(
            "(scope_level = 'global' AND account_scope IS NULL) OR "
            "(scope_level = 'account' AND account_scope IS NOT NULL AND connection_id IS NOT NULL)",
            name="ck_catalog_snapshots_account_scope",
        ),
        CheckConstraint(
            "kind = 'baseline' OR (scope_level = 'account' AND parent_snapshot_id IS NOT NULL "
            "AND discovery_id IS NOT NULL AND overlay_policy_version IS NOT NULL)",
            name="ck_catalog_snapshots_account_inputs",
        ),
        CheckConstraint(
            "kind = 'account' OR graph_snapshot_id IS NOT NULL", name="ck_catalog_snapshots_baseline_inputs"
        ),
        CheckConstraint(
            "status NOT IN ('validated','published') OR content_sha256 IS NOT NULL",
            name="ck_catalog_snapshots_content_hash",
        ),
        # One live (non-failed) attempt per identity: concurrent or repeated
        # ingestion of the same inputs converges on one row.
        Index(
            "uix_catalog_snapshots_identity_live",
            "identity_sha256",
            unique=True,
            postgresql_where=text("status <> 'failed'"),
        ),
        Index("ix_catalog_snapshots_org_lineage", "org_id", "lineage_key", "published_at"),
        Index("ix_catalog_snapshots_org_status", "org_id", "status"),
    )


class SchemaModel(Base):
    __tablename__ = "schema_models"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalog_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    logical_id: Mapped[str] = mapped_column(String(512), nullable=False)
    native_model: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[str | None] = mapped_column(String(500), nullable=True)
    model_kind: Mapped[str | None] = mapped_column(String(50), nullable=True)
    evidence_status: Mapped[str] = mapped_column(String(20), nullable=False)
    is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    # Graph node without bindings; bindings are kept separately for capability queries.
    definition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    bindings: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    # {"availability": present|explicit_empty|missing|incomplete, "items": [...]}
    constraints: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    # Outgoing model-level edges (HAS_FIELD, INHERITS_FROM, DELEGATES_TO).
    relations: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    provenance: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    conflicts: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # Account snapshots only: add (new model), replace (changed or carrying changed fields), remove.
    overlay_op: Mapped[str | None] = mapped_column(String(10), nullable=True)

    __table_args__ = (
        CheckConstraint(f"evidence_status IN ({_EVIDENCE})", name="ck_schema_models_evidence"),
        CheckConstraint(_OVERLAY_OP_CHECK, name="ck_schema_models_overlay_op"),
        UniqueConstraint("snapshot_id", "logical_id", name="uix_schema_models_snapshot_logical"),
    )


class SchemaField(Base):
    """A field, NetSuite sublist or search join. Tri-state columns keep NULL
    as unknown; they are never coerced to false."""

    __tablename__ = "schema_fields"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalog_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    # Owning schema_models row: composite FK (snapshot_id, model_logical_id), so the model is in the same snapshot.
    model_logical_id: Mapped[str] = mapped_column(String(512), nullable=False)
    logical_id: Mapped[str] = mapped_column(String(768), nullable=False)
    # Original pipeline identifiers, e.g. {"field_id": "odoo:18.0:community:res.partner:vat"}.
    pipeline_ids: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    owner_logical_id: Mapped[str] = mapped_column(String(768), nullable=False)
    native_path: Mapped[str] = mapped_column(String(500), nullable=False)
    qualified_path: Mapped[str] = mapped_column(String(768), nullable=False)
    label: Mapped[str | None] = mapped_column(String(500), nullable=True)
    native_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    type_family: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'unknown'"))
    # many_to_one / one_to_many / many_to_many / one_to_one; NULL for scalars or unknown.
    cardinality: Mapped[str | None] = mapped_column(String(20), nullable=True)
    required: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    readonly: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    stored: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # NULL = not observed (unknown); [] = observed to have none.
    conditional_requirements: Mapped[list | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    # Referenced native model, and enumeration values ([[value, label], ...]); NULL = none/unknown.
    relation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enum_values: Mapped[list | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    evidence_status: Mapped[str] = mapped_column(String(20), nullable=False)
    is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    definition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    bindings: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    # Per interface: native name, evidence and read/create/update {state, basis, conditions}.
    # Capability evidence is never reduced to the readonly column.
    # Outgoing edges (REFERENCES, COLLECTION_OF, INVERSE_OF, SEARCH_JOIN, RELATED_FIELD, FIELD_INHERITED_FROM).
    relations: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    # Per-attribute source: {"readonly": {"source": "discovery", "evidence": ...}, ...}
    provenance: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    conflicts: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    # Hash of definition + bindings + relations; embedding indexes rebuild when it changes.
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # Account snapshots only: add (new field), replace (changed), remove (absent from the account).
    overlay_op: Mapped[str | None] = mapped_column(String(10), nullable=True)

    __table_args__ = (
        CheckConstraint("kind IN ('field','sublist','search_join')", name="ck_schema_fields_kind"),
        CheckConstraint(_OVERLAY_OP_CHECK, name="ck_schema_fields_overlay_op"),
        CheckConstraint(f"evidence_status IN ({_EVIDENCE})", name="ck_schema_fields_evidence"),
        CheckConstraint(
            "type_family IN ('text','boolean','number','datetime','enum','reference','binary','complex','unknown')",
            name="ck_schema_fields_type_family",
        ),
        CheckConstraint(
            "cardinality IS NULL OR cardinality IN ('many_to_one','one_to_many','many_to_many','one_to_one')",
            name="ck_schema_fields_cardinality",
        ),
        ForeignKeyConstraint(
            ["snapshot_id", "model_logical_id"],
            ["schema_models.snapshot_id", "schema_models.logical_id"],
            ondelete="CASCADE",
            name="fk_schema_fields_model",
        ),
        UniqueConstraint("snapshot_id", "logical_id", name="uix_schema_fields_snapshot_logical"),
        Index("ix_schema_fields_snapshot_model", "snapshot_id", "model_logical_id"),
    )


class AccountDiscovery(Base):
    """Immutable, versioned metadata evidence observed from one connection.
    Never holds credentials. source_kind='fixture' marks evidence that did
    not come from a live account."""

    __tablename__ = "account_discoveries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    connection_version: Mapped[int] = mapped_column(Integer, nullable=False)
    erp: Mapped[str] = mapped_column(String(20), nullable=False)
    account_scope: Mapped[str] = mapped_column(String(255), nullable=False)
    discovery_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    erp_version_reported: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Public connection facts plus the role/permission context the evidence was observed under.
    connection_context: Mapped[dict] = mapped_column(JSONB, nullable=False)
    interfaces: Mapped[list] = mapped_column(JSONB, nullable=False)
    requested_models: Mapped[list] = mapped_column(JSONB, nullable=False)
    # Per model: {"state": "complete"|"partial"|"failed"|"not_found", "reason": ...}
    completeness: Mapped[dict] = mapped_column(JSONB, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(_ERP_ID_CHECK, name="ck_account_discoveries_erp"),
        CheckConstraint("source_kind IN ('live','fixture')", name="ck_account_discoveries_source_kind"),
        UniqueConstraint("connection_id", "discovery_version", name="uix_account_discoveries_version"),
        UniqueConstraint("org_id", "connection_id", "evidence_sha256", name="uix_account_discoveries_evidence"),
    )


class CatalogScopeConfiguration(Base):
    """One immutable revision of the scope configuration for one catalogue snapshot.

    Built from one ERP configuration version (erp_config_id) against the models
    that actually exist in the snapshot. Routes whose model the snapshot does
    not contain (for example undiscovered account-specific records) are listed
    in `unresolved`. Any change creates a new revision; plans pin a revision.
    Shared (org_id NULL) for baseline snapshots, owned for account snapshots.
    """

    __tablename__ = "catalog_scope_configurations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    # Same owner as the snapshot (NULL for a shared baseline); enforced by trigger.
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalog_snapshots.id"), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    erp_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalog_erp_configs.id"), nullable=False
    )
    review_status: Mapped[str] = mapped_column(String(20), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # [{"scope", "model_logical_id", "role", "reason"}] for template rows with no model in the snapshot.
    unresolved: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    provenance: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "review_status IN ('draft','reviewed','retired')", name="ck_catalog_scope_configurations_review"
        ),
        UniqueConstraint("snapshot_id", "revision", name="uix_catalog_scope_configurations_revision"),
        UniqueConstraint("snapshot_id", "content_sha256", name="uix_catalog_scope_configurations_content"),
        UniqueConstraint("id", "snapshot_id", name="uix_catalog_scope_configurations_id_snapshot"),
    )


class ConversionScopeModel(Base):
    """Direction-neutral association of a business scope with one model of one
    catalogue snapshot. A scope may have several models (and several routes per
    model); a model may serve several scopes. The model is resolved against the
    snapshot's effective content (an account snapshot may inherit it from its
    baseline), so there is no row-level foreign key to schema_models."""

    __tablename__ = "conversion_scope_models"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    configuration_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    model_logical_id: Mapped[str] = mapped_column(String(512), nullable=False)
    scope: Mapped[str] = mapped_column(String(100), nullable=False)
    # Route / subtype identifier within the scope, e.g. "company", "individual", "inventoryitem".
    route_key: Mapped[str] = mapped_column(String(100), nullable=False, server_default=text("'default'"))
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    # Discriminator details for the route, e.g. {"discriminator": "is_company", "value": true}.
    subtype_routing: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    # Record filter in the ERP's own syntax, e.g. Odoo domain.
    filters: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    # Approved child paths from the primary model, e.g. ["bank_ids"] or ["addressbook"].
    child_paths: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    # Field groups excluded from mapping candidates for this route:
    # {"exclude": [{"group": "website", "modules": ["website*"], "names": ["website_*"]}]} (glob patterns).
    field_rules: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    review_status: Mapped[str] = mapped_column(String(20), nullable=False)
    provenance: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    __table_args__ = (
        CheckConstraint(f"scope IN ({_VALID_SCOPES})", name="ck_conversion_scope_models_scope"),
        CheckConstraint("role IN ('primary','child','reference')", name="ck_conversion_scope_models_role"),
        CheckConstraint(
            "review_status IN ('proposed','reviewed','rejected')", name="ck_conversion_scope_models_review"
        ),
        # The configuration row and the model row must both belong to snapshot_id.
        ForeignKeyConstraint(
            ["configuration_id", "snapshot_id"],
            ["catalog_scope_configurations.id", "catalog_scope_configurations.snapshot_id"],
            ondelete="CASCADE",
            name="fk_conversion_scope_models_configuration",
        ),
        UniqueConstraint(
            "configuration_id", "scope", "model_logical_id", "route_key", name="uix_conversion_scope_models"
        ),
        Index("ix_conversion_scope_models_config_scope", "configuration_id", "scope"),
        Index("ix_conversion_scope_models_snapshot_model", "snapshot_id", "model_logical_id"),
    )


class MigrationPlanBinding(Base):
    """One immutable revision of a mapping plan's catalogue binding. Only the
    status may change (active -> superseded) when an explicit rebase creates
    the next revision. The source side is optional: a source system with no
    catalogue (a spreadsheet, an unconfigured ERP) maps from file columns alone."""

    __tablename__ = "migration_plan_bindings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    workstream_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workstreams.id", ondelete="CASCADE"), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))
    scope: Mapped[str] = mapped_column(String(100), nullable=False)
    source_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_snapshot_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_connection_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_connection_context: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    source_interface: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_snapshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    target_connection_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    target_connection_context: Mapped[dict] = mapped_column(JSONB, nullable=False)
    target_interface: Mapped[str] = mapped_column(String(50), nullable=False)
    target_operation: Mapped[str] = mapped_column(String(20), nullable=False)
    # Pinned scope-configuration revisions, one per side (each belongs to that side's snapshot).
    source_scope_configuration_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    target_scope_configuration_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    selected_routes: Mapped[list] = mapped_column(JSONB, nullable=False)
    # Optional field groups switched on for this project (e.g. ["accounting", "pos"]); core is always included.
    field_groups: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    eligibility: Mapped[dict] = mapped_column(JSONB, nullable=False)
    rebased_from_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("migration_plan_bindings.id"), nullable=True
    )
    change_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    revalidation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('active','superseded')", name="ck_migration_plan_bindings_status"),
        CheckConstraint("target_operation IN ('create','update')", name="ck_migration_plan_bindings_operation"),
        CheckConstraint(f"scope IN ({_VALID_SCOPES})", name="ck_migration_plan_bindings_scope"),
        # The source side is all present or all absent.
        CheckConstraint(
            "(source_snapshot_id IS NULL) = (source_snapshot_sha256 IS NULL) AND "
            "(source_snapshot_id IS NULL) = (source_interface IS NULL) AND "
            "(source_snapshot_id IS NULL) = (source_scope_configuration_id IS NULL)",
            name="ck_migration_plan_bindings_source_side",
        ),
        # Referenced snapshots and configurations cannot be deleted while a saved plan uses them
        # (NO ACTION). They must be shared baselines or belong to the plan's organisation (trigger).
        ForeignKeyConstraint(["source_snapshot_id"], ["catalog_snapshots.id"],
                             name="fk_migration_plan_bindings_source_snapshot"),
        ForeignKeyConstraint(["target_snapshot_id"], ["catalog_snapshots.id"],
                             name="fk_migration_plan_bindings_target_snapshot"),
        ForeignKeyConstraint(
            ["source_scope_configuration_id", "source_snapshot_id"],
            ["catalog_scope_configurations.id", "catalog_scope_configurations.snapshot_id"],
            name="fk_migration_plan_bindings_source_configuration",
        ),
        ForeignKeyConstraint(
            ["target_scope_configuration_id", "target_snapshot_id"],
            ["catalog_scope_configurations.id", "catalog_scope_configurations.snapshot_id"],
            name="fk_migration_plan_bindings_target_configuration",
        ),
        UniqueConstraint("workstream_id", "revision", name="uix_migration_plan_bindings_revision"),
        Index(
            "uix_migration_plan_bindings_active",
            "workstream_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )


# ---------------------------------------------------------------------------
# Immutability, enforced by the database. Foreign keys between catalogue rows
# use the default NO ACTION so an organisation's cascade delete (checked at
# statement end) succeeds without updating published rows.
# ---------------------------------------------------------------------------

IMMUTABILITY_DDL = (
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
    # Tenant isolation: a binding may use shared baselines or its own organisation's snapshots.
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
    # A scope configuration has the same owner as its snapshot (NULL for a shared baseline).
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
    # ERP configurations: drafts are editable; active -> retired is the only later change.
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
    # Field groups and scope routes change only while their configuration is a draft.
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

# Full content of any snapshot: a baseline's own rows; for an account snapshot, its
# added/replaced rows plus the baseline rows it does not override or remove.
# Created after the tables (SQL function bodies are checked at creation).
EFFECTIVE_CONTENT_DDL = tuple(
    f"""
CREATE OR REPLACE FUNCTION catalog_effective_{name}(p_snapshot uuid) RETURNS SETOF {table} AS $$
  SELECT o.* FROM {table} o WHERE o.snapshot_id = p_snapshot AND o.overlay_op IS DISTINCT FROM 'remove'
  UNION ALL
  SELECT b.* FROM catalog_snapshots s JOIN {table} b ON b.snapshot_id = s.parent_snapshot_id
  WHERE s.id = p_snapshot AND s.kind = 'account'
    AND NOT EXISTS (SELECT 1 FROM {table} x WHERE x.snapshot_id = p_snapshot AND x.logical_id = b.logical_id)
$$ LANGUAGE sql STABLE
"""
    for name, table in (("models", "schema_models"), ("fields", "schema_fields"))
)

TRIGGER_DDL = {
    "catalog_erp_configs": ["CREATE TRIGGER trg_catalog_erp_configs_guard BEFORE UPDATE OR DELETE "
                            "ON catalog_erp_configs FOR EACH ROW EXECUTE FUNCTION erp_config_guard()"],
    "catalog_field_groups": ["CREATE TRIGGER trg_catalog_field_groups_guard BEFORE INSERT OR UPDATE OR DELETE "
                             "ON catalog_field_groups FOR EACH ROW EXECUTE FUNCTION erp_config_child_guard()"],
    "catalog_scope_routes": ["CREATE TRIGGER trg_catalog_scope_routes_guard BEFORE INSERT OR UPDATE OR DELETE "
                             "ON catalog_scope_routes FOR EACH ROW EXECUTE FUNCTION erp_config_child_guard()"],
    "catalog_snapshots": ["CREATE TRIGGER trg_catalog_snapshots_guard BEFORE UPDATE ON catalog_snapshots "
                          "FOR EACH ROW EXECUTE FUNCTION catalog_snapshot_guard()"],
    "schema_models": ["CREATE TRIGGER trg_schema_models_guard BEFORE INSERT OR UPDATE ON schema_models "
                      "FOR EACH ROW EXECUTE FUNCTION catalog_content_guard()"],
    "schema_fields": ["CREATE TRIGGER trg_schema_fields_guard BEFORE INSERT OR UPDATE ON schema_fields "
                      "FOR EACH ROW EXECUTE FUNCTION catalog_content_guard()"],
    "account_discoveries": ["CREATE TRIGGER trg_account_discoveries_guard BEFORE UPDATE ON account_discoveries "
                            "FOR EACH ROW EXECUTE FUNCTION catalog_forbid_update()"],
    "catalog_scope_configurations": [
        "CREATE TRIGGER trg_catalog_scope_configurations_guard BEFORE UPDATE "
        "ON catalog_scope_configurations FOR EACH ROW EXECUTE FUNCTION catalog_forbid_update()",
        "CREATE TRIGGER trg_catalog_scope_configurations_tenant BEFORE INSERT "
        "ON catalog_scope_configurations FOR EACH ROW EXECUTE FUNCTION scope_configuration_tenant_guard()",
    ],
    "conversion_scope_models": ["CREATE TRIGGER trg_conversion_scope_models_guard BEFORE UPDATE "
                                "ON conversion_scope_models FOR EACH ROW EXECUTE FUNCTION catalog_forbid_update()"],
    "migration_plan_bindings": [
        "CREATE TRIGGER trg_migration_plan_bindings_guard BEFORE UPDATE "
        "ON migration_plan_bindings FOR EACH ROW EXECUTE FUNCTION plan_binding_guard()",
        "CREATE TRIGGER trg_migration_plan_bindings_tenant BEFORE INSERT "
        "ON migration_plan_bindings FOR EACH ROW EXECUTE FUNCTION plan_binding_tenant_guard()",
    ],
}

# metadata.create_all (tests, fresh databases) installs the same guards as the migration.
for _stmt in IMMUTABILITY_DDL:
    # DDL() applies %-formatting; the plpgsql RAISE placeholders must be escaped.
    event.listen(Base.metadata, "before_create", DDL(_stmt.replace("%", "%%")).execute_if(dialect="postgresql"))
for _stmt in EFFECTIVE_CONTENT_DDL:
    event.listen(Base.metadata, "after_create", DDL(_stmt).execute_if(dialect="postgresql"))
# The functions return schema_models / schema_fields rows, so they must go before metadata.drop_all drops the tables.
for _name in ("models", "fields"):
    event.listen(
        Base.metadata,
        "before_drop",
        DDL(f"DROP FUNCTION IF EXISTS catalog_effective_{_name}(uuid)").execute_if(dialect="postgresql"),
    )
for _model in (CatalogErpConfig, CatalogFieldGroup, CatalogScopeRoute, CatalogSnapshot, SchemaModel, SchemaField,
               AccountDiscovery, CatalogScopeConfiguration, ConversionScopeModel, MigrationPlanBinding):
    for _stmt in TRIGGER_DDL[_model.__tablename__]:
        event.listen(_model.__table__, "after_create", DDL(_stmt).execute_if(dialect="postgresql"))
