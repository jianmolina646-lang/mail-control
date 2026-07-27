# Backups automáticos cifrados a MEGA

El servicio `backup` se ejecuta diariamente a las 03:00 (`America/Lima`).
Respalda PostgreSQL y el `.env` necesario para recuperar las credenciales
cifradas. Antes de salir del VPS, el paquete se cifra con AES-256-CBC,
PBKDF2 y 200 000 iteraciones. MEGA recibe únicamente el archivo `.enc`.

MEGA organiza las copias en dos niveles:

- `Daily/`: una copia diaria durante 30 días.
- `Monthly/`: una copia del primer día de cada mes durante 12 meses.

## Variables

```env
MEGA_EMAIL=cuenta-backup@example.com
MEGA_PASSWORD=REEMPLAZAR
MEGA_FOLDER=/MailControlBackups
BACKUP_DAILY_KEEP_DAYS=30
BACKUP_MONTHLY_KEEP_MONTHS=12
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

El contenedor ejecuta automáticamente una restauración aislada cada domingo a
las 03:30. También se puede verificar el respaldo más reciente bajo demanda:

```bash
docker compose --profile backup exec backup /usr/local/bin/mailctl-verify-restore
```

La prueba descifra el archivo, valida sus hashes, restaura PostgreSQL en una base
temporal, comprueba que contiene tablas y elimina esa base. Nunca escribe sobre
la base de producción.
