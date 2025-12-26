import datetime

import streamlit as st

from calb_sizing_tool.state.app_state import init_app_state


def init_shared_state() -> None:
    init_app_state()


def set_run_time(results_key: str) -> None:
    init_shared_state()
    results = st.session_state.get(results_key)
    if isinstance(results, dict):
        results["last_run_time"] = datetime.datetime.now().isoformat(timespec="seconds")
