import os
import runpy

import streamlit as st

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


def render_ac_block_page() -> None:
    page_file = "ac_block_sizing.py"
    if not os.path.isfile(page_file):
        st.error(f"Page file not found: {page_file}")
        return

    try:
        runpy.run_path(page_file, run_name="__main__")
    except Exception as exc:
        st.error(f"Error loading AC sizing page:\n{exc}")
        raise


st.sidebar.title("Navigation")
app_nav_options = ("DC Block Sizing", "AC Block Sizing")
app_nav_default = st.session_state.get("app_nav", app_nav_options[0])
if app_nav_default not in app_nav_options:
    app_nav_default = app_nav_options[0]

nav_option = st.sidebar.radio(
    "Select View",
    app_nav_options,
    index=app_nav_options.index(app_nav_default),
    help="Choose between Stage 1–3 (DC) and Stage 4 (AC) sizing flows.",
)
st.session_state["app_nav"] = nav_option

if nav_option == "DC Block Sizing":
    render_dc_block_page("Stage 1–3 Inputs")
elif nav_option == "AC Block Sizing":
    render_ac_block_page()
