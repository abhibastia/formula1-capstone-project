# Capstone Project – Week 1 Preparation
### Formula 1 Race Intelligence & Strategy Platform

> **Focus:** the data pipeline. Dashboards, ML, and advanced analytics are extensions. The MVP is a complete, well-designed pipeline. Built entirely on **Databricks Free Edition** — no external cloud.

---

## 1. Project Overview

**What domain have you chosen?**
Sports — motorsport / Formula 1.

**What is your project in one or two sentences? (non-technical)**
A platform that automatically collects Formula 1 race data from public sources and turns it into clean, reliable, up-to-date insight about drivers, teams, and race strategy — instead of scattered, inconsistent spreadsheets and raw API responses.

**Who would use this pipeline?**
Race analysts and strategists (the primary analytical persona); F1 media/content creators benchmarking driver and team performance; data analysts and fans who want a trustworthy, queryable view of the championship. Concretely: me, as a data-engineering portfolio piece.

**What problem does your pipeline solve? (business need)**
There is no single trusted, current, queryable view of F1 performance. The data exists but is fragmented across inconsistent public APIs and formats, with no lineage and no quality guarantees — so a season-long comparison or a strategy readout can be silently corrupted by one wrong or missing value. Teams and analysts need one governed, up-to-date place to answer questions like *"how did tyre strategy differ across this circuit over three seasons?"* without re-parsing raw JSON every time.

---

## 2. Data

**What data source(s) are you planning to use?**

| Source | Link | Content |
|---|---|---|
| **Jolpica-F1** (Ergast successor) — *MVP backbone* | `https://api.jolpi.ca/ergast/f1` | Races, results, qualifying, driver & constructor standings, drivers, constructors, laps, pit stops |
| FastF1 *(stretch)* | `https://docs.fastf1.dev` | Telemetry, lap/sector timing, tyre data |
| OpenF1 *(stretch)* | `https://openf1.org` | Session events & positions |
| Weather API *(stretch)* | — | Race-day weather |

**What type of data is it?**
API (REST / JSON). FastF1 is a cached Python library. No CSVs, no database source, no true streaming.

**Is the data updated regularly, or is it static?**
Updated — after each race weekend (historical otherwise). Not real-time for the core data. OpenF1 is near-real-time-ish during live sessions, but that's used only for a simulated incremental demo (stretch).

**Have you already verified that you can access the data?**
✅ Yes — successfully ingested Jolpica **2024 Round 1** into storage. FastF1 / OpenF1 / weather are not yet wired in (stretch).

**Are there any limitations?**
- Jolpica rate limits: 4 req/s burst, 500 req/hr sustained; responses are paginated.
- Jolpica is community-maintained → some stability risk.
- Nested / irregular Ergast `MRData` JSON shape to flatten.
- FastF1 payloads are heavier and need caching.
- No authentication required (all public).
- Databricks Free Edition fair-use compute quotas.

---

## 3. Pipeline Design (start to finish)

```
Public F1 APIs (Jolpica → MVP)
        ↓
Scheduled Databricks Job  — Python notebook calls the API (rate-limited, retried); no AWS
        ↓
Unity Catalog Volume  — raw JSON landing zone (season / round / endpoint)
        ↓
Auto Loader (cloudFiles) — incremental file pickup
        ↓
Single triggered Lakeflow Declarative Pipeline
   • Bronze streaming tables (raw)            → expectations: warn
   • Silver streaming tables (clean/flattened) → expect_or_drop + quarantine; SCD-2 dims via AUTO CDC
   • Gold materialized views (business-ready marts)
        ↓
AI/BI Dashboard  +  Genie space (NL Q&A over Gold)

Cross-cutting: Unity Catalog — governance, lineage, event-log DQ metrics
```

- **Where does the data come from?** Public F1 REST APIs (Jolpica for the MVP).
- **How will it be ingested?** A scheduled Databricks Job runs a Python notebook that calls the API and writes raw JSON directly into a Unity Catalog Volume. No AWS, no external storage.
- **What transformations are required?** Bronze: raw capture. Silver: flatten nested `MRData`, type-cast, deduplicate, normalize driver/constructor/circuit references, quarantine bad rows, SCD-2 on `dim_driver`/`dim_constructor`. Gold: aggregate into business-ready marts.
- **Where will the processed data be stored?** Databricks-managed Delta tables, governed by Unity Catalog in `bronze` / `silver` / `gold` schemas.
- **What is the final output?** Gold marts (driver performance, constructor analytics, championship progression, race strategy) surfaced through an AI/BI Dashboard and a Genie natural-language space.

---

## 4. Technology Choices (with rationale)

