# coa-db-models

Shared SQLAlchemy models and Alembic migrations for the COA Migration platform.

## Install

```bash
pip install "coa-db-models @ git+https://github.com/<org>/coa-db-models.git@develop"
```

## Usage

```python
from coa_db_models import Base, User, Project, CoaMapping, CoaEmbeddingStore
```

All models and the `Base` declarative base are re-exported from the top-level package.

## Models

| Module | Models | Tables |
|--------|--------|--------|
| `auth` | User, Organization, OrganizationMember, RefreshToken, Invitation | users, organizations, organization_members, refresh_tokens, invitations |
| `projects` | Company, Project, ProjectAccess | companies, projects, project_access |
| `jobs` | Job | jobs |
| `mappings` | CoaMapping, CoaMappingSuggestion, CoaMappingHistory, AccountTypeMapping, CoaEmbeddingStore | coa_mappings, coa_mappings_suggestion, coa_mapping_history, account_type_mappings, coa_embedding_store |
| `storage` | File | project_files |

## Migrations

This package owns all Alembic migrations. Consuming repos do **not** maintain their own migrations.

### Setup

```bash
cp .env.example .env
# Edit .env with your DATABASE_URL
```

### Run migrations

```bash
uv sync
uv run alembic upgrade head
```

### Generate a new migration after model changes

```bash
uv run alembic revision --autogenerate -m "describe the change"
```

## Seed data

Insert demo data (users, companies, projects, sample mappings):

```bash
uv run python seed.py
```

Requires `DATABASE_URL` in `.env` or environment. Skips if data already exists.
