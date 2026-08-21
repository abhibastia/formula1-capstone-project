# Formula 1 Race Intelligence & Strategy Platform

A governed, end-to-end data pipeline on Databricks Free Edition: public F1 APIs →
Unity Catalog Volume → Lakeflow Declarative Pipeline (Bronze → Silver → Gold) →
AI/BI dashboards. Built as a data-engineering capstone.

`docs/architecture.md` is the design record — how the platform works, plus a data
dictionary in §7. `docs/adr/` holds ten Architecture Decision Records covering
why it is built this way and what was rejected, including the decisions that
turned out to be wrong.
**§7 is the data dictionary**: the grain of every stored dataset, and the
definition of every metric the project measures.

## Who it is for

People who follow Formula 1 and want to **interrogate** a season rather than read
a summary of it:

- **Reporters** checking a claim before publishing — was that win earned on pace
  or inherited in the pit lane, and did the stewards change the result after the
  flag.
- **Fans and analysts** arguing about whether a driver was actually quick, which
  the points table cannot answer: 150 driver-races in this dataset finished at
  least three places behind their own pace.

That audience drives the architecture more than the data volume does. The data is
small — roughly 1,200 race results — so nothing here is sized for scale. It is
sized for **trust**: every number on a dashboard traces back to a raw API
payload, and a wrong number has to be findable rather than merely absent.

## What it does

A scheduled job pulls ten Jolpica-F1 endpoints plus measured race-day weather
from the Open-Meteo ERA5 archive, for every season since 2024, into a Unity
Catalog Volume as raw JSON. A single triggered Lakeflow pipeline parses, cleans,
deduplicates and quality-checks that data through a medallion architecture,
maintains SCD Type 2 driver and constructor dimensions, and publishes six Gold
marts that one AI/BI dashboard reads, organised by analyst decision. Everything is governed by Unity Catalog; nothing
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
Gold    6 marts + event log      business-ready, dimensions joined as-of race date
      ↓
AI/BI Dashboard                  one page per analyst decision:
        + Genie agent            driver form · constructors · circuits · championship · trust
