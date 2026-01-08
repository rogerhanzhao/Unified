#!/usr/bin/env bash
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