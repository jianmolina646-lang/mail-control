# Seguridad operativa

## Controles activos

- Cinco fallos de login bloquean la combinación IP/usuario durante 15 minutos.
- Redis comparte el bloqueo entre todos los procesos backend.
- El JWT se entrega únicamente en una cookie `__Host-`, `Secure`, `HttpOnly` y
  `SameSite=Strict`; el frontend no lo guarda en `localStorage`.
- CORS y la validación de `Origin` aceptan únicamente `ALLOWED_ORIGINS`.
- Backend y Nginx envían CSP, HSTS, anti-clickjacking, `nosniff`, política de
  referencia y deshabilitan cámara, micrófono y geolocalización.

## 2FA TOTP (fase recomendada siguiente)

La activación segura de Google Authenticator requiere:

1. Dependencias `pyotp` y `qrcode[pil]`.
2. Columnas `totp_enabled` y `encrypted_totp_secret` en `users`.
3. Endpoint autenticado de enrolamiento que genere un secreto y QR.
4. Confirmación del primer código antes de activar TOTP.
5. Login en dos fases: contraseña y token temporal; después código TOTP.
6. Códigos de recuperación de un solo uso, almacenados como hashes.
7. Procedimiento documentado de recuperación para evitar bloquear al único
   administrador.

No se activa automáticamente hasta completar ese flujo y guardar códigos de
recuperación fuera del VPS.

## Operación

- Mantener `.env` con modo `600` y fuera de Git.
- Rotar secretos, contraseña MEGA y credenciales de Microsoft antes de expirar.
- Aplicar actualizaciones de imágenes y dependencias regularmente.
- Probar restauraciones de base de datos; crear un backup no demuestra que sea
  restaurable.
