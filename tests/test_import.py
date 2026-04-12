from coa_db_models import (
    Base,
    User,
    Organization,
    OrganizationMember,
    RefreshToken,
    Company,
    Project,
    ProjectAccess,
    Job,
    CoaMapping,
    CoaMappingSuggestion,
    File,
)


def test_all_tables_registered():
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "users",
        "organizations",
        "organization_members",
        "refresh_tokens",
        "companies",
        "projects",
        "project_access",
        "jobs",
        "coa_mappings",
        "coa_mappings_suggestion",
        "project_files",
    }
    assert expected.issubset(table_names), f"Missing tables: {expected - table_names}"


def test_reexported_symbols():
    assert Base is not None
    assert User.__tablename__ == "users"
    assert Organization.__tablename__ == "organizations"
    assert OrganizationMember.__tablename__ == "organization_members"
    assert RefreshToken.__tablename__ == "refresh_tokens"
    assert Company.__tablename__ == "companies"
    assert Project.__tablename__ == "projects"
    assert ProjectAccess.__tablename__ == "project_access"
    assert Job.__tablename__ == "jobs"
    assert CoaMapping.__tablename__ == "coa_mappings"
    assert CoaMappingSuggestion.__tablename__ == "coa_mappings_suggestion"
    assert File.__tablename__ == "project_files"
