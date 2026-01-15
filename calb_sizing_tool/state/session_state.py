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
from dataclasses import dataclass

import streamlit as st

from calb_sizing_tool.state.app_state import init_app_state


@dataclass
class DiagramOutputs:
    sld_svg: bytes | None = None
    sld_png: bytes | None = None
    sld_svg_path: str | None = None
    sld_png_path: str | None = None
    layout_svg: bytes | None = None
    layout_png: bytes | None = None
    layout_svg_path: str | None = None
    layout_png_path: str | None = None


@dataclass
class SharedState:
    dc_inputs: dict
    dc_results: dict
    ac_inputs: dict
    ac_results: dict
    diagram_outputs: DiagramOutputs
    last_run_timestamps: dict
    inputs: dict
    results: dict
    artifacts: dict
    project_name: str | None


def _ensure_dict(key: str) -> dict:
    value = st.session_state.get(key)
    if not isinstance(value, dict):
        value = {}
        st.session_state[key] = value
    return value


def _ensure_diagram_outputs() -> DiagramOutputs:
    value = st.session_state.get("diagram_outputs")
    if isinstance(value, DiagramOutputs):
        return value
    if isinstance(value, dict):
        outputs = DiagramOutputs(
            sld_svg=value.get("sld_svg"),
            sld_png=value.get("sld_png"),
            sld_svg_path=value.get("sld_svg_path"),
            sld_png_path=value.get("sld_png_path"),
            layout_svg=value.get("layout_svg"),
            layout_png=value.get("layout_png"),
            layout_svg_path=value.get("layout_svg_path"),
            layout_png_path=value.get("layout_png_path"),
        )
    else:
        outputs = DiagramOutputs()
    st.session_state["diagram_outputs"] = outputs
    return outputs


def _ensure_run_timestamps() -> dict:
    value = st.session_state.get("last_run_timestamps")
    if not isinstance(value, dict):
        value = {}
    value.setdefault("dc", None)
    value.setdefault("ac", None)
    st.session_state["last_run_timestamps"] = value
    return value


def _ensure_inputs(dc_inputs: dict, ac_inputs: dict) -> dict:
    inputs = st.session_state.get("inputs")
    if not isinstance(inputs, dict):
        inputs = {}
    inputs["dc"] = dc_inputs
    inputs["ac"] = ac_inputs
    st.session_state["inputs"] = inputs
    return inputs


def _ensure_results(dc_results: dict, ac_results: dict) -> dict:
    results = st.session_state.get("results")
    if not isinstance(results, dict):
        results = {}
    results["dc"] = dc_results
    results["ac"] = ac_results
    st.session_state["results"] = results
    return results


def _ensure_artifacts() -> dict:
    artifacts = st.session_state.get("artifacts")
    if not isinstance(artifacts, dict):
        artifacts = {}
    artifacts.setdefault("sld_png_bytes", None)
    artifacts.setdefault("sld_svg_bytes", None)
    artifacts.setdefault("sld_meta", {})
    artifacts.setdefault("layout_png_bytes", None)
    artifacts.setdefault("layout_svg_bytes", None)
    artifacts.setdefault("layout_meta", {})
    st.session_state["artifacts"] = artifacts
    return artifacts


def _resolve_project_name(dc_inputs: dict, ac_inputs: dict, dc_results: dict, ac_results: dict) -> str | None:
    name = st.session_state.get("project_name")
    if isinstance(name, str) and name.strip():
        return name
    for source in (dc_inputs, ac_inputs, dc_results, ac_results):
        if isinstance(source, dict):
            candidate = source.get("project_name")
            if isinstance(candidate, str) and candidate.strip():
                return candidate
    return None


def init_shared_state() -> SharedState:
    init_app_state()
    dc_inputs = _ensure_dict("dc_inputs")
    dc_results = _ensure_dict("dc_results")
    ac_inputs = _ensure_dict("ac_inputs")
    ac_results = _ensure_dict("ac_results")
    diagram_outputs = _ensure_diagram_outputs()
    last_run_timestamps = _ensure_run_timestamps()
    inputs = _ensure_inputs(dc_inputs, ac_inputs)
    results = _ensure_results(dc_results, ac_results)
    artifacts = _ensure_artifacts()
    project_name = _resolve_project_name(dc_inputs, ac_inputs, dc_results, ac_results)
    if project_name:
        st.session_state["project_name"] = project_name
    return SharedState(
        dc_inputs=dc_inputs,
        dc_results=dc_results,
        ac_inputs=ac_inputs,
        ac_results=ac_results,
        diagram_outputs=diagram_outputs,
        last_run_timestamps=last_run_timestamps,
        inputs=inputs,
        results=results,
        artifacts=artifacts,
        project_name=project_name,
    )


def set_run_time(results_key: str) -> None:
    state = init_shared_state()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    results = st.session_state.get(results_key)
    if isinstance(results, dict):
        results["last_run_time"] = now
        results["last_run_timestamp"] = now
    if results_key == "dc_results":
        state.last_run_timestamps["dc"] = now
    elif results_key == "ac_results":
        state.last_run_timestamps["ac"] = now
