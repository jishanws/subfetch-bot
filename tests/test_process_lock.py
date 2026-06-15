"""Tests for local bot process locking."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from main import clear_stale_lock, single_instance_lock


class ProcessLockTests(unittest.TestCase):
    """PID lock file behavior tests."""

    def test_invalid_stale_lock_file_is_cleaned_up(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "subfetch-bot.lock"
            lock_path.write_text("not-a-pid\n", encoding="utf-8")

            clear_stale_lock(lock_path)

            self.assertFalse(lock_path.exists())

    def test_dead_pid_lock_is_cleaned_up(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "subfetch-bot.lock"
            lock_path.write_text("12345\n", encoding="utf-8")

            with patch("main.is_pid_alive", return_value=False):
                clear_stale_lock(lock_path)

            self.assertFalse(lock_path.exists())

    def test_active_bot_pid_refuses_startup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "subfetch-bot.lock"
            lock_path.write_text("12345\n", encoding="utf-8")

            with (
                patch("main.is_pid_alive", return_value=True),
                patch(
                    "main.get_process_command",
                    return_value="/Library/Frameworks/Python.framework/Python main.py",
                ),
            ):
                with self.assertRaises(SystemExit):
                    clear_stale_lock(lock_path)

            self.assertTrue(lock_path.exists())

    def test_active_non_bot_pid_lock_is_cleaned_up(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "subfetch-bot.lock"
            lock_path.write_text("12345\n", encoding="utf-8")

            with (
                patch("main.is_pid_alive", return_value=True),
                patch("main.get_process_command", return_value="/usr/bin/python other.py"),
            ):
                clear_stale_lock(lock_path)

            self.assertFalse(lock_path.exists())

    def test_single_instance_lock_writes_pid_and_cleans_up(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "subfetch-bot.lock"

            with single_instance_lock(lock_path):
                self.assertEqual(
                    lock_path.read_text(encoding="utf-8").strip(),
                    str(os.getpid()),
                )

            self.assertFalse(lock_path.exists())


if __name__ == "__main__":
    unittest.main()
