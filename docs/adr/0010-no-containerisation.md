# 10. No containerisation

## Context

The criteria ask for containerisation "if needed", which requires an explicit
answer rather than silence. Docker's usual value is reproducible execution: the
same dependencies, the same runtime, everywhere.

## Decision

No Docker. Execution is serverless Databricks compute with declared environment
specs (`client: "3"`), and reproducibility comes from the Asset Bundle plus that
environment definition.

## Consequences

**Good.** No image to build, no registry to host, no base image to patch. The
ingestion module uses only the Python standard library, so there is no dependency
set to pin for the runtime path at all.

**Good.** The pipeline's runtime is pinned where it matters — the `CURRENT`
channel rather than `PREVIEW`, so the engine moves when we move it, not when
Databricks releases (this was tested: update `18857fb9` completed on `CURRENT`).

**Bad.** Local development is not identical to the workspace. PySpark needs a
JVM, so the Spark-backed transformation tests run on Databricks as a job task
rather than locally, and contributors run only the pure-Python suite. A container
would not fix this either — it would move the JVM into an image without making
the local run representative of serverless.

**Bad.** Nothing here demonstrates container skills.

## Alternatives considered

- **Docker image for the ingestion job.** Rejected: serverless already declares
  its environment, and the module has no third-party dependencies to isolate.
- **devcontainer for local development.** Rejected as scope: `requirements-dev.txt`
  plus a venv is two commands, and the CI job proves it works on a clean runner.
