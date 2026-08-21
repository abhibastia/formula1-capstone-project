# 5-minute demo script

Order matters: lead with the problem, end with the dashboard. The middle four
beats are the ones that separate this from a BI exercise — show the pipeline
catching something, not just producing something.

---

**1. The problem (30s)**

F1 performance data is fragmented across inconsistent public APIs with no
lineage and no quality guarantees. There is no single trusted, queryable view, so
a season-long comparison can be silently corrupted by one wrong value. The user
is a retrospective race-strategy analyst building priors for the next race.

**2. Source and ingestion (45s)**

Open the Volume `f1.raw.landing`. Show the `endpoint / season= / round=` layout
and one raw file — point out the ingestion envelope (`_ingest_ts`, `_source_url`)
wrapping the untouched `MRData`.

> Say: "Raw JSON is cached here, so every downstream re-run is free of the API.
> Re-running ingestion makes eight calls instead of two hundred and sixty,
> because closed rounds are skipped and only the live round is re-pulled."

**3. The pipeline and lineage (45s)**

Open the pipeline DAG, then the Unity Catalog lineage graph: Volume → 11 Bronze
→ 8 Silver facts and 3 dimensions → 6 Gold marts and a metric view → one
dashboard of six decision pages, plus a Genie agent. One pipeline, three schemas.

**4. Data quality — show it catching something (60s)** ← *the important beat*

Run query 1 in `sql/dq_event_log.sql`: expectation pass/fail counts per dataset
per run. Then open `f1.silver.quarantine_result` and show a captured row with its
`_quarantine_reason`.

> Say: "Rows that fail structural rules are dropped from the fact *and* routed to
> a quarantine table with the reason attached, so nothing is silently lost."

If quarantine is empty, corrupt one landed file and re-run beforehand — an empty
quarantine table proves nothing.

**5. SCD-2 history (45s)**

Run check 2 in `sql/validation_checks.sql`:

```sql
SELECT driver_id, constructor_name, __START_AT, __END_AT
FROM f1.silver.dim_driver WHERE __END_AT IS NOT NULL;
```

Show Lawson: RB → Red Bull → RB across 2025.

> Say: "This is why the dimension is built from results rather than the drivers
> endpoint. Every field the drivers endpoint returns is static, so Auto CDC over
> it would give twenty-eight rows and zero history — the pattern implemented but
> never exercised. Driver-to-constructor is what actually changes."

**6. Correctness (45s)**

Run checks 1 and 14 — the two reconciliations. Zero rows each.

> Say: "Each compares two independent endpoints against each other. Points summed
> from race and sprint results versus the driver standings endpoint; and the same
> again for constructors. They agree exactly. That also caught a real bug — race
> points alone leave thirteen of twenty-four drivers short, because sprint races
> award championship points."

**7. The semantic layer (30s)**

One query against `f1.gold.driver_metrics`, then change `` `Team` `` to
`` `Driver` `` and rerun.

> Say: "Same definition, different grain, both correct. A standard view fixes its
> aggregation at creation, so averaging Ferrari's three drivers gives 11.1 points
> per start when the answer is 13.6 — Bearman's single substitute appearance
> counting as much as Leclerc's season."

**8. The dashboard (45s)**

Six pages, one per analyst decision: Standings, Driver Form, Constructor
Benchmarking, Circuit Priors, Championship Swing, Trust.

> Close on: "Pages are named after the question, not the table underneath. Every
> tile reads Gold only, and the Trust page is the pipeline reporting on its own
> health — expectations passed and failed, per dataset, per run."

---

## Questions to expect

**"Why not streaming?"** The source is public and post-session; there is nothing
to stream. The triggered design is deliberate. Near-real-time via OpenF1 is a
staged stretch, not a dependency.

**"Where's the tyre strategy?"** Pit and stint analysis is possible from
Jolpica's laps/pitstops endpoints. Tyre compound per stint is not reliably in
Jolpica — that specific field is why FastF1 is on the roadmap. Worth saying
plainly rather than implying the strategy mart is complete.

**"What would you do next?"** In order: FastF1 for tyre compound, then Databricks
Asset Bundles and CI, then the ML layer. Not the other way round — the pipeline
had to be solid first.
