# 6. Gold is wide marts with dimensions joined as-of race date

## Context

Silver holds a conformed star: `dim_driver`, `dim_constructor` and `dim_race`
around six facts. The serving layer had to choose a paradigm — expose the star
directly, or denormalise.

The access pattern is a dashboard tile asking "points by constructor for season
X" and a Genie agent generating SQL from a question. Both would otherwise pay for
a five-way join on every query, and the Genie agent would have to get the join
right unaided.

## Decision

Gold is six wide marts — one big table per question — clustered by
`(season, round)`. Dimensions are joined **as of the race date**:

```sql
LEFT JOIN dim_driver d
       ON d.driver_id = f.driver_id
      AND f.race_date >= d.__START_AT
      AND (d.__END_AT IS NULL OR f.race_date < d.__END_AT)
```

## Consequences

**Good.** A driver who changed teams mid-season has each result attributed to the
team they actually drove for that weekend. A current-row join would silently
reattribute a season of points to whoever they drive for now — and the number
would still look plausible, which is what makes it dangerous.

**Good.** Metric definitions live in mart columns, so a tile counting wins and a
tile ranking drivers count the same thing by construction.

**Good.** It is what makes the Genie agent safe to scope to Gold (ADR 0009): the
joins are already resolved.

**Bad.** The marts are wide and duplicate dimension attributes. At three seasons
and ~1,200 results that costs nothing; at a hundred times the size it would need
revisiting.

**Bad.** There is still no metric-view layer — the mart columns *are* the
semantic layer. That is adequate at this scale and named as a gap in
`architecture.md`.

## Alternatives considered

- **Expose the Silver star directly.** Rejected: pushes the as-of join onto every
  consumer, and the one consumer that generates its own SQL would get it wrong.
- **Snowflake schema in Gold.** Rejected: more joins for a read-mostly workload
  with no update anomaly to protect against.
