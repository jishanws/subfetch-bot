"""Telegram bot entry point."""

from contextlib import contextmanager
import logging
import os
from pathlib import Path
import signal
import subprocess
from typing import Iterator

from telegram.ext import Application, ApplicationBuilder

from bot.handlers import register_handlers
from config import get_settings

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
BOT_LOCK_PATH = Path("/tmp/subfetch-bot.lock")


def create_application(token: str) -> Application:
    """Create and configure the Telegram application."""
    application = ApplicationBuilder().token(token).build()
    register_handlers(application)
    return application


def main() -> None:
    """Run the bot in polling mode."""
    settings = get_settings()
    token = settings.telegram_bot_token.get_secret_value()

    with single_instance_lock():
        install_shutdown_handlers()
        application = create_application(token)

        logger.info("Starting subfetch-bot in polling mode.")
        application.run_polling()


@contextmanager
def single_instance_lock(lock_path: Path = BOT_LOCK_PATH) -> Iterator[None]:
    """Prevent multiple polling processes from using the same Telegram bot token."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    clear_stale_lock(lock_path)
    write_lock_pid(lock_path)

    try:
        yield
    finally:
        remove_lock_file(lock_path)


def clear_stale_lock(lock_path: Path = BOT_LOCK_PATH) -> None:
    """Remove stale lock files and reject an active bot process."""
    if not lock_path.exists():
        return

    lock_pid = read_lock_pid(lock_path)
    if lock_pid is None:
        logger.info("Removing stale bot lock with invalid PID: %s", lock_path)
        remove_lock_file(lock_path)
        return

    if not is_pid_alive(lock_pid):
        logger.info("Removing stale bot lock for dead PID %s.", lock_pid)
        remove_lock_file(lock_path)
        return

    command = get_process_command(lock_pid)
    if "main.py" in command:
        logger.error(
            "Another subfetch-bot process is already running with PID %s: %s",
            lock_pid,
            command,
        )
        raise SystemExit(1)

    logger.info(
        "Removing stale bot lock for PID %s because it is not this bot: %s",
        lock_pid,
        command or "<unknown command>",
    )
    remove_lock_file(lock_path)


def read_lock_pid(lock_path: Path = BOT_LOCK_PATH) -> int | None:
    """Read the PID stored in the bot lock file."""
    try:
        return int(lock_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def write_lock_pid(lock_path: Path = BOT_LOCK_PATH) -> None:
    """Write the current process PID to the bot lock file."""
    lock_path.write_text(f"{os.getpid()}\n", encoding="utf-8")


def remove_lock_file(lock_path: Path = BOT_LOCK_PATH) -> None:
    """Remove the bot lock file if it exists."""
    try:
        lock_path.unlink()
    except FileNotFoundError:
        return


def is_pid_alive(pid: int) -> bool:
    """Return whether a PID currently exists."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def get_process_command(pid: int) -> str:
    """Return the process command for a PID."""
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def handle_shutdown_signal(signum: int, _frame: object) -> None:
    """Remove the lock file before exiting on local shutdown signals."""
    logger.info("Received shutdown signal %s; removing bot lock.", signum)
    remove_lock_file()
    raise SystemExit(0)


def install_shutdown_handlers() -> None:
    """Install shutdown handlers for local bot runs."""
    signal.signal(signal.SIGINT, handle_shutdown_signal)
    signal.signal(signal.SIGTERM, handle_shutdown_signal)


if __name__ == "__main__":
    main()