```

## Layout

| Path | What |
|---|---|
| `src/ingestion/` | API client, landing writer, job entry point |
| `src/pipeline/` | Lakeflow pipeline: `01_bronze` → `04_gold` |
| `scripts/apply_grants.py` | The Unity Catalog access model, idempotent, no compute |
| `sql/validation_checks.sql` | Correctness checks — the bar for "done" |
| `sql/dq_event_log.sql` | Data-quality metrics from the pipeline event log |
| `dashboards/` | The AI/BI dashboard definition — five decision pages |
| `databricks.yml`, `resources/` | Asset Bundle: pipeline, two jobs and the dashboard as code |
| `scripts/bootstrap.sh` | Clone → running platform, in one command |
| `scripts/` | Catalog provisioning, upload, pipeline run/poll, executable validation |
| `tests/` | Local suite (`pytest`) and the Spark suite that runs on Databricks |
| `genie/` | Genie agent definition — natural-language access, scoped to Gold |
| `docs/deck/build_deck.py` | The capstone presentation, generated — `python3 docs/deck/build_deck.py` |
| `setup_secrets.py` | Secret scope provisioning — not needed today, see above |
| `docs/architecture.md` | Design, data dictionary (§7), and criteria coverage |
| `docs/adr/` | Architecture Decision Records — why, and what else was on the table |
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
| `f1_ingest_incremental` | weekly, Tue 06:00 UTC (paused in dev) | ingest → pipeline → validation. The steady-state run. |

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

### Access control

```bash
python3 scripts/apply_grants.py --profile <name> --dry-run   # show the diff
python3 scripts/apply_grants.py --profile <name>             # apply
python3 scripts/apply_grants.py --profile <name> --show      # read back
```

Read access narrows as the data gets rawer, which is the argument for a
medallion layout in the first place:

| Principal | Catalog | Gold | Silver / Bronze | Landing Volume |
|---|---|---|---|---|
| `account users` | `USE_CATALOG` | `SELECT` | — | — |
| `--engineers <group>` | `USE_CATALOG` | `SELECT` | `SELECT` | `READ_VOLUME` |
| owner | everything by ownership | | | |

An analyst can query `f1.gold.driver_performance` and **cannot** read the Bronze
payload it came from or the raw JSON behind it. That is the demonstrable half of
governance — not that permissions exist, but that they differ by layer and you
can prove which.

Two constraints worth knowing. Unity Catalog resolves **account-level** groups
and user emails only: this workspace lists `admins` and `users` under
`databricks groups list` and UC rejects both with *"Could not find principal"*.
So the engineer tier is a parameter — omit it on a single-user workspace and
those layers stay owner-only, which is the right answer there. And nobody is
ever granted `WRITE_VOLUME`: the landing zone has exactly one writer, the
ingestion job, because a second writer breaks the idempotency contract that lets
Silver deduplicate on the newest `_ingest_ts`.

Grants live with `create_catalog.sh` rather than in the bundle, on the same
boundary: the bundle owns the pipeline, jobs and dashboards, and deliberately
does not own the catalog or schemas — a `bundle destroy` that dropped them would
take the data with it. The script uses the UC permissions API, so it costs no
compute and works with the daily quota exhausted.

### Semantic layer — the metric view

`f1.gold.driver_metrics` is a Unity Catalog metric view over
`driver_performance`, defined in `sql/metrics/driver_performance_metrics.sql`.
Thirteen governed measures across nine dimensions, queried with `MEASURE()`:

```sql
SELECT `Team`, MEASURE(`Points Per Start`), MEASURE(`DNF Rate`)
FROM f1.gold.driver_metrics WHERE `Season` = 2024 GROUP BY ALL
```

It exists so the dashboard, the Genie agent and an ad-hoc query resolve
`Total Points` to the same expression by construction rather than by everyone
remembering. Verified in parity with the mart: zero drivers disagreeing.

### Natural-language access — Genie

`genie/f1_gold_space.json` defines a Genie agent scoped to the five Gold marts.
It is version-controlled because a space configured only in the UI is a space
nobody can rebuild.

```bash
databricks workspace mkdirs /Workspace/Users/<you>/genie_spaces --profile <name>
databricks genie create-space --profile <name> --json "{
  \"warehouse_id\": \"<warehouse-id>\",
  \"title\": \"F1 Race Intelligence — Gold\",
  \"parent_path\": \"/Workspace/Users/<you>/genie_spaces\",
  \"serialized_space\": $(python3 -c 'import json;print(json.dumps(open("genie/f1_gold_space.json").read()))')
}"
```

**Gold only, deliberately.** Point a natural-language agent at Silver and it
will join a driver to their *current* team and report a 2024 result under the
wrong constructor — plausible, formatted, and wrong. The marts already resolve
the as-of-race-date join. `pytest` fails if the scope is ever widened.

It carries five certified SQL examples, each executed against the warehouse
before being committed, and one instruction block encoding the rules that change
answers: always use `total_points`, never assume a driver's current team,
`weather_available = false` means *no observation* rather than a dry race, and
pace is ranked on `median_clean_lap_s` rather than finishing position.

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

## Grain, in one line each

| Layer | Grain |
|---|---|
| Landing | one JSON file per API call, per endpoint / season / round |
| Bronze | one row per landed file |
| Silver facts | driver × race — except **pit stops** (driver × race × stop) and **laps** (driver × race × lap, 65,862 rows) |
| Silver dimensions | one row per version — `dim_driver` holds 42 versions across 28 drivers |
| Gold marts | driver × race, driver × round, or race — never finer |

The lap is the finest grain and the reason the project can separate *who was
quick* from *who finished ahead*. It is aggregated to driver × race before it
reaches a dashboard.

Full grain and metric definitions: `docs/architecture.md` §7.

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
- **No amendment history on the facts.** Change Data Feed is *unsupported* on
  materialised views, and the Silver facts are materialised views for a reason
  (deduplication is a full-partition window function). So "what did the stewards
  change after publication" cannot be answered without converting them to
  streaming tables. CDF is already enabled on the streaming tables — Bronze and
  both SCD-2 dimensions — where Lakeflow sets it by default. See §5.4.
- **The access model cannot be demonstrated on this workspace.** Grants are
  applied and correct, but the owner's ownership outranks every one of them, so
  proving the layering needs a second identity that owns nothing.
- `f1_prod` is wired in the bundle but its catalog does not exist. Free Edition
  cannot create catalogs over the API.
