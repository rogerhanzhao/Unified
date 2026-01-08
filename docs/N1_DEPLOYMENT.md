# N1 Deployment & Runbook

## Overview
- Host: N1
- Prod app path: `/opt/calb/prod/CALB_SIZINGTOOL`
- Test app path: `/opt/calb/test/CALB_SIZINGTOOL`
- Services:
  - `calb-sizingtool@<env>.service` (streamlit app)
  - `calb-ngrok@<env>.service` (ngrok tunnel)
- ngrok config: `/home/calb/.config/ngrok/ngrok.yml`

---

## Key commands (non-interactive)
- Check systemd status without pager:
  - `systemctl status calb-sizingtool@prod calb-ngrok@prod --no-pager -l`
- Show recent logs (last 120 lines):
  - `journalctl -u calb-sizingtool@prod -u calb-ngrok@prod --no-pager -n 120 -o cat`
- Ports/processes:
  - `ss -lntp | grep -E "8511|8512|4040|4041|4042"`
- Deploy script (non-interactive): `scripts/deploy_prod.sh <tag-or-commit>`

---

## ngrok ERR_NGROK_334 — Runbook
**Symptom:** When restarting `calb-ngrok@...` you see `ERR_NGROK_334` or logs say "failed to start tunnel... stop your existing endpoint first, or start both endpoints with --pooling-enabled".

**Root causes:**
- Two ngrok processes are attempting to create endpoints that use the *same reserved hostname/subdomain*.
- Unit previously used `ngrok start --all` which tried to start every tunnel from a shared config and caused conflicts.

**Immediate remediation:**
1. Inspect the ngrok config and running tunnels:
   - `sed -n '1,240p' /home/calb/.config/ngrok/ngrok.yml`
   - `curl -s http://127.0.0.1:4040/api/tunnels | jq -r '.tunnels[] | .name + " -> " + .public_url'`
2. If duplicate reserved `hostname` or `subdomain` are present across `calb-prod` and `calb-test`, change one of them or remove the duplicate.
3. Optionally stop one environment: `systemctl stop calb-ngrok@test` (or `@prod`) and restart the desired instance.

**Prevention / best practice**
- The service now starts only a named tunnel using `calb-<instance>` (e.g., `calb-prod`, `calb-test`) via a small wrapper that verifies the tunnel exists and checks for duplicate reserved hostnames.
- If you *must* share the same reserved domain, enable pooling in ngrok per your plan and configure accordingly.

---

## How we've hardened the system
- `calb-ngrok@.service.d/override.conf` now uses `/usr/local/bin/calb-ngrok-wrapper %i` which:
  - Validates the requested tunnel exists in `/home/calb/.config/ngrok/ngrok.yml`.
  - Checks for duplicate `hostname`/`subdomain` keys across `calb-*` tunnels and fails early with a clear message.
  - Emits a clear error message when it detects `ERR_NGROK_334` in ngrok output.
- Restart policy: `Restart=on-failure`, `StartLimitIntervalSec=60`, `StartLimitBurst=5`.
- Logs go to journal; any CLI checks use `--no-pager`.

---

## Deployment & rollback checklist
1. Test branch in `/opt/calb/test/CALB_SIZINGTOOL` passes tests (unit tests / smoke).
2. Create annotated tag: `git -C /opt/calb/test/CALB_SIZINGTOOL tag -a vX.Y -m "release" <commit>` and push tags: `git -C /opt/calb/test/CALB_SIZINGTOOL push origin --tags`.
3. On prod, run: `/opt/calb/test/CALB_SIZINGTOOL/scripts/deploy_prod.sh <tag>` (non-interactive).
4. Validate services (`systemctl status ... --no-pager -l`) and check `journalctl -n 120 -u calb-ngrok@prod -o cat`.
5. If rollback needed: `git -C /opt/calb/prod/CALB_SIZINGTOOL checkout --detach <previous-tag>` and restart services.

---

## Validation checklist
- [ ] `calb-sizingtool@prod` active and `Active: active (running)`
- [ ] `calb-ngrok@prod` active and reports a unique public URL via `curl http://127.0.0.1:4041/api/tunnels`
- [ ] Health check file present: `/opt/calb/health/calb-health.json` (recent timestamp)
- [ ] No new `ERR_NGROK_334` messages in `journalctl` logs

---

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
