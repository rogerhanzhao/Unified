# N1 — CALB SizingTool Deployment & Runbook

> Maintainer: ops/delivery engineer handoff for N1 (Linux, systemd)

---

## 1) 概览 ✅

- Host: armbian (uname: `Linux armbian 6.12.59-ophub ... aarch64`)
- Purpose: Hosts two environments for CALB SizingTool: `test` and `prod` under `/opt/calb`.
- Expected directories:
  - `/opt/calb/test/CALB_SIZINGTOOL`
  - `/opt/calb/prod/CALB_SIZINGTOOL`
- Systemd template units in use:
  - `calb-sizingtool@.service` (instances: `prod` active, `test` inactive/disabled)
  - `calb-ngrok@.service` (instance `prod` active, `test` inactive/disabled)
- Services run as user `calb` and use `/etc/calb-sizingtool/<instance>.env` for instance env (e.g. `prod.env`, `test.env`).

---

## 2) 环境快照（采集时间：2025-12-27）

- Uptime: `09:39:16 up 8:18` (load avg: 0.57, 0.19, 0.07)
- Memory: 1.8 GiB total; ~1.0 GiB used; Swap 896 MiB (unused)
- Disk: root `/` 6.4G total, ~77% used (avail ~1.6G)
- Notable processes:
  - `calb-sizingtool@prod` main PID `1275` running `/opt/calb/prod/CALB_SIZINGTOOL/.venv/bin/python -m streamlit run app.py --server.port 8511` (user: `calb`)
  - `calb-ngrok@prod` PIDs `5642/5644` (user: `calb`)
  - VS Code server process (PID `9726`) showed high CPU in snapshot (belongs to `root` VS Code server session).

---

## 3) systemd 服务盘点 🔧

### Unit files found
- `/etc/systemd/system/calb-sizingtool@.service` (enabled template)
- `/etc/systemd/system/calb-ngrok@.service` (enabled template)

### Instances observed
| Instance | Unit name | Active | Enabled | MainPID | NRestarts | WorkingDir | User |
|---|---:|---:|---:|---:|---:|---|---|
| prod | `calb-sizingtool@prod` | active (running) | enabled | 1275 | 0 | /opt/calb/prod/CALB_SIZINGTOOL | calb |
| test | `calb-sizingtool@test` | inactive (dead) | disabled | - | 0 | /opt/calb/test/CALB_SIZINGTOOL | calb |
| prod | `calb-ngrok@prod` | active (running) | enabled | 5642 | 0 | /home/calb | calb |
| test | `calb-ngrok@test` | inactive (dead) | disabled | - | 0 | /home/calb | calb |

Notes:
- `calb-sizingtool@.service` config sets `EnvironmentFile=/etc/calb-sizingtool/%i.env` and `ExecStart` uses `${PORT}`.
- `calb-ngrok@.service` sets `Environment=NGROK_CONFIG=/home/calb/.config/ngrok/ngrok.yml` and `StandardOutput=syslog` (see suggestion to use `journal`).

---

## 4) 日志与稳定性检查 (最近 300 行 & 24 小时扫描) 📝

Summary findings:
- `calb-sizingtool@prod` logs show several `Uncaught app execution` Tracebacks originating from Streamlit usage of `st.data_editor` that raises `StreamlitValueAssignmentNotAllowedError` on `diagram_inputs.dc_blocks_table`. These are runtime UI errors — they do not crash the service (service stays active) but cause user-facing errors when certain UI actions are taken.
- `calb-ngrok@prod` logs show configuration errors earlier in the day: missing/invalid tunnels and YAML parsing issues (e.g. `field region not found in type config.v3yamlConfig` and `Your configuration file must define at least one tunnel when using --all.`). This appears to have caused repeated starts/stops around 01:21–01:25, but the service is currently active.
- System logs show many SSH failed password attempts (brute-force noise) — not directly related to app but a security note.
- No OOM or kernel OOM kills observed for CALB processes in the last 24 hours.

Key logs to inspect (examples):
- `journalctl -u calb-sizingtool@prod -n 300 --no-pager`
- `journalctl -u calb-ngrok@prod -n 300 --no-pager`

---

## 5) 端口与进程检查 🔌

- Listening sockets (relevant):
  - `0.0.0.0:8511` — streamlit (prod) process PID 1275
  - `127.0.0.1:4040` — ngrok web UI
