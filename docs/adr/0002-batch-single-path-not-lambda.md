# 2. Batch, single path — not Lambda or Kappa

## Context

The pipeline architecture pattern had to be chosen explicitly. Formula 1 produces
data roughly 24 times a year, in bursts, hours after each race finishes. Results
are amended afterwards by stewards' decisions, sometimes days later.

## Decision

A single batch path. Not Lambda (batch and speed layers side by side), not Kappa
(everything as a stream).

Bronze uses streaming tables with Auto Loader for *incremental file discovery* —
that is not a streaming architecture, it is exactly-once file handling and
checkpointing without anyone polling a directory.

## Consequences

**Good.** One code path to reason about and one place a number can be wrong. The
latency target is hours, not seconds, and a race finishing means the dashboard is
correct by the next scheduled run.

**Good.** Amendment is handled properly rather than being a special case: the
whole design assumes a result is provisional when published.

**Bad.** Nothing here demonstrates stream processing. If the source ever became
live timing, the ingestion layer would need rewriting rather than extending.

## Alternatives considered

- **Lambda.** Rejected: maintaining a speed layer alongside the batch layer
  doubles the code that has to agree with itself, in exchange for latency nobody
  asked for on a source that updates 24 times a year.
- **Kappa.** Rejected: treating a post-session batch API as a stream is a
  costume, not an architecture.
