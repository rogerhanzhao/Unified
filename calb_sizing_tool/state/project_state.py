import datetime
import uuid

import streamlit as st

from calb_sizing_tool.state.session_state import init_shared_state


def _default_diagram_state() -> dict:
    return {"generated_from_ac_run_id": None, "svg": None, "png": None, "meta": {}}


def init_project_state() -> None:
    init_shared_state()
    state = st.session_state.setdefault("project_state", {})

    inputs = state.setdefault("inputs", {})
    inputs.setdefault("poi_freq_hz", None)
    inputs.setdefault("mv_kv", None)
    inputs.setdefault("lv_v", None)
    inputs.setdefault("project_name", None)
    inputs.setdefault("poi_power_mw", None)
    inputs.setdefault("poi_energy_mwh", None)
    inputs.setdefault("layout", {})
    layout_inputs = inputs.get("layout", {})
    if isinstance(layout_inputs, dict):
        layout_inputs.setdefault("dc_to_dc_clearance_m", None)
        layout_inputs.setdefault("dc_to_ac_clearance_m", None)
        layout_inputs.setdefault("perimeter_clearance_m", None)
    else:
        inputs["layout"] = {
            "dc_to_dc_clearance_m": None,
            "dc_to_ac_clearance_m": None,
            "perimeter_clearance_m": None,
        }

    dc_state = state.setdefault("dc", {})
    dc_state.setdefault("run_id", None)
    dc_state.setdefault("results", {})

    ac_state = state.setdefault("ac", {})
    ac_state.setdefault("run_id", None)
    ac_state.setdefault("results", {})

    diagrams = state.setdefault("diagrams", {})
    diagrams.setdefault("sld_pro", _default_diagram_state())
    diagrams.setdefault("layout", _default_diagram_state())


def get_project_state() -> dict:
    init_project_state()
    return st.session_state.get("project_state", {})


def _make_run_id(prefix: str) -> str:
    stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    token = uuid.uuid4().hex[:8]
    return f"{prefix}-{stamp}-{token}"


def bump_run_id_dc() -> str:
    state = get_project_state()
    run_id = _make_run_id("dc")
    state["dc"]["run_id"] = run_id
    return run_id


def bump_run_id_ac() -> str:
    state = get_project_state()
    run_id = _make_run_id("ac")
    state["ac"]["run_id"] = run_id
    return run_id
