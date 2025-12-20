import os
import runpy

import streamlit as st

from ac_block_sizing import main as render_ac_block_sizing

if not st.session_state.get("_app_page_configured"):
    st.set_page_config(page_title="CALB ESS Sizing Tool", layout="wide")
    st.session_state["_app_page_configured"] = True
    # Keep backwards-compatible flag for downstream modules
    st.session_state["_dc_page_configured"] = True


def render_dc_block_page(nav_choice: str) -> None:
    st.session_state["dc_nav_external"] = True
    st.session_state["dc_nav"] = nav_choice

    page_file = "dc_block_sizing.py"
    if not os.path.isfile(page_file):
        st.error(f"Page file not found: {page_file}")
        return

    try:
        runpy.run_path(page_file, run_name="__main__")
    except Exception as exc:
        st.error(f"Error loading DC sizing page:\n{exc}")
        raise


st.sidebar.title("Navigation")
nav_option = st.sidebar.radio(
    "Select View",
    ("Stage 1–3 Inputs", "DC Block Sizing", "AC Block Sizing"),
    help="Switch between Stage 1–3 inputs/results and AC block sizing within a single app run.",
)

if nav_option == "AC Block Sizing":
    render_ac_block_sizing()
elif nav_option == "DC Block Sizing":
    render_dc_block_page("DC Block Results & Export")
else:
    render_dc_block_page("Stage 1–3 Inputs")
