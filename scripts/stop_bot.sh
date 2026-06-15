#!/usr/bin/env bash
set -euo pipefail

LOCK_FILE="/tmp/subfetch-bot.lock"

pids="$(pgrep -f "main.py" || true)"

if [[ -n "$pids" ]]; then
  while IFS= read -r pid; do
    if [[ -n "$pid" && "$pid" != "$$" ]]; then
      kill "$pid" 2>/dev/null || true
    fi
  done <<< "$pids"

  sleep 1

  while IFS= read -r pid; do
    if [[ -n "$pid" && "$pid" != "$$" ]] && kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  done <<< "$pids"
fi

rm -f "$LOCK_FILE"
