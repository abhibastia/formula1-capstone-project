# F1 Race Intelligence Platform — MVP Action Plan

**Companion to** `f1_capstone_prep.md` (the *what* and *why*). This document is the *how*: locked decisions, build order, and acceptance criteria.

**Platform:** Databricks Free Edition, serverless. No external cloud.
**Status:** repo currently contains documentation only — all code below is to be written.

---

## 0. Decisions locked before any code is written

These are the choices that are expensive to change later. Each has a recommendation; the three marked ⚠️ need your explicit confirmation.

### 0.1 Seasons in scope ⚠️

**Recommendation: 2024 + 2025 as the historical backfill, 2026 as the live incremental season.**

Rationale: 2024 and 2025 are complete and immutable — ideal for a one-shot backfill. 2026 is in progress as of August 2026, so the scheduled Job picks up new rounds for real. This converts the "no real streaming source" weakness in the prep doc into a genuine incremental-ingestion story with zero extra engineering. It also guarantees the pipeline is exercised again between build and demo.

Request budget check: 2 backfill seasons × ~24 rounds × 4 per-round endpoints ≈ 192 calls, plus ~10 season-level calls. Comfortably inside Jolpica's 500/hour sustained limit in a single backfill run. Incremental runs are ~4 calls per round.

### 0.2 Endpoint set (frozen for MVP)

| Endpoint | Path | Grain | Cadence |
|---|---|---|---|
| Races | `/{season}/races/` | season | once per season |
| Drivers | `/{season}/drivers/` | season | once per season |
| Constructors | `/{season}/constructors/` | season | once per season |
| **Sprint** | `/{season}/sprint/` | season | once per season |
| Results | `/{season}/{round}/results/` | round | per round |
| Qualifying | `/{season}/{round}/qualifying/` | round | per round |
| Driver standings | `/{season}/{round}/driverStandings/` | round | per round |
| Constructor standings | `/{season}/{round}/constructorStandings/` | round | per round |

**`sprint` was added during implementation, and it is not optional.** Sprint races award championship points (8 down to 1 for the top eight). Reconciling the landed 2024 data proved the point: summing race points alone leaves **13 of 24 drivers** short of their official season total; adding sprint points brings mismatches to **zero**. Without this endpoint every mart understates points on the ~6 sprint weekends a season. It is fetched at season level (~2 calls per season) rather than per round, so the cost is negligible.

**Explicitly out of MVP:** `laps`, `pitstops`, FastF1, OpenF1, weather. `laps` in particular is one request *per round* returning a large paginated payload — it is the single fastest way to blow the rate limit and the compute quota. It belongs to the `gold_race_strategy` stretch mart, not here.

### 0.2a Free Edition platform limits discovered during build

Two constraints that are not documented anywhere obvious and cost real time:

- **Catalogs cannot be created over the API.** `databricks catalogs create` fails
  with *"Metastore storage root URL does not exist"*; supplying the metastore's
  own default-storage root fails with *"Please use the UI to create a catalog
  with Default Storage"*; `CREATE CATALOG` over SQL needs a warehouse. The
  catalog must be created once by hand in the UI. Schemas and Volumes are fine
  over the CLI.
- **There is a daily compute quota**, and it applies to the SQL warehouse and
  pipeline compute alike: *"cannot run the resource because you have hit your
  free daily limit"*. This is the single biggest practical risk to the build,
  because every failed pipeline run spends quota that cannot be recovered until
  the next day. Mitigations adopted: run the API backfill locally and upload via
  the Files API (no compute), validate transformation semantics in plain Python
  before running Spark, and read files as `text` in Bronze so schema inference
  cannot fail the first run.

### 0.3 Catalog and schema layout

```
f1                       (catalog)
├── raw                  (schema)  └── landing   (UC Volume — raw JSON)
├── bronze               (schema)  streaming tables, one per endpoint, payload preserved
├── silver               (schema)  cleaned/flattened facts + SCD-2 dims + quarantine
└── gold                 (schema)  business marts (materialized views)
```

