# Respaldo adicional en Google Drive

Este servicio independiente fue sustituido por la replicación central del VPS
`/usr/local/sbin/production-r2-backup-sync`, que verifica R2 y Google Drive para
todos los sitios. Se conserva solo para recuperación manual bajo el perfil
`legacy-drive`, sin reinicio automático. No activarlo junto a la tarea central.
Destino actual: `ProductionBackups/mail-control/enterprise/daily` en Drive.

El servicio lee el volumen de archivos cifrados existente y revisa cada hora
las copias terminadas. Valida descifrado y CRC gzip, sube con rclone y compara
tamaño y hash remoto. MEGA conserva su proceso independiente.

Destino: `MailControlBackups/Enterprise/Daily`. OAuth usa `drive.file` (solo
archivos creados por rclone), y se guarda en `secrets/drive/rclone.conf` con
permisos 0600. El directorio se monta escribible para renovar tokens.
Nunca añadir ese archivo a Git.

La clave existente `BACKUP_ARCHIVE_PASSWORD` y, opcionalmente, las variables
`BACKUP_TELEGRAM_BOT_TOKEN` y `BACKUP_TELEGRAM_CHAT_ID` van en `.env.drive`
(0600). Mantener la clave original para poder restaurar los archivos.

Se conservan las 30 copias más recientes. Las anteriores se eliminan
permanentemente únicamente dentro de esta carpeta y después de verificar
la subida. Otros archivos y carpetas de Drive no se modifican.

Activar con `docker compose -f compose.drive.yaml up -d --build`.
Comprobar con `docker compose -f compose.drive.yaml ps`.
Prueba manual: `docker compose -f compose.drive.yaml run --rm drive-backup python3 /app/mirror.py --once`.

El estado saludable exige una comprobación exitosa hace menos de 3 horas y
un respaldo fuente menor de 36 horas. Se alerta ante archivos obsoletos o
errores de cifrado, subida o verificación. La validación de gzip no sustituye
una prueba de restauración de PostgreSQL; esta continúa en el servicio original.
