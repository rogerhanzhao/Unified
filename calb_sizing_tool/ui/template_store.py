import json
from pathlib import Path
from typing import Optional, Dict, Any

TEMPLATES_DIR = Path("data/runtime/templates")

# Files used by the system
SLD_FILE = TEMPLATES_DIR / "active_sld.fabric.json"
LAYOUT_FILE = TEMPLATES_DIR / "active_site_layout.fabric.json"
META_FILE = TEMPLATES_DIR / "active_meta.json"


def _ensure_dirs():
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)


def save_active(diagram_type: str, fabric_json: Dict[str, Any], preview_svg: Optional[str] = None,
                preview_png_path: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> None:
    """
    Persist the active manual template for later use by SLD/Site Layout pages.
    diagram_type: "sld" or "layout"
    preview_*: optional file paths for quick previews
    """
    _ensure_dirs()
    target = SLD_FILE if diagram_type.lower().startswith("sld") else LAYOUT_FILE
    with target.open("w", encoding="utf-8") as f:
        json.dump(fabric_json, f, indent=2)
    existing_meta: Dict[str, Any] = {}
    if META_FILE.exists():
        try:
            existing_meta = json.loads(META_FILE.read_text())
        except Exception:
            existing_meta = {}
    new_meta = existing_meta or {}
    new_meta[diagram_type] = {
        "override": True,
        "preview_svg": preview_svg,
        "preview_png_path": preview_png_path,
    }
    META_FILE.write_text(json.dumps(new_meta, indent=2))


def load_active(diagram_type: str) -> Optional[Dict[str, Any]]:
    _ensure_dirs()
    target = SLD_FILE if diagram_type.lower().startswith("sld") else LAYOUT_FILE
    if not target.exists():
        return None
    try:
        data = json.loads(target.read_text())
    except Exception:
        return None
    # Add meta
    meta_all = {}
    if META_FILE.exists():
        try:
            meta_all = json.loads(META_FILE.read_text())
        except Exception:
            meta_all = {}
    if isinstance(meta_all.get(diagram_type), dict):
        data.setdefault("__meta__", meta_all.get(diagram_type))
    return data


def meta_active(diagram_type: str) -> Dict[str, Any]:
    _ensure_dirs()
    if META_FILE.exists():
        try:
            return json.loads(META_FILE.read_text())
        except Exception:
            return {}
    return {}


def clear_active(diagram_type: str) -> None:
    _ensure_dirs()
    target = SLD_FILE if diagram_type.lower().startswith("sld") else LAYOUT_FILE
    if target.exists():
        try:
            target.unlink()
        except Exception:
            pass
    meta = meta_active(diagram_type)
    if diagram_type in meta:
        meta.pop(diagram_type, None)
        META_FILE.write_text(json.dumps(meta, indent=2))
