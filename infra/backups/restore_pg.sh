#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

ensure_commands aws psql gzip python3

require_env STAGING_POSTGRES_HOST
require_env STAGING_POSTGRES_PORT
require_env STAGING_POSTGRES_DB
require_env STAGING_POSTGRES_USER
require_env STAGING_POSTGRES_PASSWORD
require_env BACKUP_S3_BUCKET
require_env BACKUP_OBJECT_KEY
require_env RESTORE_CONFIRM

if [[ "${RESTORE_CONFIRM}" != "YES" ]]; then
  log "ERROR: set RESTORE_CONFIRM=YES to run restore"
  exit 1
fi
if [[ "${ALLOW_NON_STAGING_RESTORE:-false}" != "true" ]]; then
  if [[ "${STAGING_POSTGRES_DB}" != *"stage"* && "${STAGING_POSTGRES_DB}" != *"staging"* ]]; then
    log "ERROR: target DB name must include 'stage' or 'staging'"
    exit 1
  fi
fi

AWS_ARGS=()
if [[ -n "${BACKUP_S3_ENDPOINT_URL:-}" ]]; then AWS_ARGS+=(--endpoint-url "${BACKUP_S3_ENDPOINT_URL}"); fi
if [[ -n "${BACKUP_S3_REGION:-}" ]]; then AWS_ARGS+=(--region "${BACKUP_S3_REGION}"); fi
run_aws(){ if (( ${#AWS_ARGS[@]} )); then aws "${AWS_ARGS[@]}" "$@"; else aws "$@"; fi; }

TMP_DIR="${BACKUP_TMP_DIR:-/tmp/asya-backups}"; mkdir -p "${TMP_DIR}"
STAMP="$(date -u +'%Y%m%dT%H%M%SZ')"
BACKUP_LOCAL="${TMP_DIR}/restore-${STAMP}.bin.gz"
MANIFEST_LOCAL="${TMP_DIR}/restore-${STAMP}.manifest.json"
BACKUP_URI="s3://${BACKUP_S3_BUCKET}/${BACKUP_OBJECT_KEY}"
MANIFEST_URI="${BACKUP_URI%.gz}.manifest.json"

run_aws s3 cp "${BACKUP_URI}" "${BACKUP_LOCAL}"
run_aws s3 cp "${MANIFEST_URI}" "${MANIFEST_LOCAL}" || true

if [[ -f "${MANIFEST_LOCAL}" ]]; then
  EXPECTED_SHA256="$(python3 - <<'PY' "${MANIFEST_LOCAL}"
import json,sys
print(json.load(open(sys.argv[1],encoding='utf-8')).get('checksum_sha256',''))
PY
)"
  if [[ -n "${EXPECTED_SHA256}" ]]; then
    ACTUAL_SHA256="$(sha256_file "${BACKUP_LOCAL}")"
    [[ "${EXPECTED_SHA256}" == "${ACTUAL_SHA256}" ]] || { log "ERROR: checksum mismatch"; exit 1; }
  fi
fi

if [[ "${BACKUP_OBJECT_KEY}" != *.sql.gz ]]; then
  log "ERROR: restore_pg.sh supports only full SQL backups (*.sql.gz)."
  exit 1
fi

export PGPASSWORD="${STAGING_POSTGRES_PASSWORD}"
gzip -dc "${BACKUP_LOCAL}" | psql --host="${STAGING_POSTGRES_HOST}" --port="${STAGING_POSTGRES_PORT}" --username="${STAGING_POSTGRES_USER}" --dbname="${STAGING_POSTGRES_DB}" --set ON_ERROR_STOP=on
unset PGPASSWORD

rm -f "${BACKUP_LOCAL}" "${MANIFEST_LOCAL}"
log "Restore completed successfully"
