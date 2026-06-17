# Telegram Connectivity Troubleshooting

If the bot fails to start with a `TimedOut` or `NetworkError`, it usually means the bot cannot communicate with the Telegram API (`api.telegram.org`). This guide helps diagnose and resolve these connectivity issues.

## Common Causes

1. **Network Blocks/Censorship:** Telegram is actively blocked in several regions or by some ISPs.
2. **DNS Resolution Failures:** Your local DNS cannot resolve `api.telegram.org`.
3. **Firewall Rules:** Your server/system firewall is blocking outbound HTTPS requests.
4. **Proxy Misconfiguration:** You are behind a corporate proxy but haven't configured the bot to use it.
5. **Slow Internet:** Your connection is too slow and times out before the initial handshake finishes.

## Run the Diagnostics Tool

We provide a built-in diagnostic tool to test your environment. Run:

```bash
python3 diagnostics.py
```

This will automatically test:
- Local environment variables
- Basic internet connectivity
- DNS resolution for Telegram
- HTTPS access
- Bot token validity

## macOS-specific Fixes

On macOS, Python environments (especially those installed via python.org installer) sometimes lack the necessary root certificates to make HTTPS connections.

* **Fix:** Run the `Install Certificates.command` script in your Python installation directory:
  ```bash
  /Applications/Python\ 3.x/Install\ Certificates.command
  ```

## VPN / Proxy Issues

If your region blocks Telegram, you must run a VPN or route your bot's traffic through a proxy.

1. **Using a System-wide VPN:** Connect to a VPN. If `python3 diagnostics.py` passes while the VPN is on, your ISP is blocking Telegram.
2. **Using a Local SOCKS5/HTTP Proxy:** 
   If you have a proxy running locally (e.g., `http://127.0.0.1:1080`), you can configure the bot to use it by passing it to `HTTPXRequest`. Note: You will need to install `httpx[socks]` for SOCKS proxy support.

## DNS Troubleshooting

If `diagnostics.py` shows a DNS failure:
1. **Change your DNS Server:** Switch your network settings to use public DNS like Google (`8.8.8.8`) or Cloudflare (`1.1.1.1`).
2. **Flush DNS Cache:** (macOS) `sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder`

## Telegram API Testing Commands

You can manually test connectivity using standard tools:

**Test DNS:**
```bash
ping api.telegram.org
```

**Test HTTPS Connectivity & Token:**
```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getMe"
```

If `curl` works but the bot fails, ensure Python has the correct certificates and is not being blocked by a local firewall.
