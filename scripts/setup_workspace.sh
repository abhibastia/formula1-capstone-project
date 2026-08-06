#!/usr/bin/env bash
#
# Provisions the whole project into a Databricks workspace and runs it.
#
# Idempotent: every step tolerates already-existing objects, so re-running after
# a partial failure is safe.
#
# PREREQUISITE — the catalog must already exist. Databricks Free Edition refuses
# catalog creation over the API ("Please use the UI to create a catalog with
# Default Storage"), so create it once by hand:
#     Catalog → Create catalog → name: f1 → Default storage
#
# Usage:
#     ./scripts/setup_workspace.sh [--skip-upload]

set -euo pipefail

PROFILE="${DATABRICKS_PROFILE:-abhi}"
CATALOG="${F1_CATALOG:-f1}"
USER_EMAIL="$(databricks current-user me --profile "$PROFILE" -o json | python3 -c 'import sys,json;print(json.load(sys.stdin)["userName"])')"
WS_DIR="/Workspace/Users/${USER_EMAIL}/f1_capstone"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_LANDING="${F1_LOCAL_LANDING:-}"
VOLUME_PATH="/Volumes/${CATALOG}/raw/landing"

say() { printf '\n\033[1m▸ %s\033[0m\n' "$*"; }

# ─────────────────────── 1. catalog, schemas, volume ────────────────────
# Delegated so the creation logic (and its Free Edition fallbacks) lives in
# exactly one place. Exits non-zero with instructions if the catalog is missing.
say "Catalog, schemas and volume"
"${REPO_ROOT}/scripts/create_catalog.sh"

# ────────────────────────── 2. upload raw data ──────────────────────────
# Ingestion runs locally for the backfill so it does not consume the Free
# Edition compute quota; the Files API upload needs no compute either.
if [[ "${1:-}" != "--skip-upload" ]]; then
  if [[ -z "$LOCAL_LANDING" ]]; then
    echo "  F1_LOCAL_LANDING not set — skipping raw upload."
    echo "  Run the backfill first:  python3 src/ingestion/ingest.py --mode backfill --root <dir>"
  else
    say "Uploading raw JSON to ${VOLUME_PATH}"
    databricks fs cp -r --overwrite "$LOCAL_LANDING" "dbfs:${VOLUME_PATH}" --profile "$PROFILE"
    echo "  files in volume: $(databricks fs ls "dbfs:${VOLUME_PATH}" --profile "$PROFILE" | wc -l) endpoint dirs"
  fi
fi

# ───────────────────────── 3. upload source code ────────────────────────
say "Uploading pipeline + ingestion source to ${WS_DIR}"
databricks workspace mkdirs "$WS_DIR" --profile "$PROFILE" >/dev/null 2>&1 || true
databricks workspace import-dir "${REPO_ROOT}/src/pipeline" "${WS_DIR}/pipeline" \
  --overwrite --profile "$PROFILE"
databricks workspace import-dir "${REPO_ROOT}/src/ingestion" "${WS_DIR}/ingestion" \
  --overwrite --profile "$PROFILE"

# ──────────────────────────── 4. the pipeline ───────────────────────────
# One triggered serverless pipeline spanning bronze/silver/gold. Datasets use
# fully-qualified names, so the default schema below only decides where
# unqualified objects would land.
say "Creating Lakeflow pipeline"
PIPELINE_JSON=$(cat <<EOF
{
  "name": "f1_medallion_pipeline",
  "catalog": "${CATALOG}",
  "schema": "bronze",
  "serverless": true,
  "continuous": false,
  "development": true,
  "channel": "PREVIEW",
  "photon": true,
  "configuration": {
    "f1.landing_root": "${VOLUME_PATH}",
    "pipelines.numUpdateRetryAttempts": "0",
    "pipelines.maxFlowRetryAttempts": "0"
  },
  "event_log": {
    "catalog": "${CATALOG}",
    "schema": "gold",
    "name": "pipeline_event_log"
  },
  "libraries": [{"glob": {"include": "${WS_DIR}/pipeline/**"}}]
}
EOF
)

EXISTING_PIPELINE=$(databricks pipelines list-pipelines --profile "$PROFILE" -o json 2>/dev/null \
  | python3 -c 'import sys,json;print(next((p["pipeline_id"] for p in json.load(sys.stdin) if p["name"]=="f1_medallion_pipeline"), ""))')

if [[ -n "$EXISTING_PIPELINE" ]]; then
  echo "  updating existing pipeline ${EXISTING_PIPELINE}"
  databricks pipelines update "$EXISTING_PIPELINE" --json "$PIPELINE_JSON" --profile "$PROFILE" >/dev/null
  PIPELINE_ID="$EXISTING_PIPELINE"
else
  PIPELINE_ID=$(databricks pipelines create --json "$PIPELINE_JSON" --profile "$PROFILE" -o json \
    | python3 -c 'import sys,json;print(json.load(sys.stdin)["pipeline_id"])')
  echo "  created ${PIPELINE_ID}"
fi

# ─────────────────────── 5. the scheduled ingest job ────────────────────
# Weekly on Tuesday: after every race weekend, before the next one.
say "Creating scheduled ingestion job"
JOB_JSON=$(cat <<EOF
{
  "name": "f1_ingest_incremental",
  "tasks": [{
    "task_key": "ingest",
    "spark_python_task": {
      "python_file": "${WS_DIR}/ingestion/ingest.py",
      "parameters": ["--mode", "incremental", "--root", "${VOLUME_PATH}"],
      "source": "WORKSPACE"
    },
    "environment_key": "default"
  }],
  "environments": [{
    "environment_key": "default",
    "spec": {"client": "3"}
  }],
  "schedule": {
    "quartz_cron_expression": "0 0 6 ? * TUE",
    "timezone_id": "UTC",
    "pause_status": "UNPAUSED"
  },
  "max_concurrent_runs": 1
}
EOF
)

EXISTING_JOB=$(databricks jobs list --profile "$PROFILE" -o json 2>/dev/null \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print(next((str(j["job_id"]) for j in (d if isinstance(d,list) else d.get("jobs",[])) if j.get("settings",{}).get("name")=="f1_ingest_incremental"), ""))')

if [[ -n "$EXISTING_JOB" ]]; then
  echo "  job already exists: ${EXISTING_JOB}"
else
  JOB_ID=$(databricks jobs create --json "$JOB_JSON" --profile "$PROFILE" -o json \
    | python3 -c 'import sys,json;print(json.load(sys.stdin)["job_id"])')
  echo "  created job ${JOB_ID}"
fi

cat <<EOF

────────────────────────────────────────────────────────────
Setup complete.

  pipeline id : ${PIPELINE_ID}

Run it:
  ./scripts/run_pipeline.sh ${PIPELINE_ID}
────────────────────────────────────────────────────────────
EOF
