#!/usr/bin/env bash
# Emite el certificado SSL inicial de Let's Encrypt para ecormecejhelizstore.com.
# Correr UNA vez, después de levantar los contenedores por primera vez.
set -euo pipefail

DOMAIN="panel.ecormecejhelizstore.com"
EMAIL="${CERTBOT_EMAIL:-admin@ecormecejhelizstore.com}"
CONF="./deploy/certbot/conf"
WWW="./deploy/certbot/www"

mkdir -p "$CONF" "$WWW"

# 1) Certificado temporal autofirmado para que nginx arranque con 443.
if [ ! -f "$CONF/live/$DOMAIN/fullchain.pem" ]; then
  echo ">> Creando certificado temporal para que nginx levante…"
  mkdir -p "$CONF/live/$DOMAIN"
  openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout "$CONF/live/$DOMAIN/privkey.pem" \
    -out "$CONF/live/$DOMAIN/fullchain.pem" \
    -subj "/CN=$DOMAIN"
fi

echo ">> Levantando proxy…"
docker compose up -d proxy

echo ">> Pidiendo certificado real a Let's Encrypt…"
docker compose run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
  --email $EMAIL -d $DOMAIN \
  --rsa-key-size 2048 --agree-tos --force-renewal --no-eff-email" certbot

echo ">> Recargando nginx con el certificado real…"
docker compose exec proxy nginx -s reload

echo ">> Listo. HTTPS activo en https://$DOMAIN"
