# Seguridad operativa

## Controles activos

- Cinco fallos de login bloquean la combinación IP/usuario durante 15 minutos.
- Redis comparte el bloqueo entre todos los procesos backend.
- El JWT se entrega únicamente en una cookie `__Host-`, `Secure`, `HttpOnly` y
  `SameSite=Strict`; el frontend no lo guarda en `localStorage`.
- CORS y la validación de `Origin` aceptan únicamente `ALLOWED_ORIGINS`.
- Backend y Nginx envían CSP, HSTS, anti-clickjacking, `nosniff`, política de
  referencia y deshabilitan cámara, micrófono y geolocalización.
- Los hosts no autorizados, métodos inesperados, cuerpos mayores de 1 MiB y
  tipos de contenido no admitidos se rechazan antes de ejecutar una ruta.
- Las operaciones autenticadas que modifican datos requieren un token CSRF
  de doble envío, además de la cookie de sesión `SameSite=Strict`.
- Redis limita peticiones generales, escrituras, login y agente por IP. Nginx
  añade un segundo límite en el borde de la aplicación.
- Cada rechazo del middleware se registra con IP, método, ruta y motivo, sin
  escribir credenciales, cookies ni cuerpos en el log.
- El agente interno queda fuera de CSRF porque no usa cookies, pero conserva
  autenticación Bearer con comparación constante y su propio límite.

## 2FA TOTP activo

Google Authenticator se enrola desde Configuración. El secreto TOTP se cifra con
`CREDENTIALS_ENCRYPTION_KEY`, la activación exige confirmar un primer código y
los códigos de recuperación se guardan únicamente como hashes de un solo uso.
Para desactivar 2FA se requieren la contraseña actual y un TOTP vigente.

## Operación

- Mantener `.env` con modo `600` y fuera de Git.
- Rotar secretos, contraseña MEGA y credenciales de Microsoft antes de expirar.
- Aplicar actualizaciones de imágenes y dependencias regularmente.
- Probar restauraciones de base de datos; crear un backup no demuestra que sea
  restaurable.
