from __future__ import annotations

import runpy
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def render() -> None:
    script_path = PROJECT_ROOT / "pages" / "AC_Block_Sizing.py"
    if not script_path.exists():
        st.error(f"AC sizing script not found at {script_path}.")
        return

    try:
        runpy.run_path(str(script_path), run_name="__main__")
    except Exception as exc:  # pragma: no cover - defensive UI feedback
        st.error(f"Error while running AC sizing page: {exc}")
