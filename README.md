# Formula 1 Race Intelligence & Strategy Platform

A governed, end-to-end data pipeline on Databricks Free Edition: public F1 APIs →
Unity Catalog Volume → Lakeflow Declarative Pipeline (Bronze → Silver → Gold) →
AI/BI dashboard. Built as a data-engineering capstone.

## What it does

A scheduled job pulls eight Jolpica-F1 endpoints for three seasons into a Unity
Catalog Volume as raw JSON. A single triggered Lakeflow pipeline parses, cleans,
deduplicates and quality-checks that data through a medallion architecture,
maintains SCD Type 2 driver and constructor dimensions, and publishes two Gold
marts that a dashboard reads. Everything is governed by Unity Catalog; nothing
runs outside Databricks.

```
Jolpica-F1 REST API
      ↓  scheduled Job (rate-limited, retried, idempotent)
UC Volume  f1.raw.landing        raw JSON, partitioned by endpoint/season/round
      ↓  Auto Loader
Bronze  8 streaming tables       raw capture, warn-level expectations only
      ↓
Silver  6 facts + 2 SCD-2 dims   flattened, typed, deduplicated, quarantined
      ↓
Gold    2 marts + event log      business-ready, dimensions joined as-of race date
      ↓
AI/BI Dashboard
```

## Layout

| Path | What |
|---|---|
| `src/ingestion/` | API client, landing writer, job entry point |
| `src/pipeline/` | Lakeflow pipeline: `01_bronze` → `04_gold` |
| `sql/validation_checks.sql` | Correctness checks — the bar for "done" |
| `sql/dq_event_log.sql` | Data-quality metrics from the pipeline event log |
| `dashboards/` | AI/BI dashboard definition |
| `databricks.yml`, `resources/` | Asset Bundle: pipeline, job and dashboard as code |
| `scripts/` | Catalog provisioning, raw-data upload, pipeline run/poll |
| `ACTION_PLAN.md` | Full build plan, decisions, and acceptance criteria |
| `CLAUDE.md` | Standing constraints — read before changing anything |

## Running it

Deployment is split in two on purpose. The **bundle** owns the pipeline, job and
dashboard. The **scripts** own the catalog and the raw-data upload, because Free
Edition refuses catalog creation over the API and bulk file upload is not a
bundle concern.

Once, by hand — Free Edition **cannot create catalogs over the API**:

> Catalog → Create catalog → name `f1` → Default storage

Then:

```bash
# 1. Catalog check, schemas, landing volume
./scripts/create_catalog.sh

# 2. Backfill locally, then upload — neither step uses Databricks compute
python3 src/ingestion/ingest.py --mode backfill --root ./landing
./scripts/upload_landing.sh

# 3. Deploy and run the bundle
databricks bundle validate --strict -t dev --profile abhi
databricks bundle deploy -t dev --profile abhi
databricks bundle run f1_medallion_pipeline -t dev --profile abhi
```

`scripts/run_pipeline.sh <pipeline_id>` is an alternative to `bundle run` with
sharper failure output: it polls the *update* rather than the pipeline, and
prints `error.exceptions[0].message` — the top-level message only ever says
"Update X is FAILED".

The backfill is deliberately run locally: Free Edition has a daily compute quota,
and the Files API upload needs none. Re-running ingestion is cheap — closed
rounds are skipped, so a second run makes ~8 API calls instead of ~260.

### Targets

`dev` (default) prefixes every resource with `[dev <user>]`, pauses the schedule,
and puts the pipeline in development mode. `prod` does none of that and points at
a **separate catalog** (`f1_prod`) — on Free Edition there is only one workspace,
so sharing a catalog would mean a prod deploy silently overwriting dev's tables.

## Three decisions worth knowing

**SCD-2 is built from results, not from `/drivers`.** Every field the drivers
endpoint returns is static, so Auto CDC over it produces a dimension with no
history at all — the pattern implemented but never exercised. Driver → constructor
is the attribute that actually changes, and it only appears in results. This
yields 42 versions across 28 drivers, 14 of them historical.

**Sprint points are part of the championship.** Summing race points alone leaves
13 of 24 drivers short of their official 2024 total. With sprint points, the
reconciliation against the independent standings endpoint is exact.

**Idempotency is a two-part contract.** Ingestion skips closed rounds and
re-pulls the open one; Silver deduplicates by natural key on the newest
`_ingest_ts`. Both halves are required — drop either and the live round
double-counts.

## Known limitations

- Batch, not streaming. The source is post-session and public; the triggered
  design is deliberate, not a compromise.
- No tyre-compound data — that requires FastF1, which is a roadmap item. Pit and
  stint analysis is possible from Jolpica; tyre strategy is not.
- Jolpica is community-maintained. Raw JSON is cached in the Volume so the
  pipeline never depends on the API being up.
