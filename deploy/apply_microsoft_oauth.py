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
        raise SystemExit("Missing Microsoft OAuth credentials")

    env_path = Path(".env")
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    updates = {
        "MICROSOFT_CLIENT_ID": client_id,
        "MICROSOFT_CLIENT_SECRET": client_secret,
    }
    output: list[str] = []
    seen: set[str] = set()
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in updates:
            output.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            output.append(line)
    for key, value in updates.items():
        if key not in seen:
            output.append(f"{key}={value}")

    temp_path = env_path.with_suffix(".env.tmp")
    temp_path.write_text("\n".join(output) + "\n", encoding="utf-8")
    os.chmod(temp_path, 0o600)
    temp_path.replace(env_path)
    os.chmod(env_path, 0o600)
    print("MICROSOFT_OAUTH_SAVED")


if __name__ == "__main__":
    main()
