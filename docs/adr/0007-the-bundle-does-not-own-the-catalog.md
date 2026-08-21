# 7. The bundle owns the pipeline and jobs, not the catalog

Date: 2026-08-06
Status: Accepted

## Context

Databricks Asset Bundles can declare catalogs, schemas and volumes as resources,
which would make the whole platform reproducible from one `bundle deploy`.

Two things prevent it. Free Edition refuses catalog creation over the API through
every path — the CLI, the storage-root override, and SQL all fail — so the
catalog must be made in the UI regardless. And a `bundle destroy` on
bundle-managed schemas would drop the schemas, taking the data with them.

## Decision

The bundle owns the pipeline, both jobs and the dashboard. `scripts/create_catalog.sh`
owns the catalog, schemas and Volume; `scripts/upload_landing.sh` owns bulk data
upload; `scripts/apply_grants.py` owns the access model, because grants follow
the objects they sit on.

## Consequences

**Good.** `bundle destroy` cannot delete the data. The blast radius of a bundle
mistake is code, not the lakehouse.

**Good.** The grant script uses the Unity Catalog permissions API, so it costs no
compute and works with the daily quota exhausted.

**Bad.** Provisioning is two commands rather than one, and a newcomer must know
which half owns what. `scripts/bootstrap.sh` hides this behind a single command,
and the boundary is stated at the top of `databricks.yml`.

**Bad.** The grants are not visible in `databricks.yml`, so a reviewer looking
for governance-as-code has to be pointed at the script.

## Alternatives considered

- **Bundle-managed schemas with grants in YAML.** Rejected: `bundle destroy`
  would drop populated schemas, and Free Edition still cannot create the catalog.
- **Everything in scripts, no bundle.** Rejected: loses declarative deployment,
  drift detection and the dev/prod target split for the resources that can have
  them.
