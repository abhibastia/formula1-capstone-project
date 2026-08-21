# 3. Bronze reads files as text, not JSON

Date: 2026-08-06
Status: Accepted

## Context

Bronze ingests eleven endpoints with Auto Loader. Reading them as JSON is the
obvious choice and lets Auto Loader infer a schema per endpoint.

It fails on this source. Optional Ergast fields — `FastestLap`, `Sprint`, `Q3` —
appear in only some files. With `cloudFiles.schemaEvolutionMode = addNewColumns`,
the first file carrying an unseen field makes the pipeline fail and retry, which
is correct behaviour producing an unusable pipeline: the failure arrives whenever
an unusual race happens, not when the code changes.

## Decision

Read every landing file as `text` with `wholeText = true`. The ingestion writer
lands exactly one single-line JSON object per file, so this yields one row per
file with the payload intact. Parsing is deferred to Silver, where each endpoint
has an explicit `StructType`.

## Consequences

**Good.** Schema evolution stops being an event. A new upstream field lands in
Bronze harmlessly and stays inert until someone adds it to a Silver schema — the
strategy is "defer and declare", not "infer and hope".

**Good.** Bronze genuinely never drops a row and never types a field, so the raw
payload is auditable byte-for-byte against the API call that produced it.

**Bad.** Bronze is not directly queryable in a useful way — every column beyond
the provenance envelope requires `get_json_object` or a Silver schema. That is
the intended trade: Bronze is for audit, Silver is for reading.

## Alternatives considered

- **JSON with `addNewColumns`.** Rejected: fails and retries the pipeline on the
  first unusual file.
- **JSON with `rescuedDataColumn`.** Rejected: keeps the data but leaves the
  schema drifting per endpoint, and still infers types we would rather declare.
