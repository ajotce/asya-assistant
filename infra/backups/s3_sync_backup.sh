#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=infra/backups/common.sh
source "${SCRIPT_DIR}/common.sh"

ensure_commands aws stat

require_env PRIMARY_S3_BUCKET
require_env PRIMARY_S3_PREFIX
require_env OFFSITE_S3_BUCKET
require_env OFFSITE_S3_PREFIX
require_env BACKUP_SOURCE_INSTANCE

PRIMARY_ARGS=()
OFFSITE_ARGS=()

if [[ -n "${PRIMARY_S3_ENDPOINT_URL:-}" ]]; then
  PRIMARY_ARGS+=(--endpoint-url "${PRIMARY_S3_ENDPOINT_URL}")
fi
if [[ -n "${PRIMARY_S3_REGION:-}" ]]; then
  PRIMARY_ARGS+=(--region "${PRIMARY_S3_REGION}")
fi

if [[ -n "${OFFSITE_S3_ENDPOINT_URL:-}" ]]; then
  OFFSITE_ARGS+=(--endpoint-url "${OFFSITE_S3_ENDPOINT_URL}")
fi
if [[ -n "${OFFSITE_S3_REGION:-}" ]]; then
  OFFSITE_ARGS+=(--region "${OFFSITE_S3_REGION}")
fi

STAMP="$(date -u +'%Y%m%dT%H%M%SZ')"
TMP_DIR="${BACKUP_TMP_DIR:-/tmp/asya-backups}"
mkdir -p "${TMP_DIR}"

SRC_URI="s3://${PRIMARY_S3_BUCKET%/}/${PRIMARY_S3_PREFIX%/}"
DEST_URI="s3://${OFFSITE_S3_BUCKET%/}/${OFFSITE_S3_PREFIX%/object-storage/${STAMP}}"

log "Starting object storage off-site sync"
if [[ "${PRIMARY_S3_ENDPOINT_URL:-}" == "${OFFSITE_S3_ENDPOINT_URL:-}" && -n "${PRIMARY_S3_ENDPOINT_URL:-}" ]]; then
  if (( ${#PRIMARY_ARGS[@]} )); then
  aws "${PRIMARY_ARGS[@]}" s3 sync "${SRC_URI}" "${DEST_URI}"
else
  aws s3 sync "${SRC_URI}" "${DEST_URI}"
fi
else
  log "WARN: different endpoints detected; using local staging for cross-provider sync"
  STAGE_DIR="${TMP_DIR}/s3-sync-${STAMP}"
  mkdir -p "${STAGE_DIR}"
  if (( ${#PRIMARY_ARGS[@]} )); then
    aws "${PRIMARY_ARGS[@]}" s3 sync "${SRC_URI}" "${STAGE_DIR}"
  else
    aws s3 sync "${SRC_URI}" "${STAGE_DIR}"
  fi
  if (( ${#OFFSITE_ARGS[@]} )); then
    aws "${OFFSITE_ARGS[@]}" s3 sync "${STAGE_DIR}" "${DEST_URI}"
  else
    aws s3 sync "${STAGE_DIR}" "${DEST_URI}"
  fi
  rm -rf "${STAGE_DIR}"
fi

MANIFEST_NAME="s3-sync-${STAMP}.manifest.json"
MANIFEST_FILE="${TMP_DIR}/${MANIFEST_NAME}"
TMP_MARKER="${TMP_DIR}/s3-sync-${STAMP}.txt"
printf '%s\n' "${SRC_URI} -> ${DEST_URI}" > "${TMP_MARKER}"
MARKER_SIZE="$(stat -f%z "${TMP_MARKER}" 2>/dev/null || stat -c%s "${TMP_MARKER}")"
MARKER_SHA256="$(sha256_file "${TMP_MARKER}")"

write_manifest \
  "${MANIFEST_FILE}" \
  "$(json_escape "object-storage-sync")" \
  "$(json_escape "${BACKUP_SOURCE_INSTANCE}")" \
  "${TMP_MARKER}" \
  "${MARKER_SIZE}" \
  "$(json_escape "${MARKER_SHA256}")" \
  "$(json_escape "${DEST_URI}")"

if (( ${#OFFSITE_ARGS[@]} )); then
  aws "${OFFSITE_ARGS[@]}" s3 cp "${MANIFEST_FILE}" "${DEST_URI}/${MANIFEST_NAME}"
else
  aws s3 cp "${MANIFEST_FILE}" "${DEST_URI}/${MANIFEST_NAME}"
fi

rm -f "${TMP_MARKER}" "${MANIFEST_FILE}"
log "Object storage off-site sync finished"
