#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

: "${POSTGRES_USER:?POSTGRES_USER no configurado}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD no configurado}"
: "${POSTGRES_DB:?POSTGRES_DB no configurado}"

notify_telegram() {
    local message="$1"
    local token="${BACKUP_TELEGRAM_BOT_TOKEN:-}"
    if [[ -n "${BACKUP_TELEGRAM_BOT_TOKEN_FILE:-}" && -s "$BACKUP_TELEGRAM_BOT_TOKEN_FILE" ]]; then
        token="$(tr -d '\r\n' < "$BACKUP_TELEGRAM_BOT_TOKEN_FILE")"
    fi
    if [[ -z "$token" || -z "${BACKUP_TELEGRAM_CHAT_ID:-}" ]]; then
        return 0
    fi
    curl --fail --silent --show-error --max-time 20 \
        --data-urlencode "chat_id=${BACKUP_TELEGRAM_CHAT_ID}" \
        --data-urlencode "text=$message" \
        --data-urlencode "parse_mode=HTML" \
        "https://api.telegram.org/bot${token}/sendMessage" \
        >/dev/null 2>&1 || true
}

MEGA_FOLDER="${MEGA_FOLDER:-/MailControlBackups}"
DAILY_FOLDER="${MEGA_FOLDER%/}/Daily"
MONTHLY_FOLDER="${MEGA_FOLDER%/}/Monthly"
KEEP_DAYS="${BACKUP_DAILY_KEEP_DAYS:-30}"
KEEP_MONTHS="${BACKUP_MONTHLY_KEEP_MONTHS:-12}"
TIMESTAMP="$(date -u +%Y%m%d-%H%M%S)"
WORK_DIR="$(mktemp -d)"
PLAIN_ARCHIVE="$WORK_DIR/mail-control-${TIMESTAMP}.tar.gz"
ARCHIVE="/backups/mail-control-${TIMESTAMP}.tar.gz.enc"

ARCHIVE_PASSWORD="${BACKUP_ARCHIVE_PASSWORD:-}"
if [[ -n "${BACKUP_ARCHIVE_PASSWORD_FILE:-}" && -s "$BACKUP_ARCHIVE_PASSWORD_FILE" ]]; then
    ARCHIVE_PASSWORD="$(tr -d '\r\n' < "$BACKUP_ARCHIVE_PASSWORD_FILE")"
fi
: "${ARCHIVE_PASSWORD:?BACKUP_ARCHIVE_PASSWORD no configurada}"
export ARCHIVE_PASSWORD PGPASSWORD="$POSTGRES_PASSWORD"

on_exit() {
    local status=$?
    rm -rf "$WORK_DIR"
    if (( status != 0 )); then
        notify_telegram "🔴 <b>BACKUP FALLIDO</b>

Sistema: <b>Mail Control</b>
Revisa los logs del VPS."
    fi
    return "$status"
}
trap on_exit EXIT

mkdir -p "$WORK_DIR/payload/config"
pg_dump \
    --host=db \
    --port=5432 \
    --username="$POSTGRES_USER" \
    --dbname="$POSTGRES_DB" \
    --format=custom \
    --no-owner \
    --no-acl \
    --file="$WORK_DIR/payload/database.dump"

if [[ -f /source/config/.env ]]; then
    cp -a /source/config/.env "$WORK_DIR/payload/config/.env"
fi
{
    printf 'created_utc=%s\n' "$(date -u --iso-8601=seconds)"
    printf 'database=%s\n' "$POSTGRES_DB"
    printf 'includes=database,environment\n'
} > "$WORK_DIR/payload/manifest.txt"

(
    cd "$WORK_DIR/payload"
    find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
)
tar -czf "$PLAIN_ARCHIVE" -C "$WORK_DIR/payload" .
openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 \
    -in "$PLAIN_ARCHIVE" \
    -out "$ARCHIVE" \
    -pass env:ARCHIVE_PASSWORD

mega_session_ready=false
for _attempt in 1 2 3 4 5; do
    if mega-whoami >/dev/null 2>&1; then
        mega_session_ready=true
        break
    fi
    sleep 1
done
if [[ "$mega_session_ready" != "true" ]]; then
    : "${MEGA_EMAIL:?MEGA_EMAIL no configurado y no existe una sesión}"
    : "${MEGA_PASSWORD:?MEGA_PASSWORD no configurado y no existe una sesión}"
    mega-login "$MEGA_EMAIL" "$MEGA_PASSWORD"
    mega-whoami >/dev/null
fi

mega-mkdir -p "$DAILY_FOLDER" >/dev/null 2>&1 || true
mega-mkdir -p "$MONTHLY_FOLDER" >/dev/null 2>&1 || true
mega-put "$ARCHIVE" "$DAILY_FOLDER/"
mega-ls "$DAILY_FOLDER/$(basename "$ARCHIVE")" >/dev/null

if [[ "$(date -u +%d)" == "01" ]]; then
    MONTHLY_NAME="mail-control-monthly-$(date -u +%Y%m).tar.gz.enc"
    cp "$ARCHIVE" "/backups/$MONTHLY_NAME"
    mega-put "/backups/$MONTHLY_NAME" "$MONTHLY_FOLDER/"
    mega-ls "$MONTHLY_FOLDER/$MONTHLY_NAME" >/dev/null
    rm -f "/backups/$MONTHLY_NAME"
fi

CUTOFF="$(date -u -d "-${KEEP_DAYS} days" +%Y%m%d%H%M%S)"
while IFS= read -r remote_file; do
    filename="$(basename "$remote_file")"
    if [[ "$filename" =~ ^mail-control-([0-9]{8})-([0-9]{6})\.tar\.gz(\.enc)?$ ]]; then
        file_timestamp="${BASH_REMATCH[1]}${BASH_REMATCH[2]}"
        if [[ "$file_timestamp" < "$CUTOFF" ]]; then
            mega-rm "$remote_file"
        fi
    fi
done < <(
    mega-find "$DAILY_FOLDER" \
        --type=f \
        --pattern="mail-control-*.tar.gz*"
)

MONTH_CUTOFF="$(date -u -d "-${KEEP_MONTHS} months" +%Y%m)"
while IFS= read -r remote_file; do
    filename="$(basename "$remote_file")"
    if [[ "$filename" =~ ^mail-control-monthly-([0-9]{6})\.tar\.gz\.enc$ ]]; then
        if [[ "${BASH_REMATCH[1]}" < "$MONTH_CUTOFF" ]]; then
            mega-rm "$remote_file"
        fi
    fi
done < <(
    mega-find "$MONTHLY_FOLDER" \
        --type=f \
        --pattern="mail-control-monthly-*.tar.gz.enc"
)

find /backups -type f -name "mail-control-*.tar.gz*" -mtime +1 -delete
if [[ "${BACKUP_NOTIFY_SUCCESS:-true}" == "true" ]]; then
    notify_telegram "✅ <b>BACKUP COMPLETADO</b>

Sistema: <b>Mail Control</b>
Archivo: <code>$(basename "$ARCHIVE")</code>
Retención: 30 días + 12 meses."
fi
echo "Backup cifrado completado: $(basename "$ARCHIVE")"
