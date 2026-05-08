#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    log "ERROR: required env var is not set: ${name}"
    exit 1
  fi
}

ensure_commands() {
  local cmd
  for cmd in "$@"; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      log "ERROR: required command not found: ${cmd}"
      exit 1
    fi
  done
}

sha256_file() {
  local file_path="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$file_path" | awk '{print $1}'
  else
    shasum -a 256 "$file_path" | awk '{print $1}'
  fi
}

json_escape() {
  python3 - <<'PY' "$1"
import json
import sys
print(json.dumps(sys.argv[1]))
PY
}

write_manifest() {
  local manifest_path="$1"
  local backup_type="$2"
  local source_instance="$3"
  local payload_file="$4"
  local payload_size="$5"
  local payload_checksum="$6"
  local bucket_uri="$7"

  cat > "$manifest_path" <<JSON
{
  "timestamp": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')",
  "backup_type": ${backup_type},
  "source_instance": ${source_instance},
  "file": "$(basename "$payload_file")",
  "size_bytes": ${payload_size},
  "checksum_sha256": ${payload_checksum},
  "bucket_uri": ${bucket_uri}
}
JSON
}
