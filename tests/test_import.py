from coa_db_models import (
    Base,
    User,
    Organization,
    OrganizationMember,
    RefreshToken,
    OrganizationInvitation,
    Project,
    ProjectAccess,
    ProjectDisplayCode,
    Job,
    CoaMapping,
    CoaMappingSuggestion,
    CoaMappingHistory,
    AccountTypeMapping,
    CoaEmbeddingStore,
    File,
    WorkstreamCategory,
    Workstream,
    WorkstreamStage,
    WorkstreamStatusLog,
    OrgERPConnection,
    TargetField,
    ColumnMapping,
    ColumnMappingHistory,
    OrgMappingBookmark,
    ValueMapping,
    ValueMappingHistory,
    ImportRun,
    ImportRecord,
    ConnectorRequest,
    ImportError,
)


def test_all_tables_registered():
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "users",
        "organizations",
        "organization_members",
        "refresh_tokens",
        "organization_invitations",
        "projects",
        "project_access",
        "jobs",
        "coa_mappings",
        "coa_mappings_suggestion",
        "coa_mapping_history",
        "account_type_mappings",
        "coa_embedding_store",
        "project_files",
        "workstream_categories",
        "workstreams",
        "workstream_stages",
        "workstream_status_logs",
        "project_display_codes",
        "target_fields",
        "column_mappings",
        "column_mapping_history",
        "org_mapping_bookmarks",
        "value_mappings",
        "value_mapping_history",
        "import_runs",
        "import_records",
        "connector_requests",
        "import_errors",
    }
    assert expected.issubset(table_names), f"Missing tables: {expected - table_names}"


def test_reexported_symbols():
    assert Base is not None
    assert User.__tablename__ == "users"
    assert Organization.__tablename__ == "organizations"
    assert OrganizationMember.__tablename__ == "organization_members"
    assert RefreshToken.__tablename__ == "refresh_tokens"
    assert OrganizationInvitation.__tablename__ == "organization_invitations"
    assert Project.__tablename__ == "projects"
    assert ProjectAccess.__tablename__ == "project_access"
    assert Job.__tablename__ == "jobs"
    assert CoaMapping.__tablename__ == "coa_mappings"
    assert CoaMappingSuggestion.__tablename__ == "coa_mappings_suggestion"
    assert CoaMappingHistory.__tablename__ == "coa_mapping_history"
    assert AccountTypeMapping.__tablename__ == "account_type_mappings"
    assert CoaEmbeddingStore.__tablename__ == "coa_embedding_store"
    assert File.__tablename__ == "project_files"


def test_workstream_tables_registered():
    assert WorkstreamCategory.__tablename__ == "workstream_categories"
    assert Workstream.__tablename__ == "workstreams"
    assert WorkstreamStage.__tablename__ == "workstream_stages"
    assert WorkstreamStatusLog.__tablename__ == "workstream_status_logs"


def test_mcp_connections_tables_registered():
    table_names = set(Base.metadata.tables.keys())
    assert "org_erp_connections" in table_names, "Missing table: org_erp_connections"


def test_org_erp_connection_model():
    assert OrgERPConnection.__tablename__ == "org_erp_connections"
    cols = {c.name for c in OrgERPConnection.__table__.columns}
    for col in ("id", "org_id", "label", "erp_id", "connection_role", "base_url",
                "auth_strategy", "erp_config", "status", "consecutive_failures",
                "version", "created_at", "updated_at"):
        assert col in cols, f"OrgERPConnection missing column: {col}"
    id_col = OrgERPConnection.__table__.c.id
    assert id_col.server_default is not None, "OrgERPConnection.id must have a server_default"


