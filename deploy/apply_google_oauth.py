from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> None:
    payload = json.load(sys.stdin)
    client_id = str(payload.get("client_id", "")).strip()
    client_secret = str(payload.get("client_secret", "")).strip()
    if not client_id or not client_secret:
        raise SystemExit("Google OAuth credentials are incomplete")

    env_path = Path(".env")
    values = {
        "GOOGLE_CLIENT_ID": client_id,
        "GOOGLE_CLIENT_SECRET": client_secret,
    }
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    output: list[str] = []
    replaced: set[str] = set()

    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in values:
            output.append(f"{key}={values[key]}")
            replaced.add(key)
        else:
            output.append(line)

    for key, value in values.items():
        if key not in replaced:
            output.append(f"{key}={value}")

    temporary = env_path.with_suffix(".env.tmp")
    temporary.write_text("\n".join(output) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(env_path)
    os.chmod(env_path, 0o600)
    print("GOOGLE_OAUTH_SAVED")


if __name__ == "__main__":
    main()