Free Edition provides a workspace catalog; if `f1` cannot be created, use `<workspace_catalog>.f1_bronze` / `_silver` / `_gold` schemas instead and keep every other name identical. Decide this at Step 1.1 and do not revisit.

### 0.4 Volume layout and idempotency ⚠️

```
/Volumes/f1/raw/landing/{endpoint}/season={season}/round={round}/{endpoint}_{season}_{round}_{ingest_ts}.json
```

Season-level endpoints omit the `round=` segment.

**The rule that makes this safe:**

- A round is **closed** once a later round exists in that season's race list *and* its results payload is non-empty. Closed rounds are written **once** and skipped on every later run (`if any file exists for this partition → skip`).
- The **latest** round of an in-progress season is re-pulled on each run and written with a fresh `ingest_ts`, because standings and results can be amended after the flag (penalties, appeals).
- Consequence: Bronze may hold multiple snapshots of the live round. **Silver must dedupe by natural key, keeping the row with the greatest `_ingest_ts`.** This is non-negotiable — without it, the live round double-counts.

Every file also carries an ingestion metadata envelope written by the notebook:

```json
{
  "_ingest_ts": "2026-08-06T12:00:00Z",
  "_source_url": "https://api.jolpi.ca/ergast/f1/2026/12/results/?limit=100&offset=0",
  "_season": "2026",
  "_round": "12",
  "_endpoint": "results",
  "payload": { "MRData": { ... } }
}
```

Wrapping the raw `MRData` rather than storing it bare is what makes Bronze auditable and Silver's dedupe possible.

### 0.5 SCD-2 design ⚠️ — the important one

**Do not run AUTO CDC over the raw `/drivers` and `/constructors` endpoints.** Their fields (`givenName`, `familyName`, `dateOfBirth`, `nationality`, `name`) never change, so the resulting dimension would contain no history rows at all and the SCD-2 requirement would be satisfied in form only.

**`dim_driver` (SCD-2)** — source: the *results* fact, one row per driver per round, carrying:
- Stable: `driver_id`, `code`, `permanent_number`, `given_name`, `family_name`, `dob`, `nationality`
- **Tracked (changes over time): `constructor_id`, `constructor_name`**
- Sequence key: `race_date`

This produces genuine version history wherever a driver changes team — including mid-season swaps, which exist in the 2024 backfill. Deduplicate to one row per `(driver_id, race_date)` before the CDC apply, and only emit a change record when the tracked columns actually differ from the prior round.

**`dim_constructor` (SCD-2)** — source: constructors endpoint enriched with a per-season `constructor_name`, sequenced by season. Teams rebrand between seasons, which gives this dimension real history too.

Both use `AUTO CDC INTO ... STORED AS SCD TYPE 2`.

### 0.6 Bronze read strategy

Auto Loader with `cloudFiles.format = "json"`, `multiLine = true`, `cloudFiles.inferColumnTypes = false` (everything lands as string), `rescuedDataColumn = "_rescued_data"`, plus `cloudFiles.schemaEvolutionMode = "addNewColumns"`.

Reasoning: the Ergast `MRData` shape differs per endpoint and nests irregularly. Inferring types at Bronze invites pipeline failures on schema drift mid-season. String-everything + rescue keeps Bronze append-only and faithful; all typing happens in Silver where it can be tested and quarantined. One Bronze streaming table per endpoint (7 tables).

### 0.7 Pipeline topology

**One** triggered Lakeflow Declarative Pipeline spanning all three schemas. Free Edition limits concurrent pipelines, and a single DAG gives a cleaner lineage graph for the demo. Development mode while building; production mode for the final scheduled run.

---

## 1. Phase 1 — Foundation (Day 1)