def test_value_mapping_tables_registered():
    assert ValueMapping.__tablename__ == "value_mappings"
    assert ValueMappingHistory.__tablename__ == "value_mapping_history"

    vm_cols = {c.name for c in ValueMapping.__table__.columns}
    for col in (
        "id", "run_id", "source_field", "source_value", "mapping_subtype",
        "transformation_type", "status", "mapping_source", "updated_at",
    ):
        assert col in vm_cols, f"ValueMapping missing column: {col}"

    id_col = ValueMapping.__table__.c.id
    assert id_col.server_default is not None, "ValueMapping.id must have a server_default"

    vm_indexes = {i.name for i in ValueMapping.__table__.indexes}
    assert "uix_value_mappings_run_field_value" in vm_indexes, \
        "ValueMapping missing unique index uix_value_mappings_run_field_value"

    hist_cols = {c.name for c in ValueMappingHistory.__table__.columns}
    for col in (
        "id", "mapping_id", "run_id", "changed_by", "changed_at",
        "previous_status", "new_status",
        "previous_transformation_type", "new_transformation_type",
        "previous_notes", "new_notes", "reason",
    ):
        assert col in hist_cols, f"ValueMappingHistory missing column: {col}"


def test_pipeline_column_mapping_tables_registered():
    assert TargetField.__tablename__ == "target_fields"
    assert ColumnMapping.__tablename__ == "column_mappings"
    assert ColumnMappingHistory.__tablename__ == "column_mapping_history"
    assert OrgMappingBookmark.__tablename__ == "org_mapping_bookmarks"

    tf_cols = {c.name for c in TargetField.__table__.columns}
    for col in ("id", "erp_id", "scope", "field_id", "label", "dtype", "source", "created_at"):
        assert col in tf_cols, f"TargetField missing column: {col}"

    cm_cols = {c.name for c in ColumnMapping.__table__.columns}
    for col in ("id", "run_id", "source_field", "status", "mapping_source", "updated_at"):
        assert col in cm_cols, f"ColumnMapping missing column: {col}"

    hist_cols = {c.name for c in ColumnMappingHistory.__table__.columns}
    for col in ("id", "mapping_id", "run_id", "previous_status", "new_status", "changed_at"):
        assert col in hist_cols, f"ColumnMappingHistory missing column: {col}"

    bm_cols = {c.name for c in OrgMappingBookmark.__table__.columns}
    for col in ("id", "org_id", "erp_id", "scope", "source_field", "mapping_type", "payload"):
        assert col in bm_cols, f"OrgMappingBookmark missing column: {col}"




def test_dab16_column_additions():
    # display codes live in their own table (project_display_codes), not inline on projects
    assert ProjectDisplayCode.__tablename__ == "project_display_codes"
    pdc_cols = {c.name for c in ProjectDisplayCode.__table__.columns}
    for col in ("id", "project_id", "display_code", "org_part", "source_part", "target_part", "seq"):
        assert col in pdc_cols, f"ProjectDisplayCode missing column: {col}"

    org_cols = {c.name for c in Organization.__table__.columns}
    assert "code" in org_cols, "Organization missing column: code"

    file_cols = {c.name for c in File.__table__.columns}
    assert "workstream_id" in file_cols, "File missing column: workstream_id"


def test_catalog_tables_registered_with_immutability_guards():
    from coa_db_models import (
        AccountDiscovery,
        CatalogErpConfig,
        CatalogFieldGroup,
        CatalogScopeConfiguration,
        CatalogScopeRoute,
        CatalogSnapshot,
        ConversionScopeModel,
        MigrationPlanBinding,
        OutboxEvent,
        SchemaField,
        SchemaModel,
    )
    from coa_db_models.catalog.models import TRIGGER_DDL

    tables = {m.__tablename__ for m in (CatalogErpConfig, CatalogFieldGroup, CatalogScopeRoute,
                                        CatalogSnapshot, SchemaModel, SchemaField, AccountDiscovery,
                                        CatalogScopeConfiguration, ConversionScopeModel, MigrationPlanBinding,
                                        OutboxEvent)}
    assert tables <= set(Base.metadata.tables)
    assert set(TRIGGER_DDL) == {"catalog_erp_configs", "catalog_field_groups", "catalog_scope_routes",
                                "catalog_snapshots", "schema_models", "schema_fields", "account_discoveries",
                                "catalog_scope_configurations", "conversion_scope_models",
                                "migration_plan_bindings"}


