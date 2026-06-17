# subfetch-bot

subfetch-bot is a production-oriented Telegram bot for finding, downloading,
and eventually synchronizing subtitles for movies and TV shows.

This repository is under active phased development. Subtitle search and
download are implemented; subtitle synchronization is planned for a later phase.

## Roadmap

- Telegram bot bootstrap with `/start` and `/help`
- Movie and TV metadata lookup through TMDb
- Subtitle provider integration
- Subtitle download flow
- Subtitle synchronization workflow
- Persistent user preferences and history
- Deployment-ready API and worker setup

## Current Features

- `/start` - Initialize the bot and show the welcome message
- `/help` - Show available commands
- `/search <query>` - Resolve movie and TV show names through TMDb
- `/subtitle <query>` - Identify content, show subtitle choices, and send the selected file
- Natural-language chat mode for common search and subtitle requests

## Project Structure

```text
subfetch-bot/
├── bot/
│   ├── handlers/
│   ├── services/
│   ├── models/
│   ├── utils/
│   └── __init__.py
├── tests/
├── .github/workflows/
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
├── config.py
└── main.py
```

## Installation

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Environment Setup

Copy the example environment file:

```bash
cp .env.example .env
```

Set the required values in `.env`:

```env
TELEGRAM_BOT_TOKEN=
TMDB_API_KEY=
OPENSUBTITLES_API_KEY=
GROQ_API_KEY=
PROXY_URL=
```

## Running without VPN

If Telegram is blocked in your region, running without VPN requires a working local proxy. The bot supports both HTTP and SOCKS5 proxies.

1. Ensure you have installed the requirements, which includes SOCKS5 support (`httpx[socks]`).
2. Add the `PROXY_URL` to your `.env` file. The bot will automatically route Telegram requests through it.

Example `.env` proxy configurations:
```env
# SOCKS5 proxy
PROXY_URL=socks5://127.0.0.1:1080

# SOCKS5 with authentication
PROXY_URL=socks5://user:pass@127.0.0.1:1080

# HTTP proxy
PROXY_URL=http://127.0.0.1:8080
```

## Deployment

When deploying on platforms like Render:

- **Start Command**: `python3 main.py`
- **Health URL**: `/health`

The bot automatically starts a background HTTP health server bound to `0.0.0.0:$PORT` to keep the deployment active and prevent timeout errors.

## Running Locally

Start the bot in polling mode:

```bash
python main.py
```

## How to Stop the Bot Locally

Stop any local polling process and remove the bot lock file:

```bash
scripts/stop_bot.sh
```

The bot stores its local polling PID in `/tmp/subfetch-bot.lock`. If the PID is
dead or belongs to another process, startup removes the stale lock
automatically.

Available commands:

- `/start` - Initialize the bot and show the welcome message
- `/help` - Show available commands
- `/search <query>` - Show the top 5 TMDb movie and TV matches
- `/subtitle <query>` - Show inline subtitle choices after TMDb identification

Natural-language messages are also supported. The bot uses deterministic rules
for this phase; Groq or other AI classification is not used.

Telegram sends `/start` automatically when a user presses the blue Start button.
`/start` initializes the bot; repeated `/start` calls return a short reminder
instead of repeating the full welcome text.

Example searches:

```text
/search breaking bad
/search avatar
/search dark
```

Subtitle search examples:

```text
/subtitle breaking bad s02e05
/subtitle avatar
/subtitle dark s01e03
```

Natural-language examples:

```text
interstellar subtitle
find subtitle for breaking bad season 2 episode 5
dark s01e03 english subtitle
search breaking bad
avatar 2009 subtitle
help
```

Intent rules:

- Messages containing `subtitle`, `sub`, `srt`, or `caption` search subtitles
- Messages starting with `search`, `find movie`, `movie`, `series`, or `tv`
  search TMDb titles
- `help` and `what can you do` show the help message
- Plain title-like messages default to subtitle search

Selection replies such as `1` are not processed yet. The bot replies with:

```text
Selection mode is coming soon. For now, search subtitles directly, e.g. interstellar subtitle
```

The `/subtitle` command returns inline buttons such as `English BluRay` or
`Bengali WEBRip`. Select a button to download and receive the subtitle file
directly in Telegram.

## Sync Assistant

After sending a downloaded `.srt` subtitle, the bot asks whether the timing is
correct. You can reply naturally:

```text
perfect
too fast
too slow
2s early
3s late
```

If subtitles appear too early or too fast, the bot delays them. If subtitles
appear too late or too slow, the bot shifts them earlier and sends a corrected
`.synced.srt` file.

Supported subtitle file types:

- `.srt`
- `.ass`
- `.sub`

Downloads are locally rate-limited per Telegram user. Temporary files are
removed after each upload attempt.