| Step | Task | Done when |
|---|---|---|
| 1.1 | Create catalog `f1` + schemas `raw`, `bronze`, `silver`, `gold`. Fall back to workspace-catalog schemas if blocked. | All four visible in Catalog Explorer |
| 1.2 | Create Volume `f1.raw.landing` | `/Volumes/f1/raw/landing` writable from a notebook |
| 1.3 | Initialise repo structure (below); connect workspace to Git via Databricks Repos | Notebooks version-controlled, not workspace-only |
| 1.4 | Record UC object names in `docs/conventions.md` | Naming frozen |

**Repo structure:**

```
formula1-capstone-project/
├── README.md
├── ACTION_PLAN.md
├── f1_capstone_prep.md
├── src/
│   ├── ingestion/
│   │   ├── jolpica_client.py        # HTTP, retry/backoff, pagination
│   │   ├── landing_writer.py        # volume paths, skip-if-closed logic
│   │   └── ingest_notebook.py       # job entry point
│   └── pipeline/
│       ├── bronze.py                # 7 Auto Loader streaming tables
│       ├── silver_facts.py          # flatten, type, dedupe, expectations
│       ├── silver_dims.py           # SCD-2 via AUTO CDC
│       ├── silver_quarantine.py     # rejected-row capture
│       └── gold.py                  # marts
├── sql/
│   ├── dq_event_log.sql             # DQ metrics from the pipeline event log
│   └── validation_checks.sql        # manual reconciliation queries
└── docs/
    ├── conventions.md
    ├── architecture.md              # diagram + lineage screenshot
    └── demo_script.md
```

---

## 2. Phase 2 — Ingestion (Days 1–2)

| Step | Task | Done when |
|---|---|---|
| 2.1 | `jolpica_client.py`: GET with `limit=100` pagination loop, exponential backoff on 429/5xx, ≤4 req/s throttle, hard cap on retries | Unit-testable; a deliberate 429 recovers |
| 2.2 | `landing_writer.py`: build volume paths, implement the skip-closed / repull-latest rule from §0.4, write the metadata envelope | Re-running the notebook twice adds **zero** new files for closed rounds |
| 2.3 | `ingest_notebook.py`: parameterised by `seasons` (list) and `mode` (`backfill` \| `incremental`) | Runs clean for both modes |
| 2.4 | Backfill 2024 + 2025 | ~200 files landed, `dbutils.fs.ls` count matches expected round count per endpoint |
| 2.5 | Backfill 2026 to date | Live season present |
| 2.6 | Create scheduled Job `f1_ingest_incremental`, weekly (Tuesday, post-race-weekend), serverless, `mode=incremental` | One successful scheduled run observed, not just a manual trigger |
| 2.7 | Log a per-run ingestion summary (files written, requests made, rounds skipped) | Printed in job output |

**Rate-limit guardrail:** the backfill must be run **once**. If it needs re-running, delete the affected partitions first rather than looping the API.

---

## 3. Phase 3 — Bronze (Day 2)

| Step | Task | Done when |
|---|---|---|
| 3.1 | Create the LDP `f1_medallion_pipeline`, development mode, target catalog `f1` | Pipeline created, empty run succeeds |
| 3.2 | 7 Bronze streaming tables via Auto Loader per §0.6, each carrying `_ingest_ts`, `_source_url`, `_season`, `_round`, `_endpoint`, `_file_path`, `_ingested_at` | All 7 populate; row counts equal file counts |
| 3.3 | Bronze expectations at **warn** level only: payload non-null, `_season` non-null, `_source_url` matches expected host | Warnings visible in event log; nothing dropped |

Bronze never drops a row. Its contract is: whatever the API returned, we still have it.

---

## 4. Phase 4 — Silver (Days 2–4) — the core of the project

### 4.1 Facts

One Silver streaming table per fact, each: explode nested `MRData` arrays → cast types → normalise ids → dedupe.

| Table | Grain | Notes |
|---|---|---|
| `silver.fact_result` | driver × race | grid, position, positionText, points, laps, status, fastest lap time/rank |
| `silver.fact_qualifying` | driver × race | Q1/Q2/Q3 times parsed to milliseconds, quali position |
| `silver.fact_driver_standing` | driver × round | cumulative points, wins, championship position |
| `silver.fact_constructor_standing` | constructor × round | cumulative points, wins, championship position |
| `silver.dim_race` | race | season, round, race_date, circuit_id, circuit_name, locality, country, lat/long |

