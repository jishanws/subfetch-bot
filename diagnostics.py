import socket
import sys
from urllib.parse import urlparse

import httpx

from config import ConfigError, get_settings


def mask_token(token: str) -> str:
    if not token or len(token) < 10:
        return "***"
    return f"{token[:4]}...{token[-4:]}"


def mask_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    if parsed.password:
        return url.replace(f":{parsed.password}@", ":***@")
    return url


def run_diagnostics():
    print("Running subfetch-bot diagnostics...\n")

    # 1. Environment Variables
    print("1. Environment Variables:")
    try:
        settings = get_settings()
        token = settings.telegram_bot_token.get_secret_value()
        proxy_url = settings.proxy_url.get_secret_value() if settings.proxy_url else None
        print(f"  [OK] Configuration loaded. Bot token present: {mask_token(token)}")
        if proxy_url:
            print(f"  [OK] PROXY_URL configured: {mask_url(proxy_url)}")
        else:
            print("  [INFO] No PROXY_URL configured.")
    except ConfigError as e:
        print(f"  [FAIL] Failed to load config: {e}")
        sys.exit(1)

    # 2. Internet Connectivity
    print("\n2. Internet Connectivity:")
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=5)
        print("  [OK] Internet connectivity verified.")
    except Exception as e:
        print(f"  [FAIL] Internet connection failed: {e}")

    # 3. DNS Resolution
    print("\n3. DNS Resolution (api.telegram.org):")
    try:
        ip = socket.gethostbyname("api.telegram.org")
        print(f"  [OK] api.telegram.org resolved to {ip}")
    except socket.gaierror as e:
        print(f"  [FAIL] DNS resolution failed for api.telegram.org: {e}")

    # 4. HTTPS Access to Telegram API
    print("\n4. HTTPS Access to Telegram API:")
    try:
        with httpx.Client(proxy=proxy_url, timeout=10) as client:
            response = client.get("https://api.telegram.org/")
            # Just hitting the base URL gives a 404 or redirect, which is fine.
            print(f"  [OK] Successfully connected to Telegram API. HTTP Status: {response.status_code}")
    except httpx.RequestError as e:
        print(f"  [FAIL] Failed to reach Telegram API over HTTPS: {e}")
    except Exception as e:
        print(f"  [FAIL] Unexpected error connecting to Telegram API: {e}")

    # 5. Bot Token Validity using getMe
    print("\n5. Bot Token Validity (getMe):")
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        with httpx.Client(proxy=proxy_url, timeout=15) as client:
            response = client.get(url)
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    bot_username = data['result'].get('username')
                    print(f"  [OK] Token is valid. Bot verified as: @{bot_username}")
                else:
                    print(f"  [FAIL] Token check failed. Response: {data}")
            elif response.status_code == 401:
                print("  [FAIL] Bot token is INVALID. Telegram returned HTTP 401 Unauthorized.")
            else:
                print(f"  [FAIL] HTTP Error checking token: {response.status_code}")
    except httpx.RequestError as e:
        print(f"  [FAIL] Network error checking token: {e}")
    except Exception as e:
        print(f"  [FAIL] Unexpected error verifying bot token: {e}")


if __name__ == "__main__":
    run_diagnostics()
