# 4. Silver facts are materialised views, not Auto CDC streaming tables

Date: 2026-08-07
Status: Accepted

## Context

A Formula 1 result is provisional when published: stewards apply penalties after
the flag, a disqualification removes a car, and Jolpica reissues the payload.
Ingestion also re-pulls the open round on every run by design. Both mean several
landed files describe the same round, and the newest must win.

Auto CDC with `stored_as_scd_type = 1` is the idiomatic Lakeflow answer and was
the original implementation.

## Decision

Silver facts are **materialised views** that deduplicate with a window function:

```python
window = Window.partitionBy("season", "round", "driver_id").orderBy(
    F.col("_ingest_ts").desc(), F.col("_file_path").desc()
)
```

Auto CDC is retained for the **dimensions**, where SCD Type 2 is the requirement.

## Consequences

**Good.** The `_file_path` tiebreak handles two files carrying the same
`_ingest_ts`, which a single `sequence_by` column cannot express.

**Good.** Materialised views recompute when an upstream row is amended.
Streaming tables would not, and amendment is the case this project is about.

**Bad — and this is the significant one.** Change Data Feed is unsupported on
materialised views, so `table_changes()` can never answer "what did the stewards
change" for the facts. See ADR 0008.

**Bad.** The dimensions must read Bronze directly rather than the fact MVs,
because Auto CDC requires a streaming source and a materialised view cannot be
streamed from. The dependency graph is wider than it looks.

## Alternatives considered

- **Auto CDC Type 1 on the facts.** Rejected on the tiebreak, and it would have
  made the CDF question moot — worth noting that the rejected option was better
  on that one axis.
- **Streaming tables with a dedupe in the query.** Rejected: a full-partition
  window function cannot be expressed in streaming append mode.
