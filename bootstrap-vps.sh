#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-/home/deploy/mail-control-enterprise}"
cd "$APP_DIR"
umask 077

app_secret="$(openssl rand -hex 48)"
db_password="$(openssl rand -hex 24)"
rabbitmq_password="$(openssl rand -hex 24)"
encryption_key="$(
  openssl rand -base64 32 |
    tr '/+' '_-' |
    tr -d '\n'
)"

cat > .env <<EOF
APP_ENV=production
APP_SECRET_KEY=$app_secret
DATABASE_URL=postgresql+asyncpg://mail_control:$db_password@postgres:5432/mail_control
REDIS_URL=redis://redis:6379/0
RABBITMQ_URL=amqp://mail_control:$rabbitmq_password@rabbitmq:5672/
ALLOWED_ORIGINS=http://127.0.0.1:8180
FRONTEND_URL=http://127.0.0.1:8180
LOG_LEVEL=INFO
ACCESS_TOKEN_TTL_MINUTES=15
REFRESH_TOKEN_TTL_DAYS=30
JWT_ISSUER=mail-control-enterprise
CREDENTIAL_ENCRYPTION_KEY=$encryption_key
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://127.0.0.1:8100/v1/providers/gmail/callback
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
MICROSOFT_REDIRECT_URI=http://127.0.0.1:8100/v1/providers/microsoft/callback
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.6-flash
POSTGRES_DB=mail_control
POSTGRES_USER=mail_control
POSTGRES_PASSWORD=$db_password
RABBITMQ_DEFAULT_USER=mail_control
RABBITMQ_DEFAULT_PASS=$rabbitmq_password
API_BIND_ADDRESS=127.0.0.1
API_PORT=8100
WEB_BIND_ADDRESS=127.0.0.1
WEB_PORT=8180
EOF

chmod 600 .env
echo "Production environment created at $APP_DIR/.env"
