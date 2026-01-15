#!/bin/sh
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

set -eu
NGROK_BIN=/usr/local/bin/ngrok
NGROK_CONFIG=${NGROK_CONFIG:-/home/calb/.config/ngrok/ngrok.yml}
INSTANCE="$1"
TUNNEL="calb-${INSTANCE}"

# Quick validation: tunnel defined
if ! grep -qE "^\s*${TUNNEL}:" "$NGROK_CONFIG"; then
  echo "ERROR: Tunnel ${TUNNEL} not defined in ${NGROK_CONFIG}" >&2
  exit 2
fi

# If the tunnel defines a hostname/subdomain, ensure no other calb-* tunnel uses same
get_field() {
  awk '/^\s*'"$1"':/ { found=1; next } /^\s*[^ ]/ { if(found) exit } found && /'"$2"':/ {gsub(/^[ \t]*/,"",$0); print $2 ":" $3; exit }' "$NGROK_CONFIG" | sed 's/[[:space:]]*:[[:space:]]*//' || true
}
HOSTNAME=$(get_field "$TUNNEL" "hostname")
SUBDOMAIN=$(get_field "$TUNNEL" "subdomain")

if [ -n "$HOSTNAME" ] || [ -n "$SUBDOMAIN" ]; then
  key="${HOSTNAME:-$SUBDOMAIN}"
  # search for other calb- tunnel with same key
  other=$(awk '/^\s*tunnels:/,EOF { if ($0 ~ /^[[:space:]]*calb-/) name=$1; if (name && $0 ~ /hostname:|subdomain:/) { gsub(/^[ \t]*/,"",$0); split($0,a,":"); val=a[2]; gsub(/^[ \t]+|^[ \t]+/,"",val); if(val == "'"$key"'") print name } }' "$NGROK_CONFIG" | sed 's/://g' | grep -v "^$TUNNEL$" || true)
  if [ -n "$other" ]; then
    echo "ERROR: tunnel ${TUNNEL} shares hostname/subdomain '${key}' with ${other}. Stop one or change their reserved domains (or enable pooling)." >&2
    exit 3
  fi
fi

# Warn if another ngrok is already running (may indicate conflict)
if pgrep -x ngrok >/dev/null 2>&1; then
  echo "NOTICE: Another ngrok process is already running; starting ${TUNNEL} may fail if that process owns the endpoint. If you see ERR_NGROK_334, stop the other endpoint or configure unique reserved domains (or enable pooling if supported by your plan)." >&2
fi

# Execngrok directly; let systemd capture logs and exit status (simpler/portable)
exec "$NGROK_BIN" start "$TUNNEL" --config "$NGROK_CONFIG" --log=stdout
