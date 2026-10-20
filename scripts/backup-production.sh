#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$BACKEND_DIR/.env.production}"
COMPOSE_FILE="${COMPOSE_FILE:-$BACKEND_DIR/docker-compose.production.yml}"
BACKUP_DIRECTORY="${BACKUP_DIRECTORY:-/var/backups/service-agreement-manager}"
: "${BACKUP_ENCRYPTION_KEY:?Set BACKUP_ENCRYPTION_KEY in a root-readable backup environment file}"
: "${BACKUP_S3_URI:?Set BACKUP_S3_URI to an off-site s3://bucket/prefix destination}"
[[ -f "$ENV_FILE" ]] || { echo "Missing production environment file: $ENV_FILE" >&2; exit 1; }
[[ "$BACKUP_S3_URI" == s3://* ]] || { echo "BACKUP_S3_URI must begin with s3://" >&2; exit 1; }
(( ${#BACKUP_ENCRYPTION_KEY} >= 32 )) || { echo "BACKUP_ENCRYPTION_KEY must be at least 32 characters" >&2; exit 1; }
command -v docker >/dev/null
command -v gpg >/dev/null
command -v aws >/dev/null || { echo "AWS CLI is required for off-site backup upload" >&2; exit 1; }
command -v sha256sum >/dev/null

COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")
mkdir -p "$BACKUP_DIRECTORY"
chmod 700 "$BACKUP_DIRECTORY"
WORK_DIR="$(mktemp -d)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT="$BACKUP_DIRECTORY/service-agreement-manager-$STAMP.tar.gz.gpg"
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
    "${COMPOSE[@]}" start "${TO_STOP[@]}" >/dev/null || { echo "ERROR: failed to restart the application after backup" >&2; rc=1; }
  fi
  rm -rf "$WORK_DIR"
  exit "$rc"
}
trap cleanup EXIT

echo "Temporarily stopping active API/workers for a consistent database + local-attachment snapshot..."
if ((${#TO_STOP[@]})); then "${COMPOSE[@]}" stop --timeout 60 "${TO_STOP[@]}"; fi
"${COMPOSE[@]}" exec -T db pg_dump --username=sam --dbname=service_agreements --format=custom > "$WORK_DIR/database.dump"
"${COMPOSE[@]}" run --rm --no-deps -T --entrypoint sh api -c "tar -czf - -C /srv/app/storage ." > "$WORK_DIR/attachments.tar.gz"

{
  printf "created_utc=%s\n" "$STAMP"
  printf "compose_file=%s\n" "$COMPOSE_FILE"
} > "$WORK_DIR/manifest.txt"
(cd "$WORK_DIR" && sha256sum database.dump attachments.tar.gz > checksums.sha256)
tar -C "$WORK_DIR" -czf "$WORK_DIR/backup.tar.gz" database.dump attachments.tar.gz manifest.txt checksums.sha256

# GnuPG symmetric encryption provides authenticated encryption/integrity checking.
gpg --batch --yes --symmetric --cipher-algo AES256 --pinentry-mode loopback --passphrase-fd 3 --output "$OUTPUT" "$WORK_DIR/backup.tar.gz" 3<<<"$BACKUP_ENCRYPTION_KEY"
chmod 600 "$OUTPUT"
aws s3 cp --only-show-errors --sse AES256 "$OUTPUT" "${BACKUP_S3_URI%/}/$(basename "$OUTPUT")"

echo "Encrypted backup created and uploaded: $(basename "$OUTPUT")"
echo "Configure bucket versioning, restrictive access, and retention/lifecycle policy independently."
