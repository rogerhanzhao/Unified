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

from __future__ import annotations

from dataclasses import dataclass, field

import streamlit as st


@dataclass
class AppState:
    user_inputs_dc: dict = field(default_factory=dict)
    user_inputs_ac: dict = field(default_factory=dict)
    sizing_results_dc: dict = field(default_factory=dict)
    sizing_results_ac: dict = field(default_factory=dict)
    sizing_results_final: dict = field(default_factory=dict)
    diagram_inputs: dict = field(default_factory=dict)
    diagram_results: dict = field(default_factory=dict)
    layout_inputs: dict = field(default_factory=dict)
    layout_results: dict = field(default_factory=dict)


def _coerce_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _sync_state_dict(app_state: AppState, field: str, key: str) -> None:
    existing = st.session_state.get(key)
    if isinstance(existing, dict):
        setattr(app_state, field, existing)
    else:
        current = _coerce_dict(getattr(app_state, field))
        setattr(app_state, field, current)
        st.session_state[key] = current
        return
    st.session_state[key] = getattr(app_state, field)


def init_app_state() -> AppState:
    app_state = st.session_state.get("app_state")
    if not isinstance(app_state, AppState):
        app_state = AppState()
        st.session_state["app_state"] = app_state

    _sync_state_dict(app_state, "user_inputs_dc", "dc_inputs")
    _sync_state_dict(app_state, "user_inputs_ac", "ac_inputs")
    _sync_state_dict(app_state, "sizing_results_dc", "dc_results")
    _sync_state_dict(app_state, "sizing_results_ac", "ac_results")
    _sync_state_dict(app_state, "diagram_inputs", "diagram_inputs")
    _sync_state_dict(app_state, "diagram_results", "diagram_results")
    _sync_state_dict(app_state, "layout_inputs", "layout_inputs")
    _sync_state_dict(app_state, "layout_results", "layout_results")

    if "sizing_results_final" not in st.session_state:
        st.session_state["sizing_results_final"] = app_state.sizing_results_final
    elif isinstance(st.session_state.get("sizing_results_final"), dict):
        app_state.sizing_results_final = st.session_state["sizing_results_final"]
    else:
        st.session_state["sizing_results_final"] = app_state.sizing_results_final

    return app_state
