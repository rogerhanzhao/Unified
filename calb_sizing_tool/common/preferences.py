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
