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

import datetime
import uuid

import streamlit as st

from calb_sizing_tool.state.session_state import init_shared_state


def _default_diagram_state() -> dict:
    return {"generated_from_ac_run_id": None, "svg": None, "png": None, "meta": {}}


def _ensure_state_dict(state: dict, key: str, fallback: dict) -> dict:
    value = state.get(key)
    if isinstance(value, dict):
        return value
    state[key] = fallback
    return fallback


def init_project_state() -> None:
    init_shared_state()
    state = st.session_state.setdefault("project_state", {})

    dc_inputs = st.session_state.setdefault("dc_inputs", {})
    dc_results = st.session_state.setdefault("dc_results", {})
    ac_inputs = st.session_state.setdefault("ac_inputs", {})
    ac_results = st.session_state.setdefault("ac_results", {})
    diagram_inputs = st.session_state.setdefault("diagram_inputs", {})
    diagram_results = st.session_state.setdefault("diagram_results", {})
    layout_inputs = st.session_state.setdefault("layout_inputs", {})
    layout_results = st.session_state.setdefault("layout_results", {})

    st.session_state["dc_inputs"] = _ensure_state_dict(state, "dc_inputs", dc_inputs)
    st.session_state["dc_results"] = _ensure_state_dict(state, "dc_results", dc_results)
    st.session_state["ac_inputs"] = _ensure_state_dict(state, "ac_inputs", ac_inputs)
    st.session_state["ac_results"] = _ensure_state_dict(state, "ac_results", ac_results)
    st.session_state["diagram_inputs"] = _ensure_state_dict(state, "diagram_inputs", diagram_inputs)
    st.session_state["diagram_results"] = _ensure_state_dict(
        state, "diagram_outputs", diagram_results
    )
    st.session_state["layout_inputs"] = _ensure_state_dict(state, "layout_inputs", layout_inputs)
    st.session_state["layout_results"] = _ensure_state_dict(state, "layout_outputs", layout_results)

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
