"""Health HTTP server for Render deployment."""

import logging
import os
import threading

import uvicorn
from fastapi import FastAPI

logger = logging.getLogger(__name__)

app = FastAPI()


@app.get("/health")
def health_check():
    """Health check endpoint for Render."""
    return {"status": "ok"}


@app.get("/")
def root():
    """Root endpoint for status verification."""
    return {"service": "subfetch-bot", "status": "running"}


def run_server():
    """Run the Uvicorn server synchronously."""
    port = int(os.environ.get("PORT", "10000"))
    logger.debug("Starting health server on 0.0.0.0:%d", port)
    # log_level="warning" to avoid spamming the bot's standard logs
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


def start_health_server() -> threading.Thread:
    """Start the health HTTP server in a background daemon thread."""
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    return server_thread
