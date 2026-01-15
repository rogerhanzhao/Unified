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

import json
from pathlib import Path
from typing import Any, Dict

PREFS_FILE = Path("user_preferences.json")

def load_preferences() -> Dict[str, Any]:
    if not PREFS_FILE.exists():
        return {}
    try:
        return json.loads(PREFS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_preferences(prefs: Dict[str, Any]) -> None:
    current = load_preferences()
    current.update(prefs)
    PREFS_FILE.write_text(json.dumps(current, indent=2, sort_keys=True), encoding="utf-8")

def get_preference(key: str, default: Any = None) -> Any:
    prefs = load_preferences()
    return prefs.get(key, default)
