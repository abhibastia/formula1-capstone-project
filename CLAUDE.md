# F1 Race Intelligence Platform — working constraints

Databricks Free Edition capstone. Ingestion → medallion (Bronze/Silver/Gold) →
AI/BI dashboards, governed by Unity Catalog. `docs/architecture.md` is the
design and decision record; this file holds the decisions that are expensive to
rediscover.

## Environment

- CLI profile: `abhi` → `dbc-6b3a5534-db75.cloud.databricks.com`. Never auto-pick
  a profile; pass `--profile abhi` explicitly.
- SQL warehouse: `6797e114217fa513` (Serverless Starter).
- **Free Edition has a daily compute quota.** When it is exhausted every
  warehouse and pipeline run fails with "hit your free daily limit". Assume
  compute is scarce: prefer selective refresh over full refresh, and validate
  logic locally before running anything.
- **Catalogs cannot be created over the API on Free Edition** — the CLI, the
  storage-root override, and SQL all refuse. Catalogs must be made in the UI
  with Default Storage. Schemas and Volumes *can* be created via the CLI.

## Non-negotiable design decisions

1. **`dim_driver` is built from the results endpoint, not `/drivers`.** Every
   field `/drivers` returns is static, so Auto CDC over it yields zero history
   rows. The attribute that changes is the driver's constructor, and it only
   exists in results. Verified: this produces 42 versions over 28 drivers, 14 of
   them historical. Do not "simplify" this back to the drivers endpoint.

2. **Sprint points are part of the championship.** Summing only race points
   leaves 13 of 24 drivers short of their official 2024 total. `sprint` is a
   required endpoint, and Gold must expose `total_points = race + sprint`.

3. **Idempotency is a two-part contract and both halves are required.**
   Ingestion skips closed rounds and re-pulls the open one (`landing_writer.py`);
   Silver deduplicates by natural key on the greatest `_ingest_ts`
   (`02_silver_facts.py`). Removing either double-counts the live round.

4. **Bronze reads files as `text`, not `json`.** Optional Ergast fields
   (FastestLap, Sprint, Q3) appear in only some files, so JSON schema inference
   plus `addNewColumns` fails-and-retries the pipeline on first encounter.
   Payloads are single-line JSON, so `wholeText` gives one row per file and
   Silver parses with explicit schemas.

5. **Silver facts are materialized views, not streaming tables.** Deduplication
   is a full-partition window function, which streaming append mode cannot
   express. The SCD-2 CDC sources read Bronze directly because Auto CDC requires
   a streaming source and MVs cannot be streamed.

6. **Gold joins dimensions as-of `race_date`**, never on the current row. A
   current-row join silently reattributes historical results to a driver's
   present team.

## API conventions

- Modern Lakeflow API only: `from pyspark import pipelines as dp`,
  `dp.create_auto_cdc_flow`, `@dp.materialized_view`. Never `import dlt`,
  `apply_changes`, or `LIVE.` prefixes.
- `CREATE OR REFRESH`, never `CREATE OR REPLACE`, for pipeline datasets.
- SCD-2 columns are `__START_AT` / `__END_AT` (double underscore). Current rows:
  `__END_AT IS NULL`.
- Poll a pipeline *update*, not the pipeline, and read
  `error.exceptions[0].message` for the real error — the top-level message only
  says "Update X is FAILED".
- Volume paths in `databricks fs` need the `dbfs:` prefix.

## Jolpica API

- Base `https://api.jolpi.ca/ergast/f1`, no auth. 4 req/s burst, 500 req/hr.
  429s are routine — the client backs off and recovers.
- `total` in a paginated response counts *inner* records, not outer array
  elements. Paging on `len(outer_array)` loops forever.
- Raw JSON is cached in the Volume, so re-runs never need to re-hit the API.
  **Never loop the backfill to fix a downstream bug.**

## Verification bar

Nothing is "done" until `sql/validation_checks.sql` passes:
reconciliation returns zero rows, `dim_driver` returns rows for
`__END_AT IS NOT NULL`, and no Silver fact has duplicate natural keys.