def test_import_run_model():
    assert ImportRun.__tablename__ == "import_runs"

    cols = {c.name for c in ImportRun.__table__.columns}
    for col in (
        "id", "run_id", "triggered_by", "status", "run_code", "batch_size", "req_per_sec",
        "rows_attempted", "rows_imported", "rows_failed", "rows_skipped", "rows_reconciled",
        "duration_ms", "error_detail", "started_at", "completed_at", "updated_at", "created_at",
    ):
        assert col in cols, f"ImportRun missing column: {col}"

    constraint_names = {c.name for c in ImportRun.__table__.constraints}
    assert "ck_import_runs_status" in constraint_names, (
        "ImportRun missing CHECK constraint: ck_import_runs_status"
    )

    index_names = {i.name for i in ImportRun.__table__.indexes}
    assert "uix_import_runs_run_active" in index_names, (
        "ImportRun missing partial unique index: uix_import_runs_run_active"
    )

    updated_at_col = ImportRun.__table__.c.updated_at
    assert updated_at_col.server_default is not None, "ImportRun.updated_at must have a server_default"


def test_import_record_model():
    assert ImportRecord.__tablename__ == "import_records"

    cols = {c.name for c in ImportRecord.__table__.columns}
    for col in (
        "id", "import_run_id", "source_row_index", "internal_id", "display_name",
        "batch_code", "outcome", "target_id", "latency_ms", "created_at",
    ):
        assert col in cols, f"ImportRecord missing column: {col}"

    constraint_names = {c.name for c in ImportRecord.__table__.constraints}
    assert "ck_import_records_outcome" in constraint_names, (
        "ImportRecord missing CHECK constraint: ck_import_records_outcome"
    )
    assert "uix_import_records_run_row" in constraint_names, (
        "ImportRecord missing UniqueConstraint on (import_run_id, source_row_index)"
    )


def test_connector_request_model():
    assert ConnectorRequest.__tablename__ == "connector_requests"

    cols = {c.name for c in ConnectorRequest.__table__.columns}
    for col in (
        "id", "import_run_id", "request_code", "operation", "erp_model",
        "record_ref", "batch_code", "http_status", "latency_ms", "retries",
        "request_payload", "response_payload", "created_at",
    ):
        assert col in cols, f"ConnectorRequest missing column: {col}"

    constraint_names = {c.name for c in ConnectorRequest.__table__.constraints}
    assert "uix_connector_requests_run_code" in constraint_names, (
        "ConnectorRequest missing UniqueConstraint on (import_run_id, request_code)"
    )
    assert "ck_connector_requests_operation" in constraint_names, (
        "ConnectorRequest missing CHECK constraint on operation"
    )


def test_import_error_model():
    assert ImportError.__tablename__ == "import_errors"

    cols = {c.name for c in ImportError.__table__.columns}
    for col in (
        "id", "import_run_id", "connector_request_id", "source_row_index",
        "record_ref", "batch_code", "error_title", "error_detail",
        "retry_class", "parsed_by", "status", "idempotency_key",
        "source_field", "raw_value", "written_to", "value_sent", "erp_response",
        "deterministic_rule", "ai_analysis", "ai_likely_cause", "ai_cause_category",
        "ai_fix_suggestion", "ai_fix_step", "ai_model", "created_at",
    ):
        assert col in cols, f"ImportError missing column: {col}"

    constraint_names = {c.name for c in ImportError.__table__.constraints}
    assert "ck_import_errors_retry_class" in constraint_names, (
        "ImportError missing CHECK constraint: ck_import_errors_retry_class"
    )
    assert "ck_import_errors_parsed_by" in constraint_names, (
        "ImportError missing CHECK constraint: ck_import_errors_parsed_by"
    )
    assert "ck_import_errors_status" in constraint_names, (
        "ImportError missing CHECK constraint: ck_import_errors_status"
    )

    index_names = {i.name for i in ImportError.__table__.indexes}
    assert "ix_import_errors_run_row" in index_names, (
        "ImportError missing index on (import_run_id, source_row_index)"
    )
    assert "uix_import_errors_idempotency" in index_names, (
        "ImportError missing partial unique index on (import_run_id, idempotency_key)"
    )
    idempotency_idx = next(i for i in ImportError.__table__.indexes if i.name == "uix_import_errors_idempotency")
    assert idempotency_idx.unique, "uix_import_errors_idempotency must be unique"
    assert "postgresql_where" in idempotency_idx.kwargs, (
        "uix_import_errors_idempotency must be a partial index (WHERE idempotency_key IS NOT NULL)"
    )
