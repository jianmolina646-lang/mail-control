#!/usr/bin/env bash
set -euo pipefail

cd /home/deploy/mail-control-enterprise

system_password="$(openssl rand -hex 32)"
role_exists="$(
  docker compose exec -T postgres psql -U mail_control -d mail_control -Atc \
    "SELECT 1 FROM pg_roles WHERE rolname = 'mail_control_system'"
)"

if [[ "$role_exists" == "1" ]]; then
  role_statement="ALTER ROLE"
else
  role_statement="CREATE ROLE"
fi

docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U mail_control -d mail_control \
  -c "$role_statement mail_control_system WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT BYPASSRLS PASSWORD '$system_password';" \
  >/dev/null

docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U mail_control -d mail_control \
  -c "GRANT CONNECT ON DATABASE mail_control TO mail_control_system;
      GRANT USAGE ON SCHEMA public TO mail_control_system;
      GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO mail_control_system;
      GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO mail_control_system;
      ALTER DEFAULT PRIVILEGES FOR ROLE mail_control IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO mail_control_system;
      ALTER DEFAULT PRIVILEGES FOR ROLE mail_control IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO mail_control_system;" \
  >/dev/null

python3 - "$system_password" <<'PY'
import pathlib
import sys
import urllib.parse

path = pathlib.Path(".env")
lines = path.read_text().splitlines()
owner_url = next(
    line.split("=", 1)[1] for line in lines if line.startswith("SYSTEM_DATABASE_URL=")
)
parsed = urllib.parse.urlsplit(owner_url)
password = urllib.parse.quote(sys.argv[1], safe="")
host = parsed.hostname or "postgres"
port = f":{parsed.port}" if parsed.port else ""
netloc = f"mail_control_system:{password}@{host}{port}"
system_url = urllib.parse.urlunsplit(
    (parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment)
)
updated = [
    f"SYSTEM_DATABASE_URL={system_url}"
    if line.startswith("SYSTEM_DATABASE_URL=")
    else line
    for line in lines
]
path.write_text("\n".join(updated) + "\n")
PY

chmod 600 .env
unset system_password

docker compose exec -T postgres psql -U mail_control -d mail_control -Atc \
  "SELECT rolname, rolsuper, rolbypassrls
   FROM pg_roles
   WHERE rolname IN ('mail_control_runtime', 'mail_control_system')
   ORDER BY rolname"