| Technology | Why |
|---|---|
| **Databricks Free Edition** | Free, serverless, real Lakehouse; the project's goal is Databricks depth |
| **Python & SQL** | API ingestion + transformations and marts |
| **Unity Catalog Volume** | Managed, governed file landing zone; no external location needed (the Free Edition-correct choice) |
| **Databricks Job (scheduled)** | Serverless ingestion; replaces AWS Lambda/EventBridge — one platform, no cloud account |
| **Auto Loader** | Incremental file processing + checkpointing without an always-on stream |
| **Lakeflow Declarative Pipeline (triggered)** | Declarative medallion, built-in expectations, lineage; runs batch |
| **Delta Lake** | Reliable lakehouse table format with time travel |
| **Unity Catalog** | Lineage, access control, schema management, audit |
| **AI/BI Dashboards + Genie** | Reporting + natural-language analytics over Gold |

*Deferred to stretch:* Great Expectations, SQL Alerts, Lakebase, Databricks Apps, DABs, GitHub Actions, MLflow, Vector Search, Mosaic AI.

---

## 5. Scope

**Minimum Viable Product (must work):**
1. Scheduled ingestion Job pulls the core Jolpica endpoints for ≥2 seasons and lands raw JSON in a UC Volume.
2. Single triggered LDP with Bronze → Silver for the core entities (results, standings, races, drivers, constructors), including expectations and the quarantine pattern.
3. SCD-2 dimensions (`dim_driver`, `dim_constructor`) via AUTO CDC.
4. At least two Gold marts (e.g. driver performance + championship progression).
5. Unity Catalog governing all schemas, with lineage visible and DQ metrics queryable from the event log.
6. One AI/BI Dashboard page reading Gold, proving the data is decision-ready end to end.

**Stretch goals (staged, once the MVP is done):**
- **Ingestion & DQ hardening** — FastF1/OpenF1/weather sources; a Great Expectations validation job; SQL Alerts (DQ, freshness/SLA, domain thresholds).
- **Simulated near-real-time** — the same triggered LDP on a tighter schedule polling OpenF1.
- **Serving & product layer** — sync Gold to **Lakebase**, build a **Databricks App**, and expand the **Genie** space *(pattern already built on Free Edition via an internal ticketing platform)*.
- **IaC & CI/CD** — package as **Databricks Asset Bundles** and deploy via **GitHub Actions** (OAuth M2M).
- **MLOps / MLflow** — Gold feature tables → a **race-winner predictor** with MLflow tracking, Model Registry, and batch inference; then tyre-degradation and pit-stop optimization.
- **GenAI** — Vector Search + a **Mosaic AI "Race Engineer" agent** answering hybrid questions over FIA regulations and Gold-table figures.

*Portfolio goal: one coherent F1 use case demonstrating the full Databricks stack — DE → governance → BI → serving/apps → MLOps → GenAI.*

---

## 6. Risks

**What is the biggest risk?**
Scope creep — the ML/RAG ambitions pulling focus before the core pipeline is solid — compounded by Databricks Free Edition quotas and limits.

**How will you reduce it?**
- **Strict MVP-first.** Every advanced item is explicitly staged as stretch; nothing beyond the six MVP items is required for success.
- **Free Edition quotas** (fair-use daily/monthly shutoff): keep schedules modest, use small bounded datasets, develop in short runs.
- **One active pipeline per type:** consolidate Bronze/Silver/Gold into a single LDP spanning three schemas (cleaner anyway).
- **API rate limits / community-API instability:** retry + exponential back-off (already implemented); cache raw JSON in the Volume so re-runs don't re-hit the API; pin to specific seasons.
- **Nested/irregular JSON:** Bronze stores raw; flattening and typing isolated in Silver with `expect_or_drop` + quarantine.
- **No real streaming source:** the batch/triggered design is deliberate; near-real-time is a simulated stretch demo, not a dependency.

---

## 7. Plan for Next Week (top 3)

1. **Finalise ingestion** — lock the Jolpica endpoint set, repoint the ingestion notebook to a UC Volume, and land ≥2 seasons via a scheduled Job.
2. **Stand up the pipeline** — a single triggered LDP with Bronze + Silver for the core entities, including expectations and the quarantine pattern.
3. **Prove end-to-end** — build the first Gold mart (driver/constructor standings + championship progression) and a basic AI/BI dashboard page on top of it.

---

## Before the Meeting — 5-minute explanation

**Why does this pipeline need to exist?**
F1 performance data is fragmented across inconsistent public APIs with no quality guarantees or lineage, so there's no single trusted, current, queryable view. This pipeline creates one governed place to analyze driver, team, and strategy performance reliably.

**Where does the data come from?**
Public F1 REST APIs — Jolpica-F1 (the Ergast successor) for the MVP backbone (races, results, standings, drivers, constructors), with FastF1, OpenF1, and weather as later additions.

