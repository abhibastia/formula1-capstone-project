# 9. The Genie agent is scoped to Gold only

## Context

Genie translates a natural-language question into SQL and runs it. Given access
to the whole catalog it will answer questions about Silver and Bronze too, and
those answers will look exactly as confident as the correct ones.

The specific failure is not hypothetical. `fact_result` carries
`constructor_name` as reported at the time, while Gold carries
`constructor_name_as_of_race` from the SCD-2 join. An agent reading Silver can
attribute a driver's whole season to their current team — plausible, well
formatted, and wrong.

## Decision

The agent's `data_sources` list contains exactly the six Gold marts plus the
`driver_metrics` metric view over them. Not Silver, not Bronze, not the landing
Volume. It carries seven certified SQL examples — each executed against the
warehouse before being committed — and one instruction block encoding the rules
that change answers.

## Consequences

**Good.** Scope is the correctness control. The marts already resolve the
as-of-race join and pre-compute `total_points`, so the agent cannot get those
wrong by construction rather than by instruction.

**Good.** It reuses the grant model instead of bypassing it: queries run as the
asker, so reaching the agent grants no access to Bronze.

**Good.** The scope is enforced by test, not by discipline — `tests/test_genie_space.py`
fails if a Silver table is added, if the two `agent_*` tables from a separate
project are picked up, or if anything gains `WRITE_VOLUME`.

**Bad.** Questions that genuinely need lap-level detail — "how many laps did he
lead in the wet" — cannot be answered, because `fact_lap` is out of scope and
`lap_pace` is aggregated to driver × race. Widening it is a deliberate edit with
a test to update, which is the intent.

## Alternatives considered

- **Whole-catalog access.** Rejected: the wrong-team failure mode above, with no
  signal that anything is wrong.
- **Gold plus Silver facts.** Rejected for now: it re-opens the as-of-race
  question for a small gain in answerable questions.
