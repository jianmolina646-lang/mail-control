# Backup de Mail Control Enterprise

El servicio definido en `compose.backup.yaml` respalda diariamente la base
PostgreSQL Enterprise a las 03:10 (`America/Lima`), cifra el archivo con
AES-256-CBC/PBKDF2 y lo sube a `/MailControlBackups/Enterprise` en MEGA.
La sesión de MEGA vive en un volumen exclusivo para evitar accesos concurrentes
con el backup del sistema original.

Los domingos a las 03:40 restaura la copia más reciente en una base temporal,
verifica sus hashes y confirma que contiene tablas. La base temporal se elimina
al terminar.

Configuración sensible en `.env.backup` (modo `0600`):

```dotenv
BACKUP_ARCHIVE_PASSWORD=...
BACKUP_DAILY_KEEP_DAYS=30
BACKUP_MONTHLY_KEEP_MONTHS=12
BACKUP_NOTIFY_SUCCESS=true
BACKUP_TELEGRAM_BOT_TOKEN=...
BACKUP_TELEGRAM_CHAT_ID=...
```

Activación y prueba manual:

```bash
docker compose -f compose.yaml -f compose.backup.yaml --profile backup \
  up -d --build enterprise-backup
docker compose -f compose.yaml -f compose.backup.yaml --profile backup \
  exec enterprise-backup /usr/local/bin/mailctl-enterprise-backup
docker compose -f compose.yaml -f compose.backup.yaml --profile backup \
  exec enterprise-backup /usr/local/bin/mailctl-enterprise-verify-restore
```
