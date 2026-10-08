# Catalogue Loader

One-time loading of the ERP catalogue into PostgreSQL. It lives in `coa-db-models` next to the migration that creates the catalogue tables, and is not part of the `coa-db-models` wheel.

The loader performs two tasks:

1. **ERP configuration.** It inserts a version of each ERP's catalogue configuration into `catalog_erp_configs`, `catalog_field_groups` and `catalog_scope_routes`. The configuration defines the ERP settings, the field groups and which models make up each scope. These tables replace the former backend YAML files.
2. **Baselines.** It verifies a published erp-schema-graph snapshot, converts it into catalogue rows and publishes it as a shared baseline. A shared baseline has `org_id` NULL and is used by every organisation.

The loader runs from a laptop or from CI against the target environment's database, for example through an SSH tunnel. Graph files are never copied to application servers. After loading, the backend and the ML service work from the database alone.

## 1. Prerequisites

- Python 3.13 and `uv`.
- A database URL for the target environment, in the form `postgresql+psycopg://user:password@host:5432/dbname`.
- The built graph snapshots (a directory that contains `snapshots/<id>/`). Only the CSV tables and the JSON metadata files are needed.

The snapshot reader and verifier are copied from `erp_schema_graph` into `catalog_loader/graph/` (see its `__init__.py` for the source commit), so that repository is not needed.

```bash
cd coa-db-models
uv sync --group loader
```

## 2. Order of operations (per environment)

Deploys run both steps automatically (`.github/workflows/ci-deploy-*.yml`), after the migrations:

```bash
DATABASE_URL=<url> uv run alembic upgrade head
DATABASE_URL=<url> uv run python -m catalog_loader sync
```

`sync` seeds every file in `seed/erp_configs/`, then loads each snapshot in `catalog_snapshots.lock` that is not
yet loaded. It downloads from R2 (any S3-compatible store) using these variables in the environment's `.env` file:

| Variable | Value |
|---|---|
| `CATALOG_S3_ENDPOINT` | `https://<account_id>.r2.cloudflarestorage.com` |
| `CATALOG_S3_ACCESS_KEY` | R2 API token access key ID (read-only is enough) |
| `CATALOG_S3_SECRET_KEY` | R2 API token secret |
| `CATALOG_S3_BUCKET` | Bucket name |
| `CATALOG_S3_REGION` | `auto` (default) |

Snapshots already loaded are skipped without downloading. `--source-dir DIR` reads staged files from a local
directory instead of R2.

The individual commands remain available: `seed-erp-config FILE` and
`load-baseline --store DIR --snapshot ID` against an unpacked snapshot directory.

## 3. Adding a snapshot (for example Odoo 18.0 Enterprise)

1. Build it in `erp_schema_graph`; it appears under `artifacts/snapshots/<id>/`.
2. Stage it. This verifies it, copies its files uncompressed (CSV tables, JSONL, JSON metadata) to
   `staged/catalog-snapshots/<id>/` and adds its entry to `catalog_snapshots.lock`:
   ```bash
   uv run python -m catalog_loader stage /path/to/erp_schema_graph/artifacts/snapshots/<id>
   ```
3. Upload the staged files:
   ```bash
   aws s3 sync staged/catalog-snapshots "s3://<bucket>/catalog-snapshots" \
     --endpoint-url https://<account_id>.r2.cloudflarestorage.com
   ```
4. Commit `catalog_snapshots.lock` in a pull request. The next deploy of each environment loads only the new snapshot.

If `erp_schema_graph` changed the CSV format, `stage` fails because the headers no longer match
`catalog_loader/graph/`. Copy the new reader files into `catalog_loader/graph/` in the same pull request.

## 4. Command behaviour

### 4.1 `seed-erp-config`

- **Validation:** the ERP id format, the scopes, the roles, that every referenced field group exists, and that no route is duplicated.
- **Write:** in one transaction, it creates version N+1 with its field groups and scope routes, retires the active version and activates the new one.
- **Repeats:** if the active version already has the same content, nothing changes. Notes do not count as content.
- **Purpose:** the JSON files in `seed/erp_configs/` are bootstrap data only. Later changes are made as new versions through the backend, not by editing these files.

### 4.2 `load-baseline`

**Input.** By default (`--source csv`) the loader reads the snapshot's relational CSV tables
(`models.csv`, `fields.csv`, `edges.csv`, `bindings.csv`, `properties.csv`, `annotations.csv`,
`model_links.csv`, `constraints.csv`, `field_origin.csv`, described by `tables.json`) through
`catalog_loader.graph.tables.read_tables`, and does not need `nodes.jsonl` / `edges.jsonl`. Before loading,
`catalog_loader.graph.snapshot.verify` checks every file hash, that the CSV tables rebuild the JSONL byte for
byte, the snapshot identity and the contract. `--source jsonl` reads the JSONL files instead; both give the
same rows.

1. **Rejects** account-scoped graphs. Customer-specific content arrives through account overlays in the backend.
2. **Requires** an active configuration for the graph's ERP. That configuration supplies the custom-field prefixes.
3. **Identifies** the snapshot by `(kind, catalogue contract, graph snapshot id)`. Re-running the command reports the existing snapshot and writes nothing. An interrupted load resumes.
4. **Inserts** the models and fields in batches, records the content hash, counts and diagnostics, and publishes:
   - the previous snapshot of the same lineage is linked, with a change report;
   - a `catalog.event.snapshot_published` outbox event is written for downstream consumers;
   - all of this commits in one transaction.
5. **On a validation failure,** marks the snapshot `failed`, records the problems and removes partial rows.

The loader does not build scope configurations. The backend builds them per snapshot from the active ERP configuration when they are first needed.

## 5. Reference timings (local, catalog_demo2)

| Snapshot | Models | Fields | First load | Repeat |
|---|---|---|---|---|
| odoo-18.0-3c92dbec93d9b412af1c | 1,339 | 27,367 | 20 s | 0.5 s |
| netsuite-2025.2-04a4c4733a79fc301a52 | 572 | 21,075 | 10 s | 0.4 s |

## 6. Tests

```bash
uv run pytest -q tests
```

The database tests create and drop a scratch database `catalog_loader_test` on `localhost:5432`. They are skipped if PostgreSQL is not available.
