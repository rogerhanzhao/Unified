#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Personal Open-Source Notice
#
# Copyright (c) 2026 Alex.Zhao. All rights reserved.
#
# This repository is released under the MIT License (see LICENSE file).
# Intended use: learning, evaluation, and engineering reference for Utility-scale
# BESS/ESS sizing and Reporting workflows.
#
# DISCLAIMER: This software is provided "AS IS", without warranty of any kind,
# express or implied. In no event shall the author(s) be liable for any claim,
# damages, or other liability arising from, out of, or in connection with the
# software or the use or other dealings in the software.
#
# NOTE: This is a personal project. It is not an official product or statement
# of any company or organization.
# -----------------------------------------------------------------------------

set -euo pipefail

if [ "${1:-}" = "" ]; then
  echo "Usage: $0 prod|test"
  exit 2
fi
ENV="$1"
case "$ENV" in
  prod|test) ;;
  *) echo "Invalid env: $ENV" >&2; exit 2;;
esac

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

# If git repo, show status (no auto-pull)
if [ -d ".git" ]; then
  echo "Git repository detected. Showing status (no pull performed):"
  git status --porcelain --branch || true
fi

# Ensure venv exists
if [ ! -d ".venv" ]; then
  echo "Creating python venv (.venv)"
  if [ "$(id -u)" -eq 0 ]; then
    # running as root: create venv as calb to avoid root-owned venv
    sudo -u calb bash -lc "cd '${REPO_DIR}' && python3 -m venv .venv" || { echo "Failed creating venv as calb" >&2; exit 1; }
  else
    python3 -m venv .venv
  fi
fi

PIP_BIN="${REPO_DIR}/.venv/bin/pip"
if [ -f requirements.txt ]; then
  echo "Installing requirements from requirements.txt"
  TMPERR="/tmp/pip_install_${ENV}.err"
  TMPREQ="/tmp/requirements.${ENV}.txt"
  if [ "$(id -u)" -eq 0 ]; then
    # run as calb and capture stderr
    if sudo -u calb bash -lc "cd '${REPO_DIR}' && . .venv/bin/activate && pip install -r requirements.txt" 2> "$TMPERR"; then
      :
    else
      MISSING="$(sed -n "s/.*No matching distribution found for \([^ ]\+\).*/\1/p" "$TMPERR" | tr '\n' ' ' | sed 's/ $//')"
      if [ -n "$MISSING" ]; then
        echo "Warning: the following packages have no matching distribution and will be skipped: $MISSING"
        grep -v -E "($(echo "$MISSING" | sed 's/ /|/g'))" requirements.txt > "$TMPREQ"
        echo "Retrying pip install without unavailable packages"
        sudo -u calb bash -lc "cd '${REPO_DIR}' && . .venv/bin/activate && pip install -r \"$TMPREQ\"" 2>> "$TMPERR" || { echo "Retry pip install failed (as calb)" >&2; cat "$TMPERR" >&2; exit 1; }
        rm -f "$TMPREQ"
      else
        echo "pip install failed; see $TMPERR" >&2
        cat "$TMPERR" >&2
        exit 1
      fi
    fi
  else
    if "$PIP_BIN" install -r requirements.txt 2> "$TMPERR"; then
      :
    else
      MISSING="$(sed -n "s/.*No matching distribution found for \([^ ]\+\).*/\1/p" "$TMPERR" | tr '\n' ' ' | sed 's/ $//')"
      if [ -n "$MISSING" ]; then
        echo "Warning: the following packages have no matching distribution and will be skipped: $MISSING"
        grep -v -E "($(echo "$MISSING" | sed 's/ /|/g'))" requirements.txt > "$TMPREQ"
        echo "Retrying pip install without unavailable packages"
        "$PIP_BIN" install -r "$TMPREQ" || { echo "Retry pip install failed" >&2; cat "$TMPERR" >&2; exit 1; }
        rm -f "$TMPREQ"
      else
        echo "pip install failed; see $TMPERR" >&2
        cat "$TMPERR" >&2
        exit 1
      fi
    fi
  fi
  rm -f "$TMPERR"
else
  echo "No requirements.txt found; skipping pip install"
fi

# Try optional requirements if present; failures here are non-fatal
if [ -f requirements_optional.txt ]; then
  echo "Attempting optional requirements install (non-fatal)"
  if [ "$(id -u)" -eq 0 ]; then
    if ! sudo -u calb bash -lc "cd '${REPO_DIR}' && . .venv/bin/activate && pip install -r requirements_optional.txt" 2>/tmp/pip_optional_${ENV}.err; then
      echo "Warning: optional requirements install failed; continuing. See /tmp/pip_optional_${ENV}.err for details" >&2
    fi
  else
    if ! "$PIP_BIN" install -r requirements_optional.txt 2>/tmp/pip_optional_${ENV}.err; then
      echo "Warning: optional requirements install failed; continuing. See /tmp/pip_optional_${ENV}.err for details" >&2
    fi
  fi
fi

# Restart service
echo "Restarting systemd service calb-sizingtool@${ENV}"
systemctl restart "calb-sizingtool@${ENV}"

# Read PORT from secure env file
ENVFILE="/etc/calb-sizingtool/${ENV}.env"
if [ ! -r "$ENVFILE" ]; then
  echo "Error: env file $ENVFILE missing or not readable. Please create it and ensure permissions restrict access (e.g. 600)." >&2
  exit 3
fi
PORT="$(grep -E '^PORT=' "$ENVFILE" | head -n1 | cut -d= -f2- | tr -d '"' | tr -d "'" )"
if [ -z "$PORT" ]; then
  echo "Error: PORT not defined in $ENVFILE" >&2
  exit 3
fi

# Wait for port to appear (timeout 30s)
for i in $(seq 1 30); do
  if ss -ltn | grep -q ":${PORT} \|:${PORT}$"; then
    break
  fi
  sleep 1
done

# Smoke check via curl
HTTP_LINE="$(curl -sI "http://127.0.0.1:${PORT}" | head -n 1 || true)"
if [ -z "$HTTP_LINE" ]; then
  echo "Warning: no HTTP response on 127.0.0.1:${PORT}. Check service logs with: journalctl -u calb-sizingtool@${ENV} -n 200 --no-pager" >&2
else
  echo "$HTTP_LINE"
fi

# If ngrok service exists, restart and print public URL line only
if systemctl status "calb-ngrok@${ENV}" >/dev/null 2>&1; then
  systemctl restart "calb-ngrok@${ENV}" || echo "Warning: failed restarting calb-ngrok@${ENV}" >&2
  # Extract public URL from journal (only URL, no tokens)
  URL="$(journalctl -u "calb-ngrok@${ENV}" -n 200 --no-pager | egrep -o 'https?://[A-Za-z0-9.-]+\.ngrok\.io(:[0-9]+)?' | head -n1 || true)"
  if [ -n "$URL" ]; then
    echo "$URL"
  fi
fi

echo "Deploy script completed for ${ENV}"