#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$BACKEND_DIR/.env.production}"
COMPOSE_FILE="${COMPOSE_FILE:-$BACKEND_DIR/docker-compose.production.yml}"
: "${BACKUP_ENCRYPTION_KEY:?Set BACKUP_ENCRYPTION_KEY in a root-readable backup environment file}"
: "${RESTORE_CONFIRMATION:?Set RESTORE_CONFIRMATION=I_UNDERSTAND_THIS_REPLACES_PRODUCTION_DATA}"
[[ "$RESTORE_CONFIRMATION" == "I_UNDERSTAND_THIS_REPLACES_PRODUCTION_DATA" ]] || { echo "Restore confirmation is incorrect" >&2; exit 1; }
[[ $# -eq 1 ]] || { echo "Usage: RESTORE_CONFIRMATION=I_UNDERSTAND_THIS_REPLACES_PRODUCTION_DATA $0 <local-backup.gpg|s3://bucket/key>" >&2; exit 2; }
[[ -f "$ENV_FILE" ]] || { echo "Missing production environment file: $ENV_FILE" >&2; exit 1; }
(( ${#BACKUP_ENCRYPTION_KEY} >= 32 )) || { echo "BACKUP_ENCRYPTION_KEY must be at least 32 characters" >&2; exit 1; }
command -v docker >/dev/null
command -v gpg >/dev/null

COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")
WORK_DIR="$(mktemp -d)"
APP_SERVICES=(api billing-worker webhook-worker maintenance-worker notification-worker sms-worker)
mapfile -t RUNNING_SERVICES < <("${COMPOSE[@]}" ps --services --status running)
TO_STOP=()
for service in "${APP_SERVICES[@]}"; do
  for running in "${RUNNING_SERVICES[@]}"; do
    if [[ "$running" == "$service" ]]; then TO_STOP+=("$service"); break; fi
  done
done

cleanup() {
  local rc=$?
  trap - EXIT
  if ((${#TO_STOP[@]})); then
    "${COMPOSE[@]}" start "${TO_STOP[@]}" >/dev/null || { echo "ERROR: failed to restart the application after restore" >&2; rc=1; }
  fi
  rm -rf "$WORK_DIR"
  exit "$rc"
}
trap cleanup EXIT

SOURCE="$1"
ENCRYPTED="$WORK_DIR/backup.tar.gz.gpg"
if [[ "$SOURCE" == s3://* ]]; then
  command -v aws >/dev/null || { echo "AWS CLI is required to restore from S3" >&2; exit 1; }
  aws s3 cp --only-show-errors "$SOURCE" "$ENCRYPTED"
else
  [[ -f "$SOURCE" ]] || { echo "Backup file not found: $SOURCE" >&2; exit 1; }
  cp -- "$SOURCE" "$ENCRYPTED"
fi
gpg --batch --yes --pinentry-mode loopback --passphrase-fd 3 --output "$WORK_DIR/backup.tar.gz" --decrypt "$ENCRYPTED" 3<<<"$BACKUP_ENCRYPTION_KEY"
mkdir "$WORK_DIR/extracted"
mapfile -t MEMBERS < <(tar -tzf "$WORK_DIR/backup.tar.gz")
for member in "${MEMBERS[@]}"; do
  case "$member" in database.dump|attachments.tar.gz|manifest.txt|checksums.sha256) ;; *) echo "Unexpected path in backup archive: $member" >&2; exit 1 ;; esac
done
for required in database.dump attachments.tar.gz manifest.txt checksums.sha256; do
  printf "%s\n" "${MEMBERS[@]}" | grep -Fxq "$required" || { echo "Backup is missing $required" >&2; exit 1; }
done
tar -xzf "$WORK_DIR/backup.tar.gz" -C "$WORK_DIR/extracted"
(cd "$WORK_DIR/extracted" && sha256sum --check checksums.sha256)

echo "WARNING: this replaces the current production database and local attachments."
echo "A separate current-state backup is strongly recommended before proceeding."
if ((${#TO_STOP[@]})); then "${COMPOSE[@]}" stop --timeout 60 "${TO_STOP[@]}"; fi
"${COMPOSE[@]}" cp "$WORK_DIR/extracted/database.dump" db:/tmp/sam-restore.dump
"${COMPOSE[@]}" exec -T db pg_restore --username=sam --dbname=service_agreements --clean --if-exists --no-owner --no-privileges /tmp/sam-restore.dump
"${COMPOSE[@]}" exec -T db rm -f /tmp/sam-restore.dump
"${COMPOSE[@]}" run --rm --no-deps -T --entrypoint sh api -c "set -eu; find /srv/app/storage -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +; tar -xzf - -C /srv/app/storage" < "$WORK_DIR/extracted/attachments.tar.gz"
echo "Restore data import completed. Application services will be restarted; immediately verify /health/ready and key records."
