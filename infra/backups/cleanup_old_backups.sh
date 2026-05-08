#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

ensure_commands aws python3
require_env BACKUP_S3_BUCKET
require_env BACKUP_S3_PREFIX
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

AWS_ARGS=()
if [[ -n "${BACKUP_S3_ENDPOINT_URL:-}" ]]; then AWS_ARGS+=(--endpoint-url "${BACKUP_S3_ENDPOINT_URL}"); fi
if [[ -n "${BACKUP_S3_REGION:-}" ]]; then AWS_ARGS+=(--region "${BACKUP_S3_REGION}"); fi
run_aws(){ if (( ${#AWS_ARGS[@]} )); then aws "${AWS_ARGS[@]}" "$@"; else aws "$@"; fi; }

PREFIX="${BACKUP_S3_PREFIX%/}/"
CUTOFF_EPOCH="$(python3 - <<'PY' "${RETENTION_DAYS}"
import datetime,sys
print(int((datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(days=int(sys.argv[1]))).timestamp()))
PY
)"

TMP_KEYS="/tmp/asya-cleanup-keys.txt"; : > "$TMP_KEYS"
TOKEN=""
while :; do
  if [[ -n "$TOKEN" ]]; then
    PAGE="$(run_aws s3api list-objects-v2 --bucket "${BACKUP_S3_BUCKET}" --prefix "${PREFIX}" --continuation-token "$TOKEN")"
  else
    PAGE="$(run_aws s3api list-objects-v2 --bucket "${BACKUP_S3_BUCKET}" --prefix "${PREFIX}")"
  fi
  python3 - <<'PY' "$PAGE" "${BACKUP_S3_BUCKET}" "${CUTOFF_EPOCH}" "$TMP_KEYS"
import datetime,json,sys
payload=json.loads(sys.argv[1]); bucket=sys.argv[2]; cutoff=int(sys.argv[3]); out=sys.argv[4]
with open(out,'a',encoding='utf-8') as fp:
  for item in payload.get('Contents',[]):
    key=item.get('Key'); ts=item.get('LastModified')
    if not key or not ts: continue
    dt=datetime.datetime.fromisoformat(ts.replace('Z','+00:00'))
    if int(dt.timestamp()) < cutoff: fp.write(f"s3://{bucket}/{key}\n")
PY
  TOKEN="$(python3 - <<'PY' "$PAGE"
import json,sys
p=json.loads(sys.argv[1])
print(p.get('NextContinuationToken','') if p.get('IsTruncated') else '')
PY
)"
  [[ -n "$TOKEN" ]] || break
done

if [[ ! -s "$TMP_KEYS" ]]; then log "No objects eligible for deletion"; rm -f "$TMP_KEYS"; exit 0; fi
while IFS= read -r uri; do run_aws s3 rm "$uri"; done < "$TMP_KEYS"
rm -f "$TMP_KEYS"
log "Cleanup completed"
