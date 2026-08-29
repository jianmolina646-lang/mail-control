# Mail Control Enterprise

Nueva plataforma SaaS multi-tenant para sincronizar, analizar y supervisar
cuentas de Gmail y Microsoft. Este repositorio es independiente del Mail Control
actual.

## Estado

**Fase 5 - APIs de dashboard y búsqueda**

- FastAPI con ciclo de vida explícito.
- SQLAlchemy asíncrono y PostgreSQL.
- Redis para caché, rate limits y coordinación.
- RabbitMQ para trabajos duraderos.
- Alembic como único mecanismo de migración.
- Contraseñas Argon2id y JWT de acceso de corta duración.
- Refresh tokens rotatorios, revocables y almacenados como hash.
- Roles Owner, Admin, Operator y Viewer.
- Aislamiento PostgreSQL Row-Level Security por distribuidor.
- Gmail API con OAuth 2.0 server-side, PKCE, state de un solo uso y acceso offline.
- Tokens de Google cifrados en reposo.
- Sincronización completa inicial e incremental mediante Gmail History API.
- Worker RabbitMQ independiente e importación idempotente por mensaje.
- Outlook, Hotmail y Live mediante Microsoft Graph y endpoint OAuth `common`.
- Delta Query por carpeta con cursores opacos e IDs inmutables.
- Clasificación estructurada con Gemini y validación Pydantic.
- Análisis persistente para no consumir tokens dos veces.
- Alertas automáticas y outbox transaccional con reintentos.
- Dashboard agregado, tendencias de 14 días y cobertura de análisis.
- Búsqueda full-text PostgreSQL y paginación estable por cursor.
- Filtros por cuenta, proveedor, categoría, riesgo y estado de alerta.
- Calidad automatizada con Ruff, MyPy y Pytest.

## Inicio local

```bash
cp .env.example .env
docker compose up --build
```

## API

- `GET /health/live`
- `GET /health/ready`
- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `POST /v1/auth/refresh`
- `POST /v1/auth/logout`
- `GET /v1/auth/me`
- `POST /v1/providers/gmail/authorize`
- `GET /v1/providers/gmail/callback`
- `POST /v1/providers/gmail/{account_id}/sync`
- `POST /v1/providers/microsoft/authorize`
- `GET /v1/providers/microsoft/callback`
- `POST /v1/providers/microsoft/{account_id}/sync`
- `GET /v1/dashboard/summary`
- `GET /v1/mail/accounts`
- `GET /v1/mail/messages`
- `GET /v1/alerts`
- `PATCH /v1/alerts/{alert_id}/resolve`
- `GET /v1/saas/usage`
- `GET /v1/saas/users`
- `POST /v1/saas/users`
- `PATCH /v1/saas/users/{user_id}`

Cada transacción protegida configura `app.current_tenant_id`; las políticas RLS
rechazan accesos a datos de otro distribuidor incluso si una consulta olvida el
filtro de tenant.

## Validación

```bash
docker compose run --rm api ruff check .
docker compose run --rm api mypy src
docker compose run --rm api pytest
docker compose run --rm api alembic upgrade head
```

## Frontend

El panel React de producción vive en `frontend/` y consume directamente la API
real `/v1` para autenticación, métricas, correos, cuentas conectadas,
autorización OAuth, sincronización manual y alertas.

```bash
cd frontend
npm install
npm run dev
```

En desarrollo, Vite redirige `/v1` y `/health` a `http://localhost:8000`. Define
`VITE_API_URL` únicamente cuando la API use otro origen. El paquete de
producción se genera con `npm run build`.

El servicio `web` de Docker Compose compila el frontend y lo sirve mediante
Nginx en `127.0.0.1:8080`, con proxy interno hacia `api:8000`. En producción,
configura `FRONTEND_URL` y los URI de retorno OAuth con el dominio HTTPS
definitivo antes de autorizar cuentas.
