Prerequisites & setup for Remote development

1) Create secure env files (manual step — DO NOT store tokens in the repository)
   - Place per-environment env files under /etc/calb-sizingtool/ named exactly `prod.env` and `test.env`.
   - Each file must at minimum contain PORT, e.g.:
     PORT=8501
   - Set owner root and permissions 600: `chown root:root /etc/calb-sizingtool/test.env && chmod 600 /etc/calb-sizingtool/test.env`

2) Install system packages if venv creation fails
   - On Debian/Ubuntu: `sudo apt install python3-venv python3-pip`
   - Install pytest if you want `bash tools/verify.sh` to run tests: `sudo ${REPO_PACKAGE_MANAGER} install python3-pytest` or `python3 -m pip install pytest` inside the venv.

3) Git "dubious ownership"
   - If git complains about dubious ownership, add a safe.directory entry: `git config --global --add safe.directory /opt/calb/<env>/CALB_SIZINGTOOL` (perform as the user who will run git commands).

4) Using the scripts
   - Verify (no secrets required): `bash tools/verify.sh test` then `bash tools/verify.sh prod`
   - Deploy: `bash tools/deploy.sh test` then `bash tools/deploy.sh prod`

5) Notes
   - Scripts never echo secrets or tokens. Any missing secure env files will cause the scripts to error with clear instructions.
   - Tasks for VS Code are in `.vscode/tasks.json` and run in the integrated terminal.
