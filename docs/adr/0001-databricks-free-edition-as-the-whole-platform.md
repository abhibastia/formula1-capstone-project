# 1. Databricks Free Edition as the entire platform

Date: 2026-08-06
Status: Accepted

## Context

The project needed ingestion, storage, transformation, orchestration, governance
and a serving layer. The obvious alternative was a cloud-native split — S3 for
landing, Lambda plus EventBridge for scheduled ingestion, Glue or EMR for
transformation, Athena or Redshift for serving — which is the shape most
reference architectures take.

That split requires a cloud account with billing attached, IAM to configure and
explain, and four services whose failure modes are unrelated to each other. The
stated goal of the capstone is depth in Databricks, not breadth across AWS.

## Decision

Everything runs inside Databricks Free Edition. A scheduled Lakeflow Job replaces
Lambda + EventBridge. A Unity Catalog Volume replaces the S3 landing bucket. A
Lakeflow Declarative Pipeline replaces Glue. Delta Lake replaces the warehouse.
Unity Catalog provides governance and lineage without a separate catalog service.

## Consequences

**Good.** One platform, one auth model, one place to look when something fails.
Lineage comes free from the pipeline graph rather than being assembled. No cloud
account, no IAM policy documents, no egress. A reviewer can clone the repo and
run it against their own workspace with one command.

**Bad.** Free Edition has a daily compute allowance rather than a bill, which
changes how the project is developed: selective refresh over full refresh, local
validation before any run, and a static expectation pre-flight so a typo costs
seconds instead of a cluster start. It also cannot create catalogs over the API —
the CLI, the storage-root override and SQL all refuse — so the catalog is the one
object created by hand in the UI.

**Bad.** Nothing here demonstrates multi-cloud or cross-service integration. That
is a deliberate trade, not an oversight.

## Alternatives considered

- **AWS-native (S3 + Lambda + Glue + Athena).** Rejected: four services and an
  IAM model to satisfy a requirement that one platform already meets.
- **Databricks on a paid workspace.** Rejected: no budget, and the constraint
  turned out to be productive — it forced the quota-aware habits above.
