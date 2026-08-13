# F1 Race Intelligence Platform — Action Plan

**Architecture is the source of truth.** `docs/architecture.md` holds the design,
the decision record and the criteria coverage. This document holds only what is
*left to do*.

**Status:** MVP delivered. Ingestion, medallion pipeline, SCD-2 dimensions,
quarantine, two Gold marts, DQ event log and dashboard are all built and running.
The original MVP plan — locked decisions, phase breakdown, definition of done —
is preserved in this file's git history.

---

## Part 1 — What is already delivered

| | |
|---|---|
| Ingestion | 8 endpoints, throttled, retried, idempotent, backfill + incremental modes |
| Landing | `f1.raw.landing` Volume, partitioned by endpoint/season/round, provenance envelope |
| Bronze | 8 Auto Loader streaming tables, warn-level expectations, nothing dropped |
| Silver | 5 facts, 3 dimensions (2 × SCD-2 via Auto CDC), 6 quarantine tables |
| Gold | `driver_performance`, `championship_progression`, clustered by season/round |
| Orchestration | `f1_ingest_incremental` job, ingest → pipeline, scheduled, paused in dev |
| DQ visibility | Pipeline event log published to Gold, `dq_event_log.sql`, `validation_checks.sql` |
| Dashboard | AI/BI, reads Gold only |

Reconciliation holds: 2024 championship totals from `championship_progression`
match the published standings, sprint points included.

---

## Part 2 — What is left

Four workstreams. **A is independent and short; B is the substance; C is
mechanical; D is optional.** A does not depend on B, so it can go first.

### A. Close the failing criterion — unit tests

The technical-execution criteria require *"at least one unit test for your
transformation logic"*. There is currently no test suite. This is the only hard
miss, and it is the cheapest to fix.

| Step | Task | Done when |
|---|---|---|
| A1 | Add `tests/`, `pytest.ini`, dev requirements | `pytest` runs and collects |
| A2 | Test `landing_writer.should_write` — closed round skipped, live round re-pulled, first round of a season | Three cases pass, no Spark session needed |
| A3 | Test the race-calendar parse — round → date, lat, long; malformed entry skipped not crashed | Passes against a committed sample payload |
| A4 | Test `scripts/check_expectations.py`'s own AST walk against a fixture with a deliberately stale column name | Detects it |

Nothing here needs a cluster. If a test needs Spark, the logic is in the wrong
place — move it out of the pipeline file into an importable module.

### B. Weather, laps, pit stops, circuits

Four new endpoints. **Land everything first, then extend the medallion** —
nothing reads an API after the Volume.

| Step | Task | Done when |
|---|---|---|
| B1 | `config.py`: Open-Meteo URL, `WET_THRESHOLD_MM = 1.0`, `ARCHIVE_LAG_DAYS = 5`, four new entries in `ENDPOINT_SHAPE` | Constants in one place |
| B2 | `weather.py`: one archive call per race, reusing the throttle and backoff from `jolpica_client` | Returns precipitation, temp min/max, wind for a known race |
| B3 | `ingest.py`: carry `lat`/`long` out of the calendar parse; write `weather`, `circuits`, `pitstops`, `laps` partitions | Files land in the Volume; a re-run adds none for closed rounds |
| B4 | **Verify landing before touching the pipeline** — file counts per endpoint per season | Counts match expected rounds |
| B5 | Bronze: add the four endpoints to `ENDPOINTS`; make `expected_source` per-endpoint so Open-Meteo does not fail Jolpica's host check | 12 Bronze tables populate |
| B6 | Silver: `fact_race_weather`, `fact_pit_stop`, `fact_lap`, `dim_circuit`, each with expectations and a quarantine companion | 8 facts, 4 dims |
| B7 | Gold: `race_conditions`, `race_strategy`, `lap_pace` | 5 marts, clustered |
| B8 | Dashboard tiles over the new marts | Rainfall vs retirements, stint spread, pace by stint |

**Ordering constraint — one only:** `races` must be fetched before `weather`,
because the coordinates come from it. Everything else is independent.

**Cost warning:** `laps` is paginated at roughly 12 calls per round — about 850
calls against ~120 for everything else combined, and roughly 85,000 rows. Give
it its own task so a lap failure does not block the rest, and make sure it
respects the closed-round skip.

**ERA5 lags ~5 days.** Recent and future races return nothing. That must land as
*absent*, never zero — a race with no observation is not a dry race.

### C. Convert to the notebook-source format

Cell separators give interactive output; the files stay plain `.py` and stay
importable.

| Step | Task |
|---|---|
| C1 | Add `# Databricks notebook source` + `# COMMAND ----------` to the four pipeline files |
| C2 | Move `ingest.py` to a thin entry-point notebook that imports `src/ingestion/` and prints the run summary |
| C3 | New `validation.py` notebook running `validation_checks.sql` and `dq_event_log.sql` with visible output |

**Library modules stay plain `.py`** — `config`, `jolpica_client`,
`landing_writer`, `weather`. That is what keeps workstream A possible: a
notebook orchestrates, a module computes.

### D. Optional — the two partials

| Step | Task | Why it is optional |
|---|---|---|
| D1 | Metric-definition views over Gold | Metrics are already defined once, in mart columns. Worth it only if the mart set grows. |
| D2 | Alert on failed runs or quarantine count > 0 | Failures are visible in run history and the event log; nothing pages anyone today. |

---

## Part 3 — Suggested order

```
A (tests)  →  B1–B4 (land everything)  →  verify  →  B5–B7 (medallion)  →  B8 (dashboard)
                                                        ↑
                                             C can happen any time
```

A first because the criterion is open now and closing it depends on nothing.
B4 is a real gate: confirm files are in the Volume before spending pipeline
compute on them.

---

## Part 4 — Risks

| Risk | Trigger | Mitigation |
|---|---|---|
| Free Edition daily compute quota | Repeated full refreshes while iterating on Silver | Selective refresh on single tables; never full-refresh to test one expectation |
| `laps` blows the rate limit | Backfilling three seasons in one pass | Its own task, closed-round skip honoured, 2 req/s throttle |
| Weather renders as 0.0 mm | Treating a missing ERA5 observation as dry | `weather_available` flag; the mart must say "no data" |
| Bronze host expectation fails | Open-Meteo added without touching `expected_source` | B5 covers it explicitly |
| Changing a dataset type in place | Silver facts move from materialized view to streaming table | **Cannot be done in place, and a full refresh does not help.** Drop the table manually or rename the dataset |
| Logic drifts into notebooks | Convenience during C | Anything worth asserting on lives in a module |

---

## Part 5 — Definition of done for Part 2

- [ ] `pytest` runs green with at least three meaningful transformation tests
- [ ] 12 endpoints landing; a re-run adds zero files for closed rounds
- [ ] 12 Bronze tables populated, row counts matching file counts
- [ ] `fact_race_weather` distinguishes "no observation" from "no rain"
- [ ] 5 Gold marts built and clustered
- [ ] Dashboard answers *was it the weather*, *was it the pit wall*, *who was actually fast*
- [ ] `table_changes()` on `fact_result` returns a real amendment
- [ ] `docs/architecture.md` updated — status legend flipped from PLANNED to built