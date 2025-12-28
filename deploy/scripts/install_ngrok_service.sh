#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="calb-ngrok@.service"
UNIT_DIR="/etc/systemd/system"
DROPIN_DIR="${UNIT_DIR}/calb-ngrok@.service.d"
REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
WRAPPER_SOURCE="${REPO_ROOT}/deploy/scripts/ngrok_wrapper.sh"
WRAPPER_TARGET="/usr/local/bin/calb-ngrok-wrapper"
OVERRIDE_EXAMPLE="${REPO_ROOT}/deploy/systemd/calb-ngrok@.service.d/override.conf.example"
NGROK_CONFIG_DEFAULT="/home/calb/.config/ngrok/ngrok.yml"

if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root (sudo) to install systemd units." >&2
  exit 1
fi

if [[ ! -f "${WRAPPER_SOURCE}" ]]; then
  echo "Wrapper script not found at ${WRAPPER_SOURCE}" >&2
  exit 2
fi

echo "Installing ngrok wrapper to ${WRAPPER_TARGET}..."
install -m 0755 "${WRAPPER_SOURCE}" "${WRAPPER_TARGET}"

if [[ ! -d "${DROPIN_DIR}" ]]; then
  echo "Creating systemd drop-in directory ${DROPIN_DIR}..."
  mkdir -p "${DROPIN_DIR}"
fi

if [[ -f "${OVERRIDE_EXAMPLE}" ]]; then
  echo "Copying drop-in example to ${DROPIN_DIR}/override.conf (edit before enabling)..."
  cp "${OVERRIDE_EXAMPLE}" "${DROPIN_DIR}/override.conf"
else
  echo "Drop-in example not found at ${OVERRIDE_EXAMPLE}" >&2
fi

if [[ ! -f "${NGROK_CONFIG_DEFAULT}" ]]; then
  echo "Reminder: create your ngrok config at ${NGROK_CONFIG_DEFAULT} before starting the service." >&2
fi

echo "Reloading systemd daemon..."
systemctl daemon-reload

echo "Installation complete. Use 'systemctl enable --now calb-ngrok@<env>' after configuring /etc/calb-sizingtool/<env>.env and ngrok.yml."
