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
