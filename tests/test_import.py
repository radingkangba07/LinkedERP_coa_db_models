from coa_db_models import (
    Base,
    User,
    Organization,
    OrganizationMember,
    RefreshToken,
    OrganizationInvitation,
    Project,
    ProjectAccess,
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


def test_dab16_column_additions():
    project_cols = {c.name for c in Project.__table__.columns}
    for col in ("display_code", "display_code_org", "display_code_src", "display_code_tgt", "display_code_seq"):
        assert col in project_cols, f"Project missing column: {col}"

    org_cols = {c.name for c in Organization.__table__.columns}
    assert "code" in org_cols, "Organization missing column: code"

    file_cols = {c.name for c in File.__table__.columns}
    assert "workstream_id" in file_cols, "File missing column: workstream_id"
