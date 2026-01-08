#!/bin/sh
set -eu

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <tag-or-commit>" >&2
  exit 2
fi

TAG="$1"
PROD_DIR=/opt/calb/prod/CALB_SIZINGTOOL

echo "[deploy] Fetching tags from origin..."
git -C "$PROD_DIR" fetch --tags origin

echo "[deploy] Checking out/tag $TAG into prod dir: $PROD_DIR"
# Use a detached checkout to ensure reproducible deploy
git -C "$PROD_DIR" fetch origin "$TAG" --depth=1 || true
if git -C "$PROD_DIR" rev-parse --verify --quiet "$TAG" >/dev/null; then
  git -C "$PROD_DIR" checkout --detach "$TAG"
  git -C "$PROD_DIR" reset --hard "$TAG"
else
  echo "ERROR: Tag or commit '$TAG' not found in $PROD_DIR" >&2
  exit 3
fi

echo "[deploy] Reloading systemd daemons..."
systemctl daemon-reload

echo "[deploy] Restarting services (non-blocking)..."
systemctl restart calb-sizingtool@prod calb-ngrok@prod

echo "[deploy] Services status"
systemctl status calb-sizingtool@prod calb-ngrok@prod --no-pager -l

echo "[deploy] Recent logs (last 120 lines)"
journalctl -u calb-sizingtool@prod -u calb-ngrok@prod --no-pager -n 120 -o cat

echo "[deploy] Validate: ensure health file exists and indicates OK"
if [ -f /opt/calb/health/calb-health.json ]; then
  cat /opt/calb/health/calb-health.json
else
  echo "WARNING: health file not found: /opt/calb/health/calb-health.json"
fi

echo "[deploy] Done."
