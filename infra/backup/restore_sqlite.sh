#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

usage() {
  cat <<USAGE
Usage: $0 [--force] <BACKUP_FILE> <DESTINATION_SQLITE_PATH>

Behavior:
  - Without --force: runs `docker compose down` before restore.
  - With --force: skips docker compose shutdown requirement.
USAGE
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "ERROR: required command not found: $1"
    exit 1
  fi
}

FORCE=false
if [[ "${1:-}" == "--force" ]]; then
  FORCE=true
  shift
fi

if [[ $# -ne 2 ]]; then
  usage
  exit 1
fi

require_command sqlite3

BACKUP_FILE="$1"
DESTINATION_PATH="$2"

if [[ ! -f "$BACKUP_FILE" ]]; then
  log "ERROR: backup file not found: $BACKUP_FILE"
  exit 1
fi

if [[ "$FORCE" != "true" ]]; then
  require_command docker
  if ! docker compose down; then
    log "ERROR: failed to stop docker compose. Re-run with --force to override."
    exit 1
  fi
  log "docker compose stopped"
else
  log "--force enabled: skipping docker compose down"
fi

mkdir -p "$(dirname "$DESTINATION_PATH")"
cp "$BACKUP_FILE" "$DESTINATION_PATH"

INTEGRITY_RESULT="$(sqlite3 "$DESTINATION_PATH" "PRAGMA integrity_check;" | tr '[:upper:]' '[:lower:]')"
if [[ "$INTEGRITY_RESULT" != "ok" ]]; then
  log "ERROR: restored DB integrity_check failed: $INTEGRITY_RESULT"
  exit 1
fi

log "restored_path=$DESTINATION_PATH integrity_check=$INTEGRITY_RESULT"
