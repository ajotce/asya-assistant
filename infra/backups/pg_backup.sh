#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

ensure_commands pg_dump gzip aws stat psql

require_env POSTGRES_HOST
require_env POSTGRES_PORT
require_env POSTGRES_DB
require_env POSTGRES_USER
require_env POSTGRES_PASSWORD
require_env BACKUP_S3_BUCKET
require_env BACKUP_S3_PREFIX
require_env BACKUP_SOURCE_INSTANCE

BACKUP_MODE="${BACKUP_MODE:-incremental}"
if [[ "${BACKUP_MODE}" != "incremental" && "${BACKUP_MODE}" != "full" ]]; then
  log "ERROR: BACKUP_MODE must be incremental or full"
  exit 1
fi

AWS_ARGS=()
if [[ -n "${BACKUP_S3_ENDPOINT_URL:-}" ]]; then AWS_ARGS+=(--endpoint-url "${BACKUP_S3_ENDPOINT_URL}"); fi
if [[ -n "${BACKUP_S3_REGION:-}" ]]; then AWS_ARGS+=(--region "${BACKUP_S3_REGION}"); fi

run_aws() {
  if (( ${#AWS_ARGS[@]} )); then aws "${AWS_ARGS[@]}" "$@"; else aws "$@"; fi
}

STAMP="$(date -u +'%Y%m%dT%H%M%SZ')"
TMP_DIR="${BACKUP_TMP_DIR:-/tmp/asya-backups}"
mkdir -p "${TMP_DIR}"

if [[ "${BACKUP_MODE}" == "full" ]]; then
  BACKUP_NAME="pg-full-${STAMP}.sql.gz"
  BACKUP_FILE="${TMP_DIR}/${BACKUP_NAME}"
  PG_DUMP_ARGS=(--host="${POSTGRES_HOST}" --port="${POSTGRES_PORT}" --username="${POSTGRES_USER}" --dbname="${POSTGRES_DB}" --no-owner --no-privileges --format=plain --clean --if-exists)
  export PGPASSWORD="${POSTGRES_PASSWORD}"
  log "Starting PostgreSQL full backup"
  pg_dump "${PG_DUMP_ARGS[@]}" | gzip -9 > "${BACKUP_FILE}"
  unset PGPASSWORD
else
  BACKUP_NAME="pg-wal-${STAMP}.json.gz"
  BACKUP_FILE="${TMP_DIR}/${BACKUP_NAME}"
  export PGPASSWORD="${POSTGRES_PASSWORD}"
  log "Starting PostgreSQL incremental marker backup (WAL metadata)"
  WAL_FILE="$(psql --host="${POSTGRES_HOST}" --port="${POSTGRES_PORT}" --username="${POSTGRES_USER}" --dbname="${POSTGRES_DB}" -At -c "SELECT pg_current_wal_lsn();")"
  cat <<JSON | gzip -9 > "${BACKUP_FILE}"
{"timestamp":"$(date -u +'%Y-%m-%dT%H:%M:%SZ')","wal_lsn":"${WAL_FILE}","note":"Incremental chain requires WAL archiving in cloud infra (Terraform 1.0.5)."}
JSON
  unset PGPASSWORD
fi

MANIFEST_NAME="${BACKUP_NAME%.gz}.manifest.json"
MANIFEST_FILE="${TMP_DIR}/${MANIFEST_NAME}"
BACKUP_SIZE="$(stat -f%z "${BACKUP_FILE}" 2>/dev/null || stat -c%s "${BACKUP_FILE}")"
BACKUP_SHA256="$(sha256_file "${BACKUP_FILE}")"
BUCKET_BASE="s3://${BACKUP_S3_BUCKET%/}/${BACKUP_S3_PREFIX%/}/postgresql/${BACKUP_MODE}/${STAMP}"
write_manifest "${MANIFEST_FILE}" "$(json_escape "${BACKUP_MODE}")" "$(json_escape "${BACKUP_SOURCE_INSTANCE}")" "${BACKUP_FILE}" "${BACKUP_SIZE}" "$(json_escape "${BACKUP_SHA256}")" "$(json_escape "${BUCKET_BASE}")"

run_aws s3 cp "${BACKUP_FILE}" "${BUCKET_BASE}/${BACKUP_NAME}"
run_aws s3 cp "${MANIFEST_FILE}" "${BUCKET_BASE}/${MANIFEST_NAME}"

log "Backup uploaded to ${BUCKET_BASE}"
rm -f "${BACKUP_FILE}" "${MANIFEST_FILE}"
