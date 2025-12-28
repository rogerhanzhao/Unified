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
4. Validate services (`systemctl status ... --no-pager -l`) and check `journalctl --no-pager -n 120 -u calb-ngrok@prod -o cat`.
5. If rollback needed: `git -C /opt/calb/prod/CALB_SIZINGTOOL checkout --detach <previous-tag>` and restart services.

---

## Validation checklist
- [ ] `calb-sizingtool@prod` active and `Active: active (running)`
- [ ] `calb-ngrok@prod` active and reports a unique public URL via `curl http://127.0.0.1:4041/api/tunnels`
- [ ] Health check file present: `/opt/calb/health/calb-health.json` (recent timestamp)
- [ ] No new `ERR_NGROK_334` messages in `journalctl` logs

---

## Notes
- Never run `journalctl` without `--no-pager` in automated scripts; it will block and appear as "stuck".
- If you need help interpreting ngrok diagnostics, follow the Runbook steps above or reach out and I can assist.
