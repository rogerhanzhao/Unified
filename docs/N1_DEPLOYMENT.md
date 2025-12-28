# N1 Deployment Guide

This guide explains how to deploy the CALB Sizing Tool with ngrok tunnelling on an N1 host without committing secrets to git.

## Prerequisites
- Ubuntu host with `systemd`
- `ngrok` binary installed at `/usr/local/bin/ngrok` (or set `NGROK_BIN`)
- Repo checked out at `/opt/calb/<env>/CALB_SIZINGTOOL` from branch `refactor/streamlit-structure-v1`
- Service environment file at `/etc/calb-sizingtool/<env>.env` containing at least `PORT=<port>` (and optional `NGROK_CONFIG`)

## Files provided in the repo
- `deploy/ngrok/ngrok.example.yml`: template for the real `ngrok.yml`. Copy to the server and fill in the authtoken/reserved domain.
- `deploy/systemd/calb-ngrok@.service`: base unit that starts the ngrok wrapper.
- `deploy/systemd/calb-ngrok@.service.d/override.conf.example`: drop-in template to set the config path and command.
- `deploy/scripts/ngrok_wrapper.sh`: wrapper that reads `NGROK_CONFIG` (default: `/home/calb/.config/ngrok/ngrok.yml`), validates inputs, and starts ngrok without leaking secrets.
- `deploy/scripts/install_ngrok_service.sh`: helper to install the wrapper and drop-in.

## Preparing ngrok configuration (server only)
1. On the server, create the config directory and copy the example:
   ```bash
   sudo -u calb mkdir -p /home/calb/.config/ngrok
   sudo cp deploy/ngrok/ngrok.example.yml /home/calb/.config/ngrok/ngrok.yml
   sudo chown calb:calb /home/calb/.config/ngrok/ngrok.yml
   ```
2. Edit `/home/calb/.config/ngrok/ngrok.yml` and set `authtoken`, `hostname` (if using a reserved domain), and any other ngrok options.
3. Keep this file **out of git**. It is already ignored via `.gitignore`.

## Installing the ngrok wrapper and systemd drop-in
1. Run the installer from the repo root:
   ```bash
   sudo ./deploy/scripts/install_ngrok_service.sh
   ```
2. Edit `/etc/systemd/system/calb-ngrok@.service.d/override.conf` if you need a non-default `NGROK_CONFIG` or extra flags.
3. Confirm the service environment file exists: `/etc/calb-sizingtool/<env>.env` with `PORT=<port>` (and optional `NGROK_CONFIG`).
4. Reload systemd (installer does this automatically):
   ```bash
   sudo systemctl daemon-reload
   ```

## Starting services
1. Start the application service (example for `prod`):
   ```bash
   sudo systemctl enable --now calb-sizingtool@prod
   ```
2. Start the ngrok tunnel for the same environment:
   ```bash
   sudo systemctl enable --now calb-ngrok@prod
   ```
3. Check status and logs:
   ```bash
   sudo systemctl status calb-ngrok@prod
   journalctl -u calb-ngrok@prod -f
   ```

## Updating from the `refactor/streamlit-structure-v1` branch (N1 runbook)
1. On the server, switch to the repo directory and update:
   ```bash
   cd /opt/calb/prod/CALB_SIZINGTOOL
   git fetch origin
   git checkout refactor/streamlit-structure-v1
   git pull --ff-only origin refactor/streamlit-structure-v1
   ```
2. Review any new example deployment files, then restart services:
   ```bash
   sudo systemctl restart calb-sizingtool@prod
   sudo systemctl restart calb-ngrok@prod
   ```

## Notes on secrets
- Do **not** commit real ngrok tokens or override files. Only `*.example.*` files are tracked.
- If a token is ever committed, rotate it immediately from the ngrok dashboard and rewrite history if necessary.