**Dedupe pattern (required, per §0.4):**

```sql
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY season, round, driver_id
  ORDER BY _ingest_ts DESC
) = 1
```

### 4.2 Expectations and quarantine

Three tiers, applied consistently:

- `@expect` (warn) — soft signals: e.g. `points >= 0`, `status` in known set.
- `@expect_or_drop` — structural integrity: `driver_id IS NOT NULL`, `season IS NOT NULL`, `round IS NOT NULL`, `race_date IS NOT NULL`, `position IS NOT NULL OR position_text IS NOT NULL`.
- `@expect_or_fail` — reserved for one invariant that must never break: `season BETWEEN 1950 AND 2100`. Having exactly one fail-level expectation demonstrates you understand the difference; more than one makes the pipeline brittle.

**Quarantine:** for each fact, a companion `silver.quarantine_<fact>` table selecting rows that violate the drop rules, plus a `_quarantine_reason` column and `_quarantined_at`. Implement by branching from the same Bronze source with the inverse predicate — dropped rows are captured, not lost. This is a named MVP requirement; do not shortcut it.

### 4.3 SCD-2 dimensions

Per §0.5. `dim_driver` sequenced by `race_date` tracking `constructor_id`; `dim_constructor` sequenced by season.

**Acceptance test — run this and it must return rows:**

```sql
SELECT driver_id, constructor_id, __START_AT, __END_AT
FROM f1.silver.dim_driver
WHERE __END_AT IS NOT NULL
ORDER BY driver_id, __START_AT;
```

An empty result means the dimension has no history and item 3 of the MVP is **not** met.

---

## 5. Phase 5 — Gold (Day 4)

Materialized views, joined to the SCD-2 dimensions using the race date so historical rows attach to the *correct* team-of-the-time.

**`gold.driver_performance`** — grain: driver × race
`season, round, race_date, circuit_name, driver_id, driver_name, constructor_id (as-of), grid_position, finish_position, positions_gained, points, laps_completed, dnf_flag, status, fastest_lap_rank`

**`gold.championship_progression`** — grain: driver × round
`season, round, race_date, driver_id, driver_name, constructor_name (as-of), points_after_round, cumulative_points, championship_position, gap_to_leader, position_change_vs_prev_round`

Both are MVP-required. If time allows and only then:

**`gold.quali_vs_race`** (stretch-lite) — quali position vs finish position, delta, pole-to-win conversion. Cheap, since `fact_qualifying` already exists.

**Reconciliation check before declaring Gold done:** total points per driver in `gold.championship_progression` for the final round of 2024 must equal the published 2024 championship standings. If they don't match, the pipeline is wrong — find out why before building the dashboard. Put this query in `sql/validation_checks.sql`.

---

## 6. Phase 6 — Governance and DQ visibility (Day 5)

| Step | Task | Done when |
|---|---|---|
| 6.1 | Add table/column comments across Silver and Gold | Catalog Explorer reads as documentation |
| 6.2 | Screenshot the lineage graph: Volume → Bronze → Silver → Gold → Dashboard | Saved to `docs/architecture.md` |
| 6.3 | Write `sql/dq_event_log.sql` — query the pipeline event log for expectation pass/fail counts per table per run | Returns real numbers, including at least one non-zero failure |
| 6.4 | Create a Gold view exposing those DQ metrics so the dashboard can chart them | View queryable |
| 6.5 | Verify quarantine tables are non-empty (deliberately corrupt one landed file if needed, then reload) | Demonstrable evidence the pattern works |

Point 6.5 matters: a quarantine table with zero rows proves nothing. Manufacture one bad record so you can *show* it being caught.

---

## 7. Phase 7 — Dashboard (Day 5)

