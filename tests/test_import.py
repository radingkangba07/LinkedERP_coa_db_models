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
)
from coa_db_models.workstreams.models import (
    WorkstreamCategory,
    Workstream,
    WorkstreamStage,
    WorkstreamStatusLog,
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
