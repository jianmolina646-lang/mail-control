#!/usr/bin/env bash
set -euo pipefail

cd /home/deploy/mail-control-enterprise

runtime_password="$(openssl rand -hex 32)"
role_exists="$(
  docker compose exec -T postgres psql -U mail_control -d mail_control -Atc \
    "SELECT 1 FROM pg_roles WHERE rolname = 'mail_control_runtime'"
)"

if [[ "$role_exists" == "1" ]]; then
  role_statement="ALTER ROLE"
else
  role_statement="CREATE ROLE"
fi

docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U mail_control -d mail_control \
  -c "$role_statement mail_control_runtime WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD '$runtime_password';" \
  >/dev/null

docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U mail_control -d mail_control \
  -c "GRANT CONNECT ON DATABASE mail_control TO mail_control_runtime;
      GRANT USAGE ON SCHEMA public TO mail_control_runtime;
      GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO mail_control_runtime;
      GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO mail_control_runtime;
      ALTER DEFAULT PRIVILEGES FOR ROLE mail_control IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO mail_control_runtime;
      ALTER DEFAULT PRIVILEGES FOR ROLE mail_control IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO mail_control_runtime;" \
  >/dev/null

python3 - "$runtime_password" <<'PY'
import pathlib
import sys
import urllib.parse

path = pathlib.Path(".env")
lines = path.read_text().splitlines()
old_url = next(line.split("=", 1)[1] for line in lines if line.startswith("DATABASE_URL="))
parsed = urllib.parse.urlsplit(old_url)
password = urllib.parse.quote(sys.argv[1], safe="")
host = parsed.hostname or "postgres"
port = f":{parsed.port}" if parsed.port else ""
netloc = f"mail_control_runtime:{password}@{host}{port}"
runtime_url = urllib.parse.urlunsplit(
    (parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment)
)
remaining = [
    line
    for line in lines
    if not line.startswith(("DATABASE_URL=", "SYSTEM_DATABASE_URL="))
]
path.write_text(
    f"DATABASE_URL={runtime_url}\nSYSTEM_DATABASE_URL={old_url}\n"
    + "\n".join(remaining)
    + "\n"
)
PY

chmod 600 .env
unset runtime_password

docker compose exec -T postgres psql -U mail_control -d mail_control -Atc \
  "SELECT rolname, rolsuper, rolbypassrls
   FROM pg_roles
   WHERE rolname IN ('mail_control', 'mail_control_runtime')
   ORDER BY rolname"
grep -E '^(DATABASE_URL|SYSTEM_DATABASE_URL)=' .env | cut -d= -f1
