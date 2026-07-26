# Backups automáticos cifrados a MEGA

El servicio `backup` se ejecuta diariamente a las 03:00 (`America/Lima`).
Respalda PostgreSQL y el `.env` necesario para recuperar las credenciales
cifradas. Antes de salir del VPS, el paquete se cifra con AES-256-CBC,
PBKDF2 y 200 000 iteraciones. MEGA recibe únicamente el archivo `.enc`.

Se eliminan automáticamente los archivos con más de `BACKUP_KEEP_DAYS`.

## Variables

```env
MEGA_EMAIL=cuenta-backup@example.com
MEGA_PASSWORD=REEMPLAZAR
MEGA_FOLDER=/MailControlBackups
BACKUP_KEEP_DAYS=7
BACKUP_ARCHIVE_PASSWORD=UNA_FRASE_LARGA_Y_UNICA
```

Guarda `BACKUP_ARCHIVE_PASSWORD` también en un gestor de contraseñas fuera del
VPS. Sin esa clave no se puede restaurar el archivo.

## Activación y prueba

```bash
docker compose --profile backup build backup
docker compose --profile backup up -d backup
docker compose --profile backup run --rm backup /usr/local/bin/mailctl-backup
docker compose logs --tail=100 backup
```

## Restauración de prueba

```bash
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -in mail-control-YYYYMMDD-HHMMSS.tar.gz.enc \
  -out mail-control.tar.gz \
  -pass env:BACKUP_ARCHIVE_PASSWORD
mkdir restore
tar -xzf mail-control.tar.gz -C restore
cd restore
sha256sum -c SHA256SUMS
createdb mailctl_restore_test
pg_restore --no-owner --no-acl --dbname=mailctl_restore_test database.dump
```

Un respaldo solo se considera válido después de completar una restauración de
prueba.
