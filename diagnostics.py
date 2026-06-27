"""Production sanity checks for SubFetchBot."""

from __future__ import annotations

import socket
import sys
from dataclasses import dataclass

import httpx

from config import ConfigError, Settings, get_settings


TELEGRAM_API_BASE = "https://api.telegram.org"
TMDB_API_BASE = "https://api.themoviedb.org/3"
OPENSUBTITLES_API_BASE = "https://api.opensubtitles.com/api/v1"
SUBDL_API_BASE = "https://api.subdl.com/api/v1"
LOCAL_HEALTH_URL = "http://127.0.0.1:10000/health"


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def print_result(result: CheckResult) -> None:
    status = "OK" if result.ok else "FAIL"
    print(f"[{status}] {result.name}: {result.detail}")


def check_env(settings: Settings) -> list[CheckResult]:
    required = {
        "TELEGRAM_BOT_TOKEN": settings.telegram_bot_token.get_secret_value(),
        "TMDB_API_KEY": settings.tmdb_api_key.get_secret_value(),
        "OPENSUBTITLES_API_KEY": settings.opensubtitles_api_key.get_secret_value(),
        "GROQ_API_KEY": settings.groq_api_key.get_secret_value(),
    }
    optional = {
        "PROXY_URL": settings.proxy_url.get_secret_value() if settings.proxy_url else "",
        "SUBDL_API_KEY": settings.subdl_api_key.get_secret_value() if settings.subdl_api_key else "",
    }

    required_ok = all(bool(value) for value in required.values())
    required_detail = "all required values are present" if required_ok else "one or more required values are missing"
    results = [CheckResult("required env vars", required_ok, required_detail)]
    for name, value in optional.items():
        state = "present" if value else "not configured"
        results.append(CheckResult(name, True, state))
    return results


def check_dns(hostname: str) -> CheckResult:
    try:
        socket.gethostbyname(hostname)
    except OSError:
        return CheckResult(f"DNS {hostname}", False, "resolution failed")
    return CheckResult(f"DNS {hostname}", True, "resolved")


def check_telegram_token(settings: Settings, proxy_url: str | None) -> CheckResult:
    token = settings.telegram_bot_token.get_secret_value()
    try:
        with httpx.Client(proxy=proxy_url, timeout=15) as client:
            response = client.get(f"{TELEGRAM_API_BASE}/bot{token}/getMe")
    except httpx.RequestError:
        return CheckResult("Telegram token", False, "request failed")

    if response.status_code == 200 and response.json().get("ok"):
        return CheckResult("Telegram token", True, "valid")
    if response.status_code == 401:
        return CheckResult("Telegram token", False, "invalid")
    return CheckResult("Telegram token", False, f"unexpected status {response.status_code}")


def check_tmdb(settings: Settings) -> CheckResult:
    try:
        with httpx.Client(timeout=15) as client:
            response = client.get(
                f"{TMDB_API_BASE}/configuration",
                params={"api_key": settings.tmdb_api_key.get_secret_value()},
            )
    except httpx.RequestError:
        return CheckResult("TMDb", False, "request failed")

    if response.status_code == 200:
        return CheckResult("TMDb", True, "reachable")
    if response.status_code in {401, 403}:
        return CheckResult("TMDb", False, "credentials rejected")
    return CheckResult("TMDb", False, f"unexpected status {response.status_code}")


def check_opensubtitles(settings: Settings) -> CheckResult:
    try:
        with httpx.Client(timeout=15) as client:
            response = client.get(
                f"{OPENSUBTITLES_API_BASE}/infos/languages",
                headers={
                    "Api-Key": settings.opensubtitles_api_key.get_secret_value(),
                    "User-Agent": "subfetch-bot diagnostics",
                },
            )
    except httpx.RequestError:
        return CheckResult("OpenSubtitles", False, "request failed")

    if response.status_code == 200:
        return CheckResult("OpenSubtitles", True, "reachable")
    if response.status_code in {401, 403}:
        return CheckResult("OpenSubtitles", False, "credentials rejected")
    return CheckResult("OpenSubtitles", False, f"unexpected status {response.status_code}")


def check_subdl(settings: Settings) -> CheckResult:
    if not settings.subdl_api_key:
        return CheckResult("SubDL", True, "not configured")

    try:
        with httpx.Client(timeout=15) as client:
            response = client.get(
                f"{SUBDL_API_BASE}/subtitles",
                params={
                    "api_key": settings.subdl_api_key.get_secret_value(),
                    "film_name": "test",
                    "languages": "EN",
                },
            )
    except httpx.RequestError:
        return CheckResult("SubDL", False, "request failed")

    if response.status_code == 200:
        return CheckResult("SubDL", True, "reachable")
    if response.status_code in {401, 403}:
        return CheckResult("SubDL", False, "credentials rejected")
    return CheckResult("SubDL", False, f"unexpected status {response.status_code}")


def check_local_health() -> CheckResult:
    try:
        with httpx.Client(timeout=3) as client:
            response = client.get(LOCAL_HEALTH_URL)
    except httpx.RequestError:
        return CheckResult("local health endpoint", True, "not running locally")

    if response.status_code == 200:
        return CheckResult("local health endpoint", True, "reachable")
    return CheckResult("local health endpoint", False, f"unexpected status {response.status_code}")


def run_diagnostics() -> int:
    print("Running SubFetchBot diagnostics...\n")

    try:
        settings = get_settings()
    except ConfigError as exc:
        print_result(CheckResult("configuration", False, str(exc)))
        return 1

    proxy_url = settings.proxy_url.get_secret_value() if settings.proxy_url else None
    checks = [
        *check_env(settings),
        check_dns("api.telegram.org"),
        check_telegram_token(settings, proxy_url),
        check_tmdb(settings),
        check_opensubtitles(settings),
        check_subdl(settings),
        check_local_health(),
    ]

    for result in checks:
        print_result(result)

    return 0 if all(result.ok for result in checks) else 1


if __name__ == "__main__":
    sys.exit(run_diagnostics())
