from __future__ import annotations

import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "drive_mirror", Path(__file__).parents[1] / "backup-drive" / "mirror.py"
)
assert spec and spec.loader
mirror = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mirror)


class DriveBackupTests(unittest.TestCase):
    def test_only_exact_valid_archive_dates_are_managed(self):
        self.assertIsNone(mirror.archive_time("../mail-control-enterprise-20260909-073830.tar.gz.enc"))
        self.assertIsNone(mirror.archive_time("mail-control-enterprise-20269999-073830.tar.gz.enc"))
        self.assertIsNone(mirror.archive_time("private-document.pdf"))
        self.assertIsNotNone(mirror.archive_time("mail-control-enterprise-20260909-073830.tar.gz.enc"))

    def test_retention_only_after_verified_upload_and_excludes_other_files(self):
        self.exercise(fail_check=False)

    def test_failed_remote_check_never_deletes_or_marks_success(self):
        self.exercise(fail_check=True)

    def exercise(self, fail_check):
        latest = "mail-control-enterprise-20260909-073830.tar.gz.enc"
        old = "mail-control-enterprise-20260901-073830.tar.gz.enc"
        middle = "mail-control-enterprise-20260902-073830.tar.gz.enc"
        calls = []

        def rclone(*args):
            calls.append(args)
            if args[0] == "check" and fail_check:
                raise RuntimeError("simulated check failure")
            if args[0] == "lsf":
                return "\n".join([old, middle, latest, "private-document.pdf"])
            return ""

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            archive = source / latest
            archive.write_bytes(b"test encrypted snapshot")
            now = mirror.archive_time(latest) + 120
            os.utime(archive, (now - 90, now - 90))
            state = Path(directory) / "state" / "last-success.json"
            with (
                patch.object(mirror, "SOURCE", source),
                patch.object(mirror, "STATE", state),
                patch.object(time, "time", return_value=now),
                patch.object(mirror, "verify_archive"),
                patch.object(mirror, "notify"),
                patch.object(mirror, "run_rclone", side_effect=rclone),
                patch.dict(os.environ, {
                    "BACKUP_ARCHIVE_PASSWORD": "test-only",
                    "DRIVE_REMOTE": "mailcontrol_drive:MailControlBackups/Enterprise/Daily",
                    "DRIVE_KEEP_COPIES": "2",
                }),
            ):
                if fail_check:
                    with self.assertRaises(RuntimeError):
                        mirror.mirror()
                    self.assertFalse(state.exists())
                    self.assertFalse(any(call[0] == "deletefile" for call in calls))
                else:
                    mirror.mirror()
                    deletes = [call[1] for call in calls if call[0] == "deletefile"]
                    self.assertEqual(deletes, [
                        "mailcontrol_drive:MailControlBackups/Enterprise/Daily/" + old
                    ])
                    self.assertTrue(state.exists())

    def test_invalid_ciphertext_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "invalid.enc"
            archive.write_bytes(b"broken ciphertext")
            with (
                patch.dict(os.environ, {"BACKUP_ARCHIVE_PASSWORD": "test-only"}),
                self.assertRaises(RuntimeError),
            ):
                mirror.verify_archive(archive)


if __name__ == "__main__":
    unittest.main()
