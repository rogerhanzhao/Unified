import json
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from calb_sizing_tool.sld.iidm_builder import build_network_for_single_unit
from calb_sizing_tool.sld.renderer import render_raw_svg
from calb_sizing_tool.sld.snapshot_single_unit import (
    build_single_unit_snapshot,
    validate_single_unit_snapshot,
)
from calb_sizing_tool.sld.svg_postprocess_margin import add_margins
from calb_sizing_tool.sld.svg_postprocess_raw import apply_raw_style
from calb_sizing_tool.ui.sld_inputs import render_electrical_inputs

try:
    import pypowsybl  # noqa: F401

    POWSYBL_AVAILABLE = True
except Exception:
    POWSYBL_AVAILABLE = False


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def show():
    st.header("SLD Raw V0.5")
    st.caption("Raw PowSyBl SLD with a single LV busbar and 4 feeder injections.")

    if not POWSYBL_AVAILABLE:
        st.warning("pypowsybl is not installed. Install it to enable SLD raw generation.")
        st.code("pip install pypowsybl")
        return

    stage13_output = st.session_state.get("stage13_output", {}) or {}
    ac_output = st.session_state.get("ac_output", {}) or {}
    dc_summary = st.session_state.get("dc_result_summary", {}) or {}

    scenario_default = stage13_output.get("selected_scenario", "container_only")
    scenario_id = st.text_input("Scenario ID", value=scenario_default)

    stored_inputs = st.session_state.get("sld_raw_inputs", {}) or {}

    st.subheader("Chain Parameters")
    c1, c2, c3 = st.columns(3)
    mv_kv_default = _safe_float(
        ac_output.get("grid_kv") or stage13_output.get("poi_nominal_voltage_kv"), 33.0
    )
    mv_kv = c1.number_input(
        "MV nominal voltage (kV)",
        min_value=1.0,
        value=_safe_float(stored_inputs.get("mv_nominal_kv_ac"), mv_kv_default),
        step=0.1,
    )

    pcs_lv_default = _safe_float(ac_output.get("inverter_lv_v"), 690.0)
    pcs_lv_v = c2.number_input(
        "PCS LV voltage (V_LL,rms)",
        min_value=100.0,
        value=_safe_float(stored_inputs.get("pcs_lv_voltage_v_ll"), pcs_lv_default),
        step=10.0,
    )

    transformer_mva_default = _safe_float(
        stored_inputs.get("transformer_rating_mva"), _safe_float(ac_output.get("transformer_kva"), 0.0) / 1000.0
    )
    if transformer_mva_default <= 0 and _safe_float(ac_output.get("block_size_mw"), 0.0) > 0:
        transformer_mva_default = _safe_float(ac_output.get("block_size_mw"), 5.0) / 0.9
    transformer_rating_mva = c3.number_input(
        "Transformer rating (MVA)",
        min_value=0.1,
        value=transformer_mva_default or 5.0,
        step=0.1,
    )

    d1, d2 = st.columns(2)
    pcs_rating_default = _safe_float(stored_inputs.get("pcs_rating_each_kva"), 0.0)
    if pcs_rating_default <= 0 and _safe_float(ac_output.get("block_size_mw"), 0.0) > 0:
        pcs_rating_default = _safe_float(ac_output.get("block_size_mw"), 5.0) * 1000 / 4
    pcs_rating_each_kva = d1.number_input(
        "PCS rating each (kVA)",
        min_value=0.0,
        value=pcs_rating_default or 1250.0,
        step=10.0,
    )

    dc_block_default = None
    dc_block = dc_summary.get("dc_block") if isinstance(dc_summary, dict) else None
    if dc_block is not None:
        dc_block_default = getattr(dc_block, "capacity_mwh", None)
    dc_block_energy_mwh = d2.number_input(
        "DC block energy (MWh)",
        min_value=0.0,
        value=_safe_float(stored_inputs.get("dc_block_energy_mwh"), dc_block_default or 5.106),
        step=0.001,
    )

    temp_snapshot = build_single_unit_snapshot(
        stage13_output,
        ac_output,
        dc_summary,
        {
            "mv_nominal_kv_ac": mv_kv,
            "pcs_lv_voltage_v_ll": pcs_lv_v,
            "transformer_rating_mva": transformer_rating_mva,
            "pcs_rating_each_kva": pcs_rating_each_kva,
            "dc_block_energy_mwh": dc_block_energy_mwh,
        },
        scenario_id,
    )
    dc_df = pd.DataFrame(temp_snapshot.get("dc_blocks_by_feeder", []))
    if not dc_df.empty:
        dc_df = dc_df[["feeder_id", "dc_block_count", "dc_block_energy_mwh"]]
    st.caption("DC blocks by feeder (edit if needed).")
    dc_df = st.data_editor(dc_df, use_container_width=True, num_rows="fixed")
    dc_blocks_by_feeder = dc_df.to_dict("records")

    electrical_inputs = render_electrical_inputs(stored_inputs)

    generate = st.button("Generate Raw SLD")

    sld_inputs = {
        "mv_nominal_kv_ac": mv_kv,
        "pcs_lv_voltage_v_ll": pcs_lv_v,
        "transformer_rating_mva": transformer_rating_mva,
        "pcs_rating_each_kva": pcs_rating_each_kva,
        "dc_block_energy_mwh": dc_block_energy_mwh,
        "dc_blocks_by_feeder": dc_blocks_by_feeder,
        "diagram_scope": "one_ac_block_group",
        **electrical_inputs,
    }
    st.session_state["sld_raw_inputs"] = sld_inputs

    if generate:
        try:
            snapshot = build_single_unit_snapshot(
                stage13_output, ac_output, dc_summary, sld_inputs, scenario_id
            )
            validate_single_unit_snapshot(snapshot)

            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                raw_svg_path = tmp_path / "sld_raw.svg"
                styled_svg_path = tmp_path / "sld_raw_styled.svg"
                final_svg_path = tmp_path / "sld_raw_final.svg"
                metadata_path = tmp_path / "sld_raw_metadata.json"

                network = build_network_for_single_unit(snapshot)
                render_raw_svg(
                    network,
                    container_id="SUB_MV_NODE_01",
                    out_svg=raw_svg_path,
                    out_metadata=metadata_path,
                )

                labels = snapshot.get("mv", {}).get("labels", {})
                apply_raw_style(
                    raw_svg_path,
                    styled_svg_path,
                    to_switchgear=labels.get("to_switchgear"),
                    to_other_rmu=labels.get("to_other_rmu"),
                )
                add_margins(styled_svg_path, final_svg_path, left_margin_px=140, top_margin_px=40)

                st.session_state["sld_raw_svg_bytes"] = final_svg_path.read_bytes()
                st.session_state["sld_raw_metadata_bytes"] = (
                    metadata_path.read_bytes() if metadata_path.exists() else None
                )
                st.session_state["sld_raw_snapshot_json"] = json.dumps(
                    snapshot, indent=2, sort_keys=True
                )
        except Exception as exc:
            st.error(f"Raw SLD generation failed: {exc}")
            return

        st.success("Raw SLD generated.")

    raw_svg_bytes = st.session_state.get("sld_raw_svg_bytes")
    if raw_svg_bytes:
        st.subheader("Preview")
        st.components.v1.html(raw_svg_bytes.decode("utf-8"), height=640, scrolling=True)

        st.subheader("Downloads")
        st.download_button(
            "Download snapshot.json",
            st.session_state.get("sld_raw_snapshot_json", ""),
            "sld_single_unit_snapshot.json",
            "application/json",
        )
        st.download_button(
            "Download raw.svg",
            st.session_state.get("sld_raw_svg_bytes"),
            "raw.svg",
            "image/svg+xml",
        )
        if st.session_state.get("sld_raw_metadata_bytes"):
            st.download_button(
                "Download raw_metadata.json",
                st.session_state.get("sld_raw_metadata_bytes"),
                "raw_metadata.json",
                "application/json",
            )