- No conflict observed between test/prod (test instance not running). Ensure test, if enabled, uses a different PORT.
- Example inspection commands:
  - `ss -lntp | grep -E "8511|4040|streamlit|ngrok"`
  - `ps aux | egrep "streamlit|app.py|ngrok"`
  - Local health check: `curl -I http://127.0.0.1:8511` → returns `HTTP/1.1 200 OK` when healthy.

---

## 6) 目录、权限与虚拟环境 🔒

- `/opt/calb` owner: `calb:calb`, contains `test/` and `prod/` directories.
- `/opt/calb/prod/CALB_SIZINGTOOL` and `/opt/calb/test/CALB_SIZINGTOOL` exist and are owned by `calb` (mode `drwxrwxr-x` / 0775).
- `.venv` exists in both `test` and `prod`; Python in prod venv: `/opt/calb/prod/CALB_SIZINGTOOL/.venv/bin/python` → `Python 3.10.12`.
- Service user `calb` runs the service; env files under `/etc/calb-sizingtool` are owned by `root:root` with mode `rw-------` (0600) — this is acceptable; systemd reads them as root and passes to the service.

---

## 7) Git 状态检查 (test / prod) 🔀

- Both `test` and `prod` are on branch `refactor/streamlit-structure-v1` at commit `6c618bc`.
- Both show local modifications (e.g., `M requirements.txt`) and several untracked files (including `docs/`).
- **Observation / Risk**: `prod` is tracking a branch head (not a tag/fixed commit). This increases release risk (accidental upstream changes affecting prod). Recommendation: adopt release tags or fixed commit hashes for prod deployments.

Suggested safer publish workflow (short):
1. Use `test` to validate: `git fetch origin && git checkout refactor/... && git pull --ff-only` then run tests.
2. Create an annotated tag (e.g. `vYYYYMMDD-rc1`), push tag to `origin`.
3. On `prod`: `git fetch --tags && git checkout <tag>` and restart service.
4. For hotfix: revert or re-deploy previous tag.

---

## 8) systemd Unit / env file details (paths only, variables masked) 🗂️

- Unit files:
  - `/etc/systemd/system/calb-sizingtool@.service` — uses `EnvironmentFile=/etc/calb-sizingtool/%i.env` and `ExecStart` references `.venv` python and `${PORT}`.
  - `/etc/systemd/system/calb-ngrok@.service` — uses `NGROK_CONFIG=/home/calb/.config/ngrok/ngrok.yml`.
- Environment files:
  - `/etc/calb-sizingtool/prod.env` — perms: `-rw------- root:root`; variables (masked): `PORT=***MASKED***`
  - `/etc/calb-sizingtool/test.env` — perms: `-rw------- root:root`; variables (masked): `PORT=***MASKED***`

> Note: values are masked in this doc by design. Do NOT place secrets in env files; use secrets manager if needed.

---

## 9) 常用命令速查（一键检查清单）

- Service status:
  - `systemctl status calb-sizingtool@prod --no-pager`
  - `systemctl status calb-sizingtool@test --no-pager`
  - `systemctl status calb-ngrok@prod --no-pager`
- Show unit file:
  - `systemctl cat calb-sizingtool@.service --no-pager`
- Logs:
  - `journalctl -u calb-sizingtool@prod -n 300 --no-pager`
  - `journalctl -u calb-ngrok@prod -n 300 --no-pager`
  - `journalctl --since "24 hours ago" | egrep -i "Failed|error|traceback|OOM|killed"`
- Ports & processes:
  - `ss -lntp | egrep "8511|4040|streamlit|ngrok"`
  - `ps aux | egrep "streamlit|app.py|ngrok"`
- Git:
  - `cd /opt/calb/test/CALB_SIZINGTOOL && git status -sb && git log -n5 --oneline --decorate`
  - `cd /opt/calb/prod/CALB_SIZINGTOOL && git status -sb && git log -n5 --oneline --decorate`
- Env files (do not print values):
  - `ls -lah /etc/calb-sizingtool/`
  - `grep -E "^[A-Za-z_][A-Za-z0-9_]*=" /etc/calb-sizingtool/prod.env | sed 's/=.*$/=***MASKED***/'`

---

## 10) 发布流程建议（本地->GitHub->N1 test->N1 prod）

- Test deployment (non-disruptive):
  1. On N1 test: `cd /opt/calb/test/CALB_SIZINGTOOL && git fetch origin && git pull --ff-only` (avoid merge commits).
  2. (Optional) Activate venv & run smoke tests: `/opt/calb/test/CALB_SIZINGTOOL/.venv/bin/python -m pytest tests -q`.
  3. Restart service: `systemctl restart calb-sizingtool@test` (only after updating `/etc/calb-sizingtool/test.env` port if needed).
