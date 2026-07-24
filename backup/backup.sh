#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

: "${POSTGRES_USER:?POSTGRES_USER no configurado}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD no configurado}"
: "${POSTGRES_DB:?POSTGRES_DB no configurado}"

MEGA_FOLDER="${MEGA_FOLDER:-/MailControlBackups}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-7}"
TIMESTAMP="$(date -u +%Y%m%d-%H%M%S)"
WORK_DIR="$(mktemp -d)"
ARCHIVE="/backups/mail-control-${TIMESTAMP}.tar.gz"

cleanup() {
    rm -rf "$WORK_DIR"
}
trap cleanup EXIT

export PGPASSWORD="$POSTGRES_PASSWORD"

pg_dump \
    --host=db \
    --port=5432 \
    --username="$POSTGRES_USER" \
    --dbname="$POSTGRES_DB" \
    --format=custom \
    --no-owner \
    --no-acl \
    --file="$WORK_DIR/database.dump"

sha256sum "$WORK_DIR/database.dump" \
    > "$WORK_DIR/database.dump.sha256"

tar -czf "$ARCHIVE" \
    -C "$WORK_DIR" \
    database.dump \
    database.dump.sha256

if ! mega-whoami >/dev/null 2>&1; then
    : "${MEGA_EMAIL:?MEGA_EMAIL no configurado y no existe una sesión}"
    : "${MEGA_PASSWORD:?MEGA_PASSWORD no configurado y no existe una sesión}"
    mega-login "$MEGA_EMAIL" "$MEGA_PASSWORD"
fi

if ! mega-ls "$MEGA_FOLDER" >/dev/null 2>&1; then
    mega-mkdir -p "$MEGA_FOLDER"
fi
mega-put "$ARCHIVE" "$MEGA_FOLDER/"
mega-ls "$MEGA_FOLDER/$(basename "$ARCHIVE")" >/dev/null

CUTOFF="$(date -u -d "-${KEEP_DAYS} days" +%Y%m%d%H%M%S)"
while IFS= read -r remote_file; do
    filename="$(basename "$remote_file")"
    if [[ "$filename" =~ ^mail-control-([0-9]{8})-([0-9]{6})\.tar\.gz$ ]]; then
        file_timestamp="${BASH_REMATCH[1]}${BASH_REMATCH[2]}"
        if [[ "$file_timestamp" < "$CUTOFF" ]]; then
            mega-rm "$remote_file"
        fi
    fi
done < <(
    mega-find "$MEGA_FOLDER" \
        --type=f \
        --pattern="mail-control-*.tar.gz"
)

find /backups \
    -type f \
    -name "mail-control-*.tar.gz" \
    -mtime +1 \
    -delete

echo "Backup completado: $(basename "$ARCHIVE")"
