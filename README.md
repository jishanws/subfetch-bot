<div id="top">

<!-- HEADER STYLE: MODERN -->
<div align="left" style="position: relative; width: 100%; height: 100%; ">

# SUBFETCH-BOT

<em><em>

<!-- BADGES -->

<em>Built with the tools and technologies:</em>

<img src="https://img.shields.io/badge/Python-3776AB.svg?style=flat-square&logo=Python&logoColor=white" alt="Python">
<img src="https://img.shields.io/badge/Telegram-2CA5E0.svg?style=flat-square&logo=Telegram&logoColor=white" alt="Telegram">
<img src="https://img.shields.io/badge/FastAPI-009688.svg?style=flat-square&logo=FastAPI&logoColor=white" alt="FastAPI">
<img src="https://img.shields.io/badge/Pydantic-E92063.svg?style=flat-square&logo=Pydantic&logoColor=white" alt="Pydantic">

</div>
</div>
<br clear="right">

---

## Table of Contents

I. [Table of Contents](#table-of-contents)<br>
II. [Overview](#overview)<br>
III. [Features](#features)<br>
IV. [Project Structure](#project-structure)<br>
V. [Getting Started](#getting-started)<br>
&nbsp;&nbsp;&nbsp;&nbsp;V.a. [Prerequisites](#prerequisites)<br>
&nbsp;&nbsp;&nbsp;&nbsp;V.b. [Installation](#installation)<br>
&nbsp;&nbsp;&nbsp;&nbsp;V.c. [Usage](#usage)<br>
&nbsp;&nbsp;&nbsp;&nbsp;V.d. [Testing](#testing)<br>
VI. [Contributing](#contributing)<br>

---

## Overview

subfetch-bot is a production-oriented Telegram bot designed for seamlessly finding, downloading, and synchronizing subtitles for movies and TV shows. It integrates seamlessly with TMDb for metadata lookup and OpenSubtitles for subtitle retrieval, offering both a structured command interface and a natural-language chat mode for an intuitive user experience.

---

## Features

- **Metadata Lookup**: Integrates with TMDb to resolve movie and TV show names accurately.
- **Subtitle Integration**: Connects to OpenSubtitles to identify, rank, and download subtitles.
- **Natural Language Chat**: Supports conversational requests for common search and subtitle queries.
- **Sync Assistant**: Interactive workflow to adjust subtitle timing directly through Telegram chats.
- **Flexible Proxy Support**: Works in regions with blocked Telegram access using SOCKS5 or HTTP proxies.

---

## Project Structure

```sh
└── subfetch-bot/
    ├── .github
    │   └── workflows
    ├── README.md
    ├── bot
    │   ├── __init__.py
    │   ├── handlers
    │   ├── health_server.py
    │   ├── models
    │   ├── services
    │   └── utils
    ├── config.py
    ├── diagnostics.py
    ├── docs
    │   └── telegram-connectivity-troubleshooting.md
    ├── main.py
    ├── requirements.txt
    ├── scripts
    │   └── stop_bot.sh
    └── tests
        ├── __init__.py
        ├── test_conversation_state_service.py
        ├── test_intent_service.py
        ├── test_main.py
        ├── test_main_handlers.py
        ├── test_opensubtitles_service.py
        ├── test_process_lock.py
        ├── test_search_handler.py
        ├── test_start_handler.py
        ├── test_subtitle_handler.py
        ├── test_subtitle_ranking_service.py
        ├── test_subtitle_sync_service.py
        ├── test_sync_intent_service.py
        ├── test_text_handler.py
        ├── test_title_resolution_service.py
        └── test_tmdb_service.py
```



---

## Getting Started

### Prerequisites

This project requires the following dependencies:

- **Programming Language:** Python
- **Package Manager:** Pip

### Installation

Build subfetch-bot from the source and install dependencies:

1. **Clone the repository:**

    ```sh
    ❯ git clone https://github.com/jishanws/subfetch-bot
    ```

2. **Navigate to the project directory:**

    ```sh
    ❯ cd subfetch-bot
    ```

3. **Install the dependencies:**

	**Using [pip](https://pypi.org/project/pip/):**

	```sh
	❯ pip install -r requirements.txt
	```

### Usage

Run the project with:

**Using [pip](https://pypi.org/project/pip/):**
```sh
python main.py
```

### Testing

Subfetch-bot uses the pytest test framework. Run the test suite with:

**Using [pip](https://pypi.org/project/pip/):**
```sh
pytest
```

---

## Contributing

Contributions are welcome! Since this is a small project, feel free to directly:

- **💬 [Join the Discussions](https://github.com/jishanws/subfetch-bot/discussions)**: Share your insights, provide feedback, or ask questions.
- **🐛 [Report Issues](https://github.com/jishanws/subfetch-bot/issues)**: Submit bugs found or log feature requests for the `subfetch-bot` project.
- **💡 [Submit Pull Requests](https://github.com/jishanws/subfetch-bot/blob/main/CONTRIBUTING.md)**: Review open PRs, and submit your own PRs.

---

<div align="right">

[![][back-to-top]](#top)

</div>


[back-to-top]: https://img.shields.io/badge/-BACK_TO_TOP-151515?style=flat-square