**What does your pipeline look like from start to finish?**
A scheduled Databricks Job pulls the API into a Unity Catalog Volume → Auto Loader → a single triggered Lakeflow Declarative Pipeline (Bronze → Silver → Gold, with expectations, a quarantine pattern, and SCD-2 dimensions) → Gold marts → an AI/BI Dashboard and a Genie space. Everything runs on Databricks Free Edition with no external cloud.

**What is your MVP?**
A complete, governed batch pipeline: ingestion → medallion with data quality → at least two Gold marts → one dashboard, all governed by Unity Catalog.

**What do you plan to complete before next week's meeting?**
The three items above — finalise ingestion into a Volume, stand up the Bronze → Silver LDP, and prove end-to-end with a first Gold mart plus a basic dashboard page.


Good — these are the two questions that most sharpen a data project, so worth answering precisely rather than hand-waving.

## Primary user and the decisions they make

what the *data* supports: it's public and post-session, so the primary user is **not** a live race strategist making pit calls on the pit wall (that needs private real-time telemetry you don't have). Your primary user is a **race strategy / performance analyst working retrospectively** — someone at a team's factory, a media/broadcast analytics desk, or an independent analyst — who studies *what happened* to build priors for *what to do next*.

Concretely, they're making decisions like:
- **Strategy priors per circuit** — did one-stop or two-stop win here historically? Does track position or tyre life dominate? This informs the strategy playbook for the next visit.
- **Driver form and deployment** — who is over- or under-performing their machinery, trending up or down across the season, strong in qualifying but losing places on Sunday (or vice versa)?
- **Constructor benchmarking** — where are points actually won and lost — qualifying pace, race pace, pit-stop execution, reliability?
- **Where the championship turned** — which rounds swung the title fight, and why.

That single persona is clean and defensible. I'd then name two **secondary** users the same Gold marts serve for free, because it strengthens the "who uses it" answer without diluting the primary: **F1 media/content creators** (benchmarking numbers for articles and video) and **F1 Fantasy players** (driver/constructor value, form, consistency, upcoming-circuit history). Pick the analyst as primary; mention the other two as beneficiaries.

## 2. Core Gold-layer datasets and metrics

Underneath everything sit the **conformed dimensions** your marts join to — `dim_driver` and `dim_constructor` (both SCD-2, so mid-season team changes are preserved), plus `dim_circuit` and a race/date dimension. The marts themselves:

**MVP marts** (all buildable from Jolpica results / standings / qualifying — no laps or pit stops needed):

- **`gold_driver_performance`** — grain: driver × race. Grid position, finish position, positions gained/lost, points, fastest-lap flag, laps completed, DNF flag, status. This is your benchmarking backbone.
- **`gold_constructor_performance`** — grain: constructor × race, with a season rollup. Points, wins, podiums, average finish, double-points finishes, DNF/reliability rate, best/worst result.
- **`gold_championship_progression`** — grain: driver/constructor × round. Cumulative points, championship position by round, gap to leader, round-over-round position change. This is what drives the standings/points-progression dashboard page.
- **`gold_quali_vs_race`** — grain: driver × race. Qualifying position, Q1/Q2/Q3 progression, race finish, quali-to-finish delta, pole-to-win conversion. A genuinely useful signal (who makes up places, who goes backwards) and cheap to build.

Start your MVP with **`gold_driver_performance` + `gold_championship_progression`** — they satisfy the "≥2 Gold marts" bar and directly feed one dashboard page.

**Stretch marts** (need per-round laps/pit stops, and tyre compound in particular):

- **`gold_race_strategy`** — grain: driver × race × stint. Pit-stop count, stint count and length, pit-stop duration, average lap time per stint, undercut/overcut indicators. This is the headline "strategy" mart. ⚠️ One honesty flag for the meeting: pit-stop counts, timing, and stint lengths come from Jolpica's laps/pitstops endpoints, but **tyre compound per stint isn't reliably in Jolpica** — that's the specific field that pulls in **FastF1**. So "pit and stint analysis" is Jolpica-only; "tyre-compound strategy" is the reason FastF1 is on the roadmap.
- **`gold_circuit_profile`** — grain: circuit (× season). Typical winning strategy, average stops per race, a position-change/overtaking index, pole-to-win conversion at that circuit. The "what usually works here" mart that turns retrospective data into forward-looking priors.

A clean way to state the metric philosophy : the Gold layer exposes **performance** (points, positions, form), **execution** (qualifying delta, pit/stint efficiency, reliability), and **context** (circuit and championship-state) — so every number an analyst pulls is already benchmarked against field and circuit norms rather than sitting in isolation.


