# Architecture Decision Records

One file per decision that was expensive to make and would be expensive to
reverse. Each records the context at the time, the decision, and what it cost —
including the decisions that turned out to be wrong.

These were extracted from `docs/architecture.md`, which remains the narrative
design document. The split: architecture.md explains **how the platform works**;
these explain **why it is that way, and what else was on the table**.

| # | Decision | Status |
|---|---|---|
| [0001](0001-databricks-free-edition-as-the-whole-platform.md) | Databricks Free Edition as the entire platform | Accepted |
| [0002](0002-batch-single-path-not-lambda.md) | Batch, single path — not Lambda or Kappa | Accepted |
| [0003](0003-bronze-reads-files-as-text.md) | Bronze reads files as text, not JSON | Accepted |
| [0004](0004-silver-facts-are-materialised-views.md) | Silver facts are materialised views, not Auto CDC streaming tables | Accepted |
| [0005](0005-scd2-built-from-results-not-drivers.md) | SCD-2 dimensions built from results, not `/drivers` | Accepted |
| [0006](0006-gold-is-wide-marts-joined-as-of-race-date.md) | Gold is wide marts with dimensions joined as-of race date | Accepted |
| [0007](0007-the-bundle-does-not-own-the-catalog.md) | The bundle owns the pipeline and jobs, not the catalog | Accepted |
| [0008](0008-change-data-feed-is-not-enabled.md) | Change Data Feed is not enabled | Accepted |
| [0009](0009-genie-agent-is-scoped-to-gold.md) | The Genie agent is scoped to Gold only | Accepted |
| [0010](0010-no-containerisation.md) | No containerisation | Accepted |

Format: context, decision, consequences, alternatives considered. A decision that
was later corrected says so in its own file rather than being edited into
looking right.
