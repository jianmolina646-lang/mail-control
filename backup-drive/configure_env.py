"""Provision only the required backup settings from the existing container."""
import json
import os
import subprocess
from pathlib import Path


def main() -> None:
    os.umask(0o077)
    target = Path("/home/deploy/mail-control-enterprise/.env.drive")
    if target.exists():
        print("Drive environment already exists; preserved")
        return
    result = subprocess.run(
        ["docker", "inspect", "mail-control-enterprise-enterprise-backup-1"],
        capture_output=True, text=True, check=True,
    )
    environment = dict(
        entry.split("=", 1) for entry in json.loads(result.stdout)[0]["Config"]["Env"]
        if "=" in entry
    )
    if not environment.get("BACKUP_ARCHIVE_PASSWORD"):
        raise RuntimeError("Original archive encryption key is unavailable")
    keys = ("BACKUP_ARCHIVE_PASSWORD", "BACKUP_TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID")
    # Compose env files interpolate dollar signs even within double quotes.
    content = "\n".join(
        key + "=" + json.dumps(environment[key].replace("$", "$$"))
        for key in keys if environment.get(key)
    ) + "\n"
    with target.open("x", encoding="utf-8") as destination:
        destination.write(content)
    print("Drive environment provisioned privately")


if __name__ == "__main__":
    main()
