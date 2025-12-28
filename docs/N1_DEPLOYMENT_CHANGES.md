# N1 Applied Changes (2025-12-27)

- 2025-12-27 09:49: Created systemd drop-in `/etc/systemd/system/calb-ngrok@.service.d/override.conf` with:

  [Service]
  StandardOutput=journal
  StandardError=journal

  Commands executed:
  - `systemctl daemon-reload`
  - `systemctl restart calb-ngrok@prod`

  Reason: systemd warned that `StandardOutput=syslog` is obsolete and automatically upgraded to journal; this drop-in removes repeated warnings and ensures logs go to journal. This change is reversible (remove the drop-in and `systemctl daemon-reload`).


- 2025-12-27 09:57: Created `/etc/systemd/system/calb-ngrok@test.service.d/override.conf` to override ExecStart and run `ngrok start --none` for the `test` instance; reloaded daemon and started `calb-ngrok@test` to validate behaviour (service remained active).
- 2025-12-27 09:58: Created `/etc/systemd/system/calb-ngrok@prod.service.d/override.conf` to override ExecStart and run `ngrok start --none` for the `prod` instance; reloaded daemon and restarted `calb-ngrok@prod`. This ensures ngrok runs without attempting to start tunnels when the config might be invalid.

Rollback: remove the test/prod override files and run `systemctl daemon-reload && systemctl restart calb-ngrok@<instance>` (or restore earlier files), e.g. `rm /etc/systemd/system/calb-ngrok@prod.service.d/override.conf && systemctl daemon-reload && systemctl restart calb-ngrok@prod`.

- 2025-12-27 10:22: Restored `calb-ngrok@test` and `calb-ngrok@prod` to use `--all` (removed instance overrides); verified active tunnel:
  - tunnel name: `calb-prod`
  - public_url: `https://carlton-inartistic-perla.ngrok-free.dev`
  - verification: `curl -I` to public_url returned HTTP 200 from the streamlit app

Note: If there are unexpected YAML parsing errors in future, validate `/home/calb/.config/ngrok/ngrok.yml` for unsupported fields (example earlier error: `field region not found`).
---RECORD CHANGE---

- 2025-12-27 10:24: Installed health check script `/opt/calb/tools/calb_health_check.py`, created systemd `calb-health.service` and `calb-health.timer` to run check every 5 minutes; status written to `/opt/calb/health/calb-health.json` and checks logged to journal. Validated run returned OK.
