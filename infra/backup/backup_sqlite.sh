#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

usage() {
  cat <<USAGE
Usage: $0 [SQLITE_PATH] [BACKUP_DIR]

Env vars:
  SQLITE_PATH   Path to source SQLite database file.
  BACKUP_DIR    Backup directory (default: ./backups).
USAGE
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "ERROR: required command not found: $1"
    exit 1
  fi
}

file_size_bytes() {
  local file_path="$1"
  stat -f%z "$file_path" 2>/dev/null || stat -c%s "$file_path"
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

require_command sqlite3

SQLITE_PATH="${1:-${SQLITE_PATH:-}}"
BACKUP_DIR="${2:-${BACKUP_DIR:-./backups}}"

if [[ -z "$SQLITE_PATH" ]]; then
  log "ERROR: SQLITE_PATH is required as arg or env var"
  usage
  exit 1
fi

if [[ ! -f "$SQLITE_PATH" ]]; then
  log "ERROR: SQLite DB file not found: $SQLITE_PATH"
  exit 1
fi

mkdir -p "$BACKUP_DIR"

STAMP="$(date +'%Y%m%d_%H%M%S')"
BACKUP_FILE="${BACKUP_DIR%/}/asya_backup_${STAMP}.db"
cp "$SQLITE_PATH" "$BACKUP_FILE"

INTEGRITY_RESULT="$(sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;" | tr '[:upper:]' '[:lower:]')"
if [[ "$INTEGRITY_RESULT" != "ok" ]]; then
  rm -f "$BACKUP_FILE"
  log "backup_path=$BACKUP_FILE size_bytes=0 integrity_check=$INTEGRITY_RESULT"
  log "ERROR: integrity_check failed, backup removed"
  exit 1
fi

SIZE_BYTES="$(file_size_bytes "$BACKUP_FILE")"
log "backup_path=$BACKUP_FILE size_bytes=$SIZE_BYTES integrity_check=$INTEGRITY_RESULT"

# Retention: keep last 30 backups.
TOTAL_BACKUPS="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'asya_backup_*.db' | wc -l | tr -d ' ')"
if [[ "$TOTAL_BACKUPS" -gt 30 ]]; then
  TO_DELETE=$((TOTAL_BACKUPS - 30))
  find "$BACKUP_DIR" -maxdepth 1 -type f -name 'asya_backup_*.db' \
    | LC_ALL=C sort \
    | head -n "$TO_DELETE" \
    | while IFS= read -r old_file; do
        rm -f "$old_file"
        log "retention_delete=$old_file"
      done
fi
