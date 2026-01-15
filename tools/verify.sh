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

# Quick syntax check
echo "Running python syntax check (compileall)"
python3 -m compileall . >/dev/null || { echo "PYTHON SYNTAX CHECK: FAIL"; exit 1; }

echo "PYTHON SYNTAX CHECK: OK"

# Optional tests
if [ -d "tests" ]; then
  if command -v pytest >/dev/null 2>&1; then
    echo "Running pytest -q"
    pytest -q || { echo "TESTS: FAIL"; exit 1; }
    echo "TESTS: OK"
  else
    echo "pytest not installed; skipping tests"
  fi
fi

# Service active check
SERVICE_STATUS="$(systemctl is-active "calb-sizingtool@${ENV}" 2>&1 || true)"
if [ "$SERVICE_STATUS" = "active" ]; then
  SERVICE_OK=1
else
  SERVICE_OK=0
fi

envfile="/etc/calb-sizingtool/${ENV}.env"
if [ ! -r "$envfile" ]; then
  echo "ERROR: missing or unreadable env file $envfile" >&2
  exit 3
fi
PORT="$(grep -E '^PORT=' "$envfile" | head -n1 | cut -d= -f2- | tr -d '"' | tr -d "'" )"
if [ -z "$PORT" ]; then
  echo "ERROR: PORT not defined in $envfile" >&2
  exit 3
fi

HTTP_LINE="$(curl -sI "http://127.0.0.1:${PORT}" | head -n 1 || true)"

# Summary
echo "SUMMARY: env=${ENV}"
if [ "$SERVICE_OK" -eq 1 ]; then
  echo " - service: active"
else
  echo " - service: not-active"
fi
if [ -n "$HTTP_LINE" ]; then
  echo " - http: ${HTTP_LINE}"
else
  echo " - http: no response on 127.0.0.1:${PORT}"
fi

if [ "$SERVICE_OK" -eq 1 ] && [ -n "$HTTP_LINE" ]; then
  echo "OK"
  exit 0
else
  echo "FAIL"
  exit 4
fi