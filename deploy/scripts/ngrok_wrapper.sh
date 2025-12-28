#!/usr/bin/env bash
set -euo pipefail

NGROK_BIN=${NGROK_BIN:-/usr/local/bin/ngrok}
NGROK_CONFIG=${NGROK_CONFIG:-/home/calb/.config/ngrok/ngrok.yml}
LOG_LEVEL=${NGROK_LOG_LEVEL:-info}

usage() {
  cat <<USAGE
Usage: ${0##*/} http <port> [ngrok args]

Environment:
  NGROK_BIN      Path to the ngrok binary (default: ${NGROK_BIN})
  NGROK_CONFIG   Path to the ngrok configuration file (default: ${NGROK_CONFIG})
  NGROK_LOG_LEVEL  Log level passed to ngrok (default: ${LOG_LEVEL})
USAGE
}

if [[ $# -lt 2 ]]; then
  echo "[ngrok-wrapper] Missing arguments." >&2
  usage >&2
  exit 64
fi

COMMAND=$1
PORT=$2
shift 2

if [[ ${COMMAND} != "http" ]]; then
  echo "[ngrok-wrapper] Only 'http' tunnels are supported (got '${COMMAND}')." >&2
  exit 65
fi

if ! [[ ${PORT} =~ ^[0-9]+$ ]]; then
  echo "[ngrok-wrapper] Port must be numeric (got '${PORT}')." >&2
  exit 66
fi

if ! command -v "${NGROK_BIN}" >/dev/null 2>&1; then
  echo "[ngrok-wrapper] ngrok binary not found at ${NGROK_BIN}." >&2
  exit 67
fi

if [[ ! -f "${NGROK_CONFIG}" ]]; then
  echo "[ngrok-wrapper] ngrok config not found at ${NGROK_CONFIG}." >&2
  echo "Ensure the config exists on the server and contains a valid authtoken." >&2
  exit 68
fi

if ss -ltn "( sport = :${PORT} )" 2>/dev/null | grep -q "LISTEN"; then
  echo "[ngrok-wrapper] Port ${PORT} is already listening. Confirm the app is running on this port or choose a different PORT." >&2
fi

exec "${NGROK_BIN}" --config "${NGROK_CONFIG}" --log=stdout --log-level="${LOG_LEVEL}" "${COMMAND}" "${PORT}" "$@"
