#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
: > /etc/mailctl-backup.env

for variable in \
    POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB \
    MEGA_EMAIL MEGA_PASSWORD MEGA_FOLDER BACKUP_KEEP_DAYS \
    BACKUP_ARCHIVE_PASSWORD BACKUP_ARCHIVE_PASSWORD_FILE
do
    printf 'export %s=%q\n' "$variable" "${!variable:-}" \
        >> /etc/mailctl-backup.env
done

chmod 600 /etc/mailctl-backup.env
if (( $# > 0 )); then
    exec "$@"
fi
exec cron -f
