#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-/home/deploy/mail-control-enterprise}"
cd "$APP_DIR"

db_password="$(openssl rand -hex 24)"
rabbitmq_password="$(openssl rand -hex 24)"

docker compose exec -T postgres psql \
  -U mail_control \
  -d mail_control \
  -c "ALTER USER mail_control WITH PASSWORD '$db_password';" >/dev/null
docker compose exec -T rabbitmq rabbitmqctl \
  change_password mail_control "$rabbitmq_password" >/dev/null

sed -i \
  -e "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+asyncpg://mail_control:$db_password@postgres:5432/mail_control|" \
  -e "s|^MIGRATION_DATABASE_URL=.*|MIGRATION_DATABASE_URL=postgresql+asyncpg://mail_control:$db_password@postgres:5432/mail_control|" \
  -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$db_password|" \
  -e "s|^RABBITMQ_URL=.*|RABBITMQ_URL=amqp://mail_control:$rabbitmq_password@rabbitmq:5672/|" \
  -e "s|^RABBITMQ_DEFAULT_PASS=.*|RABBITMQ_DEFAULT_PASS=$rabbitmq_password|" \
  -e "s|^AI_PROVIDER=openaiWEB_PORT=8081$|AI_PROVIDER=openai|" \
  .env

if ! grep -q '^WEB_PORT=' .env; then
  printf '\nWEB_PORT=8081\n' >> .env
fi

if ! grep -q '^MIGRATION_DATABASE_URL=' .env; then
  printf '\nMIGRATION_DATABASE_URL=postgresql+asyncpg://mail_control:%s@postgres:5432/mail_control\n' "$db_password" >> .env
fi

chmod 600 .env
docker compose up -d --no-build --force-recreate \
  api worker microsoft-worker analysis-worker web >/dev/null
echo "Runtime credentials rotated and services recreated."
