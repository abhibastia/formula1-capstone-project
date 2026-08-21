# 5. SCD-2 dimensions built from results, not `/drivers`

## Context

The criteria require change data capture, and a driver dimension is the obvious
place for SCD Type 2. Jolpica has a `/drivers` endpoint that returns exactly what
a dimension wants: id, name, code, nationality, date of birth.

Every one of those fields is static. Auto CDC Type 2 over `/drivers` produces a
dimension with one version per driver and **no history at all** — the pattern
implemented, the criterion technically claimed, and nothing actually captured.

## Decision

Build `dim_driver` from the **results** endpoint, sequenced by `race_date`. The
attribute that changes is the driver's constructor, and it exists only in
results.

## Consequences

**Good.** The dimension has real history: 42 versions across 28 drivers, 14 of
them historical. Mid-season team changes are preserved, which is what makes the
as-of-race join in Gold meaningful (ADR 0006).

**Good.** It is verifiable. A dimension whose row count equals its distinct key
count has no history, and that comparison is now a documented check.

**Bad.** `dim_driver` depends on the results feed, so a driver who never starts a
race never appears. For this platform that is correct — a driver with no results
has nothing to attribute.

**Bad.** It is more code than reading `/drivers`, and the reason is not obvious
from the code alone. Hence this record, and a standing note in `CLAUDE.md`
warning against "simplifying" it back.

## Alternatives considered

- **`/drivers` with Auto CDC Type 2.** Rejected: zero history rows, which is
  worse than not implementing the pattern because it looks like it works.
- **Type 1 dimensions plus a separate history table.** Rejected: hand-rolling
  what Auto CDC already does correctly.