- Prod publish (recommended safe approach):
  1. Create and push a **tag** for release from verified commit (e.g., `git tag -a v20251227-1 -m "release" && git push origin v20251227-1`).
  2. On prod: `cd /opt/calb/prod/CALB_SIZINGTOOL && git fetch --tags && git checkout v20251227-1`.
  3. Restart service: `systemctl daemon-reload && systemctl restart calb-sizingtool@prod`.
  4. Verify: `systemctl status calb-sizingtool@prod` and `curl -I http://127.0.0.1:<PORT>`.
- Rollback: `git checkout <previous-tag>` and `systemctl restart ...`.

> Use `git pull --ff-only` to avoid accidental merges; if pull fails due to local changes, either commit or stash changes, or reset to remote (`git reset --hard origin/<branch>`) — exercise caution.

---

## 11) 启停与重启要点 ⚙️

- After editing unit files: `systemctl daemon-reload` first.
- Start/stop/restart/status examples:
  - `systemctl start calb-sizingtool@prod`
  - `systemctl stop calb-sizingtool@prod`
  - `systemctl restart calb-sizingtool@prod`
  - `systemctl status calb-sizingtool@prod --no-pager`

---

## 12) 常见故障排查 & 建议 🛠️

1. Streamlit crashes / raises `StreamlitValueAssignmentNotAllowedError`:
   - Reproduce and capture exact user action causing it; fix code to avoid setting the widget via `st.session_state` for that key.
   - Add error handling and better input validation.
2. `ngrok` fails to start (YAML / no tunnels):
   - Validate `/home/calb/.config/ngrok/ngrok.yml` (YAML schema and tunnels presence). Fix or set `--none` if intended.
3. Port conflict / service not reachable:
   - `ss -lntp | grep <port>` and confirm service binding; adjust `/etc/calb-sizingtool/<instance>.env` `PORT` as needed.
4. venv missing or wrong python:
   - Check `.venv` presence and python version; re-create with the same Python minor version if necessary.
5. Permissions failures:
   - Ensure directories and files under `/opt/calb` are owned by `calb:calb` and have appropriate group/others perms.
6. Memory / OOM:
   - Monitor with `top` and consider adding swap or reducing memory footprint if OOMs occur.

---

## 13) Security & Operational Notes 🔐

- Do NOT store secrets in `/etc/calb-sizingtool/*.env` in plaintext if they are sensitive; prefer a secrets manager. If present, ensure file perms are restricted (0600) and owned by `root`.
- Consider adding basic fail2ban/iptables rules to reduce SSH brute-force attempts observed in system logs.
- Recommend not to run services as `root` (current `calb` user is good).

---

## 14) Current state summary (conclusion) ✅

- `calb-sizingtool@prod`: Active/running; no automatic restarts observed (NRestarts=0); intermittent app-level Tracebacks from Streamlit (non-fatal) need code fix.
- `calb-ngrok@prod`: Active; earlier config errors around tunnels (fix expected in `/home/calb/.config/ngrok/ngrok.yml`).
- `calb-sizingtool@test` and `calb-ngrok@test` are present but disabled/inactive.

---

## 15) Change log (at time of run)

- `test` & `prod` commit: `6c618bc` on `refactor/streamlit-structure-v1`.
- Key findings: Streamlit runtime errors (data_editor session_state assignment); ngrok YAML/tunnel misconfiguration; env files exist and are masked.

---

## 16) Files & commands produced during this audit

- File generated: `docs/N1_DEPLOYMENT_RUNBOOK.md` (this file)
- Commands used in audit (examples): see section **常用命令速查** above.

---

## 17) Next steps / Recommended fixes (minimal changes) ⚠️

1. Fix ngrok config (`/home/calb/.config/ngrok/ngrok.yml`) so `--all` has at least one tunnel or change service to `ngrok start --none` if not used; minimal change: update YAML to valid schema and include tunnels.
2. Fix Streamlit `st.data_editor` usage to avoid illegal `st.session_state` assignment for the key `diagram_inputs.dc_blocks_table`.
3. Consider changing `StandardOutput=syslog` to `journal` in `calb-ngrok@.service` (run `systemctl daemon-reload` after edits).
4. Adopt tag-based prod deployment to avoid running branch head in prod.

---

### Contact / Handoff
- Owner on host: user `calb` exists and owns app files.
- If handoff needed, provide these commands and this runbook to incoming on-call.

---

*Report generated automatically from on-host inspection commands executed by ops engineer. Values that might contain secrets were masked (e.g., env values).* 
