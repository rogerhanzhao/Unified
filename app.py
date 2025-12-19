from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Callable, Dict, Optional

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    os.chdir(PROJECT_ROOT)
except OSError:
    pass

PAGE_MODULES: Dict[str, str] = {
    "DC Sizing": "pages.dc_sizing_page",
    "AC Block Sizing": "pages.ac_sizing_page",
}

st.set_page_config(page_title="CALB ESS Sizing Tool", layout="wide")
st.sidebar.title("Navigation")
selected_page = st.sidebar.radio("Select a page", list(PAGE_MODULES.keys()))


def load_page_renderer(module_path: str) -> Optional[Callable[[], None]]:
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        st.error(f"Unable to import page module '{module_path}': {exc}")
        return None
    except Exception as exc:  # pragma: no cover - defensive UI feedback
        st.error(f"Unexpected error while importing '{module_path}': {exc}")
        return None

    render_fn = getattr(module, "render", None)
    if not callable(render_fn):
        st.error(f"Page module '{module_path}' does not define a callable render()")
        return None

    return render_fn


renderer = load_page_renderer(PAGE_MODULES[selected_page])
if renderer:
    try:
        renderer()
    except Exception as exc:  # pragma: no cover - defensive UI feedback
        st.error(f"Error while rendering '{selected_page}': {exc}")