One AI/BI Dashboard page, reading **Gold only**:

1. Championship progression line chart — cumulative points by round, per driver, season filter
2. Driver performance table — avg finish, points, DNF rate, positions gained
3. Grid-vs-finish scatter — who gains places
4. Constructor points bar chart
5. Small DQ tile — rows processed vs rows quarantined per run (this is what separates a data-engineering capstone from a BI exercise)

Season and driver filters wired across the page.

If any dashboard tile references a Silver table, the layering claim is broken — fix the mart instead.

---

## 8. Phase 8 — Demo readiness (Day 5)

| Step | Task |
|---|---|
| 8.1 | Set the LDP to production mode; run a full end-to-end refresh from a clean state |
| 8.2 | Verify the scheduled ingestion Job has at least one successful automatic run in its history |
| 8.3 | Write `docs/demo_script.md` — the 5-minute walkthrough: problem → source → Volume → lineage graph → an expectation failing → quarantine table → SCD-2 history rows → Gold → dashboard |
| 8.4 | Commit everything; ensure notebooks are in Git, not just the workspace |
| 8.5 | Record the known limitations honestly: no tyre compound without FastF1, batch not streaming, Free Edition quotas |

---

## 9. Definition of done

The MVP is complete when **every one** of these is true:

- [ ] ≥2 complete seasons of raw JSON in the UC Volume, plus the in-progress season
- [ ] A scheduled Job with a successful *automatic* (not manual) run in its history
- [ ] Re-running ingestion produces zero duplicate files for closed rounds
- [ ] All 7 Bronze tables populated, row counts matching file counts
- [ ] All 5 Silver facts/dims populated, with warn + drop + one fail expectation each where applicable
- [ ] Quarantine tables exist and contain at least one demonstrable row
- [ ] `dim_driver` returns non-empty rows for `__END_AT IS NOT NULL`
- [ ] Both Gold marts built and reconciling against published 2024 standings
- [ ] Lineage graph renders end to end and is screenshotted
- [ ] DQ metrics queryable from the event log and surfaced on the dashboard
- [ ] Dashboard page reads Gold only

**Nothing from the stretch list is started until all eleven boxes are ticked.** That is the entire defence against the scope-creep risk named in the prep doc.

---

## 10. Risk register (build-time, not concept-level)

| Risk | Trigger | Mitigation |
|---|---|---|
| Free Edition compute shutoff | Long dev loops, repeated full refreshes | Develop against a single season; use `refresh selection` on individual tables rather than full-pipeline refreshes |
| Jolpica rate limit / outage | Backfill loops, re-runs | Backfill once; raw JSON cached in the Volume means every downstream re-run is free of the API |
| Auto Loader schema drift mid-build | New field appears in a 2026 payload | `inferColumnTypes=false` + `rescuedDataColumn` (§0.6) makes this a non-event |
| SCD-2 produces no history | Wrong source table | Addressed by §0.5; the acceptance query in §4.3 is the check |
| Live-round duplicates in Gold | Missing dedupe | The `QUALIFY` pattern in §4.1 is mandatory; reconciliation check in §5 catches it |
| Time lost to stretch goals | Curiosity | §9 gate |

---

## 11. Mapping to the prep doc's "next week, top 3"

| Prep doc item | Phases here |
|---|---|
| 1. Finalise ingestion | §0.1–0.4, Phase 2 |
| 2. Stand up the pipeline | Phases 3–4 |
| 3. Prove end-to-end | Phases 5–7 |

Phases 6 and 8 are the difference between "it works" and "it's assessable". Budget for them.

---

## 12. Open items needing your confirmation

1. **§0.1** — 2024 + 2025 backfill with 2026 live, or the original 2023 + 2024 static pair?
2. **§0.4** — agreed on skip-closed / repull-latest plus Silver dedupe as the idempotency contract?
3. **§0.5** — agreed that `dim_driver` is built from results (tracking constructor) rather than from the drivers endpoint?

Answer these three and Phase 1 can start immediately.
