# Backups automáticos a MEGA

El servicio `backup` ejecuta `pg_dump` todos los días a las 03:00
(`America/Lima`), crea un `tar.gz` con checksum SHA-256, lo sube con MEGAcmd y
elimina de MEGA los archivos cuyo nombre indique más de `BACKUP_KEEP_DAYS`.

## Configuración

Configurar en `.env` una cuenta MEGA dedicada:

```env
MEGA_EMAIL=cuenta-backup@example.com
MEGA_PASSWORD=REEMPLAZA_CON_TU_PASSWORD
MEGA_FOLDER=/MailControlBackups
BACKUP_KEEP_DAYS=7
```

Proteger el archivo:

```bash
chmod 600 .env
```

Más seguro: iniciar sesión una sola vez de forma interactiva (también permite
resolver 2FA de MEGA), conservar la sesión en el volumen `mega_session` y
después borrar `MEGA_PASSWORD` del `.env`:

```bash
docker compose --profile backup run --rm backup mega-login
nano .env
```

El script usa `MEGA_EMAIL`/`MEGA_PASSWORD` únicamente si no encuentra una
sesión persistida.

## Activación y prueba

```bash
docker compose --profile backup build backup
docker compose --profile backup up -d backup
docker compose --profile backup run --rm backup /usr/local/bin/mailctl-backup
docker compose logs --tail=100 backup
```

## Restauración de prueba

Descargar el archivo desde MEGA y ejecutar:

```bash
tar -xzf mail-control-YYYYMMDD-HHMMSS.tar.gz
sha256sum -c database.dump.sha256
createdb mailctl_restore_test
pg_restore --no-owner --no-acl --dbname=mailctl_restore_test database.dump
```

Una copia no se considera válida hasta completar una restauración de prueba.
Guardar `CREDENTIALS_ENCRYPTION_KEY` en un gestor de secretos separado: sin esa
clave no se pueden recuperar las credenciales cifradas del dump.
