"""Copy validated encrypted archives to Drive independently of MEGA uploads."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

ARCHIVE = re.compile(r"mail-control-enterprise-(\d{8}-\d{6})\.tar\.gz\.enc")
SOURCE = Path("/backups")
STATE = Path("/state/last-success.json")


def archive_time(name: str) -> float | None:
    match = ARCHIVE.fullmatch(name)
    if not match:
        return None
    try:
        return dt.datetime.strptime(match[1], "%Y%m%d-%H%M%S").replace(
            tzinfo=dt.UTC
        ).timestamp()
    except ValueError:
        return None


def run_rclone(*args: str) -> str:
    result = subprocess.run(
        ["rclone", *args, "--retries", "3", "--contimeout", "20s", "--timeout", "2m"],
        capture_output=True, text=True, timeout=1800, check=False,
    )
    if result.returncode:
        # Provider errors can contain identifying information. Keep logs generic.
        raise RuntimeError("Google Drive: transferencia o verificación fallida")
    return result.stdout


def verify_archive(path: Path) -> None:
    # Validate decryption and the complete gzip CRC before uploading any file.
    with subprocess.Popen(
        ["openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", "200000",
         "-in", str(path), "-pass", "env:BACKUP_ARCHIVE_PASSWORD"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    ) as decrypt:
        try:
            checked = subprocess.run(
                ["gzip", "-t"], stdin=decrypt.stdout,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600,
            )
            if decrypt.stdout:
                decrypt.stdout.close()
            code = decrypt.wait(timeout=30)
            if code or checked.returncode:
                raise RuntimeError("Archivo cifrado incompleto o inválido")
        finally:
            if decrypt.poll() is None:
                decrypt.kill()


def notify(message: str) -> None:
    token = os.environ.get("BACKUP_TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("BACKUP_TELEGRAM_CHAT_ID")
    if not token or not chat:
        return
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=urllib.parse.urlencode({"chat_id": chat, "text": message}).encode(),
    )
    try:
        with urllib.request.urlopen(request, timeout=20):
            pass
    except Exception:
        print("No se pudo enviar la alerta de backup", flush=True)


def mirror() -> None:
    if not os.environ.get("BACKUP_ARCHIVE_PASSWORD"):
        raise RuntimeError("Falta la clave de cifrado del respaldo")
    remote = os.environ.get("DRIVE_REMOTE", "")
    if remote != "mailcontrol_drive:MailControlBackups/Enterprise/Daily":
        raise RuntimeError("Destino de respaldo no permitido")
    keep = int(os.environ.get("DRIVE_KEEP_COPIES", "30"))
    if not 2 <= keep <= 365:
        raise RuntimeError("Retención fuera de rango")
    now = time.time()
    candidates = sorted(
        p for p in SOURCE.iterdir()
        if not p.is_symlink() and p.is_file() and archive_time(p.name) is not None
        and now - p.stat().st_mtime >= 60
    )
    if not candidates or now - (archive_time(candidates[-1].name) or 0) > 36 * 3600:
        raise RuntimeError("No hay un respaldo reciente: revisar generación de backups")
    previous = json.loads(STATE.read_text()) if STATE.exists() else {}
    uploaded = []
    for source in candidates:
        with tempfile.TemporaryDirectory(prefix="drive-backup-") as directory:
            snapshot = Path(directory) / source.name
            shutil.copyfile(source, snapshot)
            verify_archive(snapshot)
            run_rclone("copyto", str(snapshot), f"{remote}/{source.name}", "--checksum")
            run_rclone("check", directory, remote, "--one-way", "--include", source.name)
        uploaded.append(source.name)
    # Only apply retention after successfully verifying today's upload. Exact
    # file names in the dedicated folder prevent touching unrelated Drive data.
    names = run_rclone("lsf", remote, "--files-only", "--max-depth", "1").splitlines()
    managed = sorted(name for name in names if archive_time(name) is not None)
    if not set(uploaded).issubset(managed):
        raise RuntimeError("No se pudo confirmar el inventario remoto")
    for name in managed[:-keep]:
        if name not in uploaded:
            run_rclone("deletefile", f"{remote}/{name}", "--drive-use-trash=false")
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE.with_suffix(".tmp")
    temporary.write_text(json.dumps({"checked_at": now, "latest": uploaded[-1]}))
    temporary.replace(STATE)
    if previous.get("latest") != uploaded[-1]:
        notify("✅ Mail Control: respaldo cifrado verificado en Google Drive. " + uploaded[-1])
    print("Google Drive: respaldo cifrado verificado", flush=True)


def main() -> None:
    os.umask(0o077)
    if "--health" in sys.argv:
        try:
            status = json.loads(STATE.read_text())
            healthy = time.time() - status["checked_at"] < 3 * 3600
            healthy &= time.time() - (archive_time(status["latest"]) or 0) < 36 * 3600
        except (OSError, ValueError, KeyError, TypeError):
            healthy = False
        sys.exit(0 if healthy else 1)
    alerted = False
    while True:
        try:
            mirror()
            alerted = False
        except Exception:
            print("ERROR: respaldo Drive no verificado; revisar conexión o archivo fuente",
                  flush=True)
            if not alerted:
                notify("🔴 Mail Control: falló el respaldo adicional en Google Drive. "
                       "Revisar el servicio drive-backup.")
                alerted = True
            if "--once" in sys.argv:
                sys.exit(1)
        if "--once" in sys.argv:
            return
        time.sleep(3600)


if __name__ == "__main__":
    main()
