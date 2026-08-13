# Formula 1 Race Intelligence & Strategy Platform

A governed, end-to-end data pipeline on Databricks Free Edition: public F1 APIs →
Unity Catalog Volume → Lakeflow Declarative Pipeline (Bronze → Silver → Gold) →
AI/BI dashboard. Built as a data-engineering capstone.

## What it does

A scheduled job pulls ten Jolpica-F1 endpoints plus measured race-day weather
from the Open-Meteo ERA5 archive, for three seasons, into a Unity Catalog Volume
as raw JSON. A single triggered Lakeflow pipeline parses, cleans,
deduplicates and quality-checks that data through a medallion architecture,
maintains SCD Type 2 driver and constructor dimensions, and publishes five Gold
marts that two dashboards read. Everything is governed by Unity Catalog; nothing
runs outside Databricks.

```
Jolpica-F1 REST API
      ↓  scheduled Job (rate-limited, retried, idempotent)
UC Volume  f1.raw.landing        raw JSON, partitioned by endpoint/season/round
      ↓  Auto Loader
Bronze  11 streaming tables      raw capture, warn-level expectations only
      ↓
Silver  8 facts + 3 dims         flattened, typed, deduplicated, quarantined
        (2 of them SCD-2)        + one quarantine view per fact
      ↓
Gold    5 marts + event log      business-ready, dimensions joined as-of race date
      ↓
2 AI/BI Dashboards               championship & performance | pace & reliability
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
| `scripts/bootstrap.sh` | Clone → running platform, in one command |
| `scripts/` | Catalog provisioning, upload, pipeline run/poll, executable validation |
| `tests/` | Local suite (`pytest`) and the Spark suite that runs on Databricks |
| `setup_secrets.py` | Secret scope provisioning — not needed today, see above |
| `ACTION_PLAN.md` | Full build plan, decisions, and acceptance criteria |
| `CLAUDE.md` | Standing constraints — read before changing anything |

## Quickstart

One command, from a fresh clone:

```bash
databricks auth login --host https://<workspace>.cloud.databricks.com --profile <name>
./scripts/bootstrap.sh --profile <name>
```

It runs preflight (CLI version, profile, auth), the local test suite, catalog
provisioning, the backfill and upload, `bundle deploy`, and then asks before
running the job — the only step that spends Databricks compute. Steps before it
are free and idempotent, so a failure costs you a re-run and nothing else.

Two things it cannot do for you:

**The catalog must exist first.** Free Edition refuses catalog creation over the
API through every path — CLI, storage-root override, and SQL. Make it once in
the UI: *Catalog → Create catalog → name `f1` → Default storage*. The script
tries all three paths anyway and tells you exactly this if they fail, because
the SQL path is only quota-blocked and may work tomorrow.

**The first backfill takes ~40 minutes.** `landing/` is gitignored — several
hundred JSON payloads reproducible from a public API. Jolpica's sustained limit
is 450 requests/hour and the laps endpoint alone is ~11 pages per race, so the
client paces itself. It uses no Databricks compute, it is resumable, and a
second run makes ~8 calls instead of ~850 because closed rounds are skipped.

There is no default profile anywhere in this repository. Every script names one
explicitly or stops and lists what you have configured — a default meant a fork
ran against a workspace its author had never heard of.

## Running it by hand

The bootstrap script is the sequence below with checks between the steps.
Deployment is split in two on purpose: the **bundle** owns the pipeline, jobs and
dashboards; the **scripts** own the catalog and the raw-data upload, because Free
Edition refuses catalog creation over the API and bulk file upload is not a
bundle concern.

```bash
export DATABRICKS_PROFILE=<name>          # or pass --profile to each script

# 1. Catalog check, schemas, landing volume
./scripts/create_catalog.sh

# 2. Backfill locally, then upload — neither step uses Databricks compute
python3 src/ingestion/ingest.py --mode backfill --root ./landing
./scripts/upload_landing.sh

# 3. Deploy
databricks bundle validate --strict -t dev --profile "$DATABRICKS_PROFILE"
databricks bundle deploy -t dev --profile "$DATABRICKS_PROFILE"

# 4. Run: unit tests -> ingest -> pipeline -> validation
databricks bundle run f1_end_to_end -t dev --profile "$DATABRICKS_PROFILE"
```

`scripts/run_pipeline.sh <pipeline_id>` is an alternative to `bundle run` with
sharper failure output: it polls the *update* rather than the pipeline, and
prints `error.exceptions[0].message` — the top-level message only ever says
"Update X is FAILED".

### Jobs

| Job | When | What |
|---|---|---|
| `f1_end_to_end` | on demand | unit tests → ingest → pipeline → validation. Run this after changing pipeline code. |
| `f1_ingest_incremental` | weekly, Tue 06:00 UTC (paused in dev) | ingest → pipeline. The cheap steady-state run. |

### Testing

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest              # ingestion + repo contracts, no Spark, <1s
python3 scripts/check_expectations.py   # every expectation names a real column
```

Three layers, and each catches something the others cannot:

- **`pytest`** — the pure-Python ingestion logic (pagination, rate budget,
  calendar, idempotent writes) plus contract tests that enforce the rules in
  `CLAUDE.md`: no legacy DLT API, correct dashboard widget versions, no field
  named `constructor`, no pinned profile in `databricks.yml`. Every one of those
  assertions exists because the mistake was made here once.
- **`scripts/check_expectations.py`** — static pre-flight across all five Silver
  files. An expectation naming a column its staged view does not emit fails two
  datasets at runtime and is only found by graph analysis, which costs a cluster
  start and quota.
- **`tests/spark/test_pipeline_transforms.py`** — unit tests for the pipeline's
  own transformation logic (lap-time and pit-duration parsers, the three-level
  laps schema, threshold agreement with the ingestion config). These need a real
  Spark session, so they run on Databricks as the first task of `f1_end_to_end`
  rather than locally. They load the real pipeline files with a stubbed `dp`, so
  no transformation logic is duplicated into the test.

Validation is executable too: `scripts/validate_marts.py` runs the checks in
`sql/validation_checks.sql` and exits non-zero, and is the last task of
`f1_end_to_end`. A green pipeline update is not the bar; reconciliation is.

### Configuration

Copy `.env.example` to `.env` for local overrides. Everything has a working
default except the profile. `databricks.yml` pins neither a host nor a profile —
both come from the CLI profile you pass — so a fork deploys to its own workspace
with no edit to the file.

`setup_secrets.py` provisions a secret scope, and **you almost certainly do not
need it**: Jolpica and Open-Meteo are both keyless and nothing in the repository
reads a secret. It exists for the day Jolpica issues API keys to lift the rate
limit.

### Targets

`dev` (default) prefixes every resource with `[dev <user>]`, pauses the schedule,
and puts the pipeline in development mode. `prod` does none of that and points at
a **separate catalog** (`f1_prod`) — on Free Edition there is only one workspace,
so sharing a catalog would mean a prod deploy silently overwriting dev's tables.
`f1_prod` does not exist yet; create it in the UI before deploying that target.

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
