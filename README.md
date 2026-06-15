# subfetch-bot

subfetch-bot is a production-oriented Telegram bot for finding, downloading,
and eventually synchronizing subtitles for movies and TV shows.

This repository is currently in the bootstrap stage. Subtitle search,
download, and synchronization workflows are intentionally not implemented yet.

## Roadmap

- Telegram bot bootstrap with `/start` and `/help`
- Movie and TV metadata lookup through TMDb
- Subtitle provider integration
- Subtitle download flow
- Subtitle synchronization workflow
- Persistent user preferences and history
- Deployment-ready API and worker setup

## Current Features

- `/start` - Show the welcome message
- `/help` - Show available commands
- `/search <query>` - Resolve movie and TV show names through TMDb
- `/subtitle <query>` - Identify content through TMDb and show subtitle metadata

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
```

## Running Locally

Start the bot in polling mode:

```bash
python main.py
```

Available commands:

- `/start` - Show the welcome message
- `/help` - Show available commands
- `/search <query>` - Show the top 5 TMDb movie and TV matches
- `/subtitle <query>` - Show the top 5 OpenSubtitles matches after TMDb identification

Example searches:

```text
/search breaking bad
/search avatar
/search dark
```

Subtitle metadata search examples:

```text
/subtitle breaking bad s02e05
/subtitle avatar
/subtitle dark s01e03
```

The `/subtitle` command only searches and displays subtitle metadata in this
phase. Subtitle downloading is intentionally reserved for Phase 4.
