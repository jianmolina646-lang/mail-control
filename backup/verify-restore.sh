#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

: "${POSTGRES_USER:?POSTGRES_USER no configurado}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD no configurado}"
: "${POSTGRES_DB:?POSTGRES_DB no configurado}"

ARCHIVE_PASSWORD="${BACKUP_ARCHIVE_PASSWORD:-}"
if [[ -n "${BACKUP_ARCHIVE_PASSWORD_FILE:-}" && -s "$BACKUP_ARCHIVE_PASSWORD_FILE" ]]; then
    ARCHIVE_PASSWORD="$(tr -d '\r\n' < "$BACKUP_ARCHIVE_PASSWORD_FILE")"
fi
: "${ARCHIVE_PASSWORD:?BACKUP_ARCHIVE_PASSWORD no configurada}"

WORK_DIR="$(mktemp -d)"
RESTORE_DB="mailctl_verify_$(date -u +%Y%m%d_%H%M%S)_$$"
export ARCHIVE_PASSWORD PGPASSWORD="$POSTGRES_PASSWORD"

cleanup() {
    dropdb --if-exists --host=db --username="$POSTGRES_USER" "$RESTORE_DB" >/dev/null 2>&1 || true
    rm -rf "$WORK_DIR"
}
trap cleanup EXIT

ARCHIVE="${1:-}"
if [[ -z "$ARCHIVE" ]]; then
    ARCHIVE="$(find /backups -maxdepth 1 -type f -name 'mail-control-*.tar.gz.enc' -printf '%T@ %p\n' | sort -nr | head -n1 | cut -d' ' -f2-)"
fi
if [[ -z "$ARCHIVE" ]]; then
    MEGA_FOLDER="${MEGA_FOLDER:-/MailControlBackups}"
    REMOTE="$(mega-find "${MEGA_FOLDER%/}/Daily" --type=f --pattern='mail-control-*.tar.gz.enc' | sort | tail -n1)"
    [[ -n "$REMOTE" ]] || { echo "No se encontró ningún respaldo para verificar" >&2; exit 1; }
    mega-get "$REMOTE" "$WORK_DIR/"
    ARCHIVE="$WORK_DIR/$(basename "$REMOTE")"
fi
[[ -s "$ARCHIVE" ]] || { echo "El respaldo está vacío o no existe: $ARCHIVE" >&2; exit 1; }

openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
    -in "$ARCHIVE" -out "$WORK_DIR/archive.tar.gz" -pass env:ARCHIVE_PASSWORD
mkdir "$WORK_DIR/payload"
tar -xzf "$WORK_DIR/archive.tar.gz" -C "$WORK_DIR/payload"
(
    cd "$WORK_DIR/payload"
    sha256sum -c SHA256SUMS
    pg_restore --list database.dump >/dev/null
)

createdb --host=db --username="$POSTGRES_USER" "$RESTORE_DB"
pg_restore --host=db --username="$POSTGRES_USER" --no-owner --no-acl \
    --dbname="$RESTORE_DB" "$WORK_DIR/payload/database.dump"
TABLE_COUNT="$(psql --host=db --username="$POSTGRES_USER" --dbname="$RESTORE_DB" \
    --tuples-only --no-align --command="SELECT count(*) FROM information_schema.tables WHERE table_schema='public';")"
[[ "$TABLE_COUNT" -gt 0 ]] || { echo "La restauración no contiene tablas" >&2; exit 1; }

echo "Restauración verificada: $(basename "$ARCHIVE") ($TABLE_COUNT tablas)"
