# 8. Change Data Feed is not enabled

## Context

Because results are provisional, the most distinctive question this dataset could
answer is "*which classifications were revised after publication, and by how
many places*". Change Data Feed and `table_changes()` are the mechanism for
exposing that to consumers.

This decision was recorded wrongly twice, which is why it is stated carefully
here.

1. The architecture document originally described CDF as **enabled** on
   `fact_result` and the Gold marts, and scored the criterion as met. It never
   was — `delta.enableChangeDataFeed` appears nowhere in `src/`.
2. The correction then said enabling it was "one table property on the Silver
   facts and the Gold marts". Also wrong.

## Decision

Do not enable Change Data Feed, because on the datasets where it would matter it
**cannot** be enabled. Measured in this workspace:

| Dataset type | Ours | `table_changes()` |
|---|---|---|
| Materialised view | 8 Silver facts, 6 Gold marts | `MATERIALIZED_VIEW_UNSUPPORTED_OPERATION — Operation CHANGE DATA FEED is currently not supported on Materialized Views` |
| Streaming table | 11 Bronze, both SCD-2 dimensions | Already enabled by Lakeflow — `delta.enableChangeDataFeed = true` |

`table_changes('f1.silver.dim_driver', 2)` returns 42 rows today. Reading from
version 0 fails on `deletedFileRetentionDuration` (168 hours), which is a
retention limit, not a CDF one.

## Consequences

**Good.** No cargo-cult table property. CDF was never needed for incremental
processing — Lakeflow already does that — and enabling it for internal plumbing
would have been decoration.

**Bad.** Amendment history on the facts is genuinely unavailable, and the
criterion "change tracking for consumers" is Partial rather than Met.

**Neutral.** Getting it would mean converting the Silver facts from materialised
views to streaming tables and rebuilding the deduplication as an Auto CDC flow —
reversing ADR 0004 and losing the `_file_path` tiebreak. That is an architectural
trade, not a checkbox, and it is not worth making to satisfy a criterion.

**Available instead.** SCD Type 2 on the dimensions is real change tracking that
exists and is queryable: 42 driver versions with `__START_AT` / `__END_AT`, and
it is what powers the as-of-race join in ADR 0006.

## Alternatives considered

- **Set the property on the marts anyway.** Rejected: unsupported, and a
  reassuring line of code that buys nothing is worse than an admitted gap.
- **Convert the Silver facts to streaming tables.** Rejected for now; see ADR
  0004 for what the dedupe requires.
