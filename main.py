"""Telegram bot entry point."""

from contextlib import contextmanager
import logging
import os
from pathlib import Path
import signal
import subprocess
import sys
from typing import Iterator
from urllib.parse import urlparse

from telegram.error import InvalidToken, TimedOut, NetworkError
from telegram.ext import Application, ApplicationBuilder
from telegram.request import HTTPXRequest

from bot.handlers import register_handlers
from bot.health_server import start_health_server
from config import get_settings

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
BOT_LOCK_PATH = Path("/tmp/subfetch-bot.lock")


def mask_token(token: str) -> str:
    """Mask the bot token for safe logging."""
    if not token or len(token) < 10:
        return "***"
    return f"{token[:4]}...{token[-4:]}"


def mask_url(url: str) -> str:
    """Mask password in URL for safe logging."""
    if not url:
        return ""
    parsed = urlparse(url)
    if parsed.password:
        return url.replace(f":{parsed.password}@", ":***@")
    return url


def mask_proxy_host(url: str) -> str:
    """Return a log-safe proxy endpoint without credentials."""
    parsed = urlparse(url)
    if not parsed.hostname:
        return mask_url(url)

    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if parsed.port:
        host = f"{host}:{parsed.port}"
    if parsed.scheme:
        return f"{parsed.scheme}://{host}"
    return host


def create_application(token: str, proxy_url: str | None = None) -> Application:
    """Create and configure the Telegram application."""
    request = HTTPXRequest(
        proxy=proxy_url if proxy_url else None,
        connection_pool_size=8,
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0,
    )
    application = (
        ApplicationBuilder()
        .token(token)
        .request(request)
        .get_updates_request(request)
        .build()
    )
    register_handlers(application)
    return application


def main() -> None:
    """Run the bot in polling mode."""
    try:
        settings = get_settings()
    except Exception as e:
        logger.error("Startup failed: Configuration error: %s", e)
        sys.exit(1)

    token = settings.telegram_bot_token.get_secret_value()
    proxy_url = settings.proxy_url.get_secret_value() if settings.proxy_url else None

    with single_instance_lock():
        install_shutdown_handlers()
        application = create_application(token, proxy_url)

        logger.info("Bot token loaded successfully: %s", mask_token(token))
        if proxy_url:
            logger.info("Using Telegram proxy: %s", mask_proxy_host(proxy_url))
        else:
            logger.info("No PROXY_URL configured. Telegram will connect directly.")
        logger.info("Attempting to connect to Telegram API...")
        logger.info("Starting subfetch-bot in polling mode.")

        start_health_server()

        try:
            application.run_polling()
        except InvalidToken:
            logger.error("Startup failed: Invalid bot token provided. Check your TELEGRAM_BOT_TOKEN in .env.")
            sys.exit(1)
        except TimedOut:
            logger.error("Startup failed: Connection to Telegram API timed out.")
            logger.error("This usually means api.telegram.org is unreachable from your network, proxy issues, or DNS failures.")
            logger.error("Run `python3 diagnostics.py` to troubleshoot.")
            sys.exit(1)
        except NetworkError as e:
            logger.error("Startup failed: A network error occurred while connecting to Telegram API: %s", e)
            logger.error("Run `python3 diagnostics.py` to troubleshoot.")
            sys.exit(1)
        except Exception as e:
            logger.error("Startup failed: An unexpected error occurred during polling: %s", e)
            sys.exit(1)


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
