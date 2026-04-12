# coa-db-models

Shared SQLAlchemy models for the COA Migration platform.

## Install

```bash
pip install "coa-db-models @ git+https://github.com/<org>/coa-db-models.git@develop"
```

## Usage

```python
from coa_db_models import Base, User, Project, CoaMapping
```

All models and the `Base` declarative base are re-exported from the top-level package.
