import json
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from calb_sizing_tool.sld.jp_pro_renderer import render_jp_pro_svg
from calb_sizing_tool.sld.snapshot_single_unit import (
    build_single_unit_snapshot,
    validate_single_unit_snapshot,
)
from calb_sizing_tool.ui.sld_inputs import render_electrical_inputs


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def show():
    st.header("SLD Pro (English JP Style)")
    st.caption("Deterministic JP-style SLD with fixed layout for delivery.")

    stage13_output = st.session_state.get("stage13_output", {}) or {}
    ac_output = st.session_state.get("ac_output", {}) or {}
    dc_summary = st.session_state.get("dc_result_summary", {}) or {}

    scenario_default = stage13_output.get("selected_scenario", "container_only")
    scenario_id = st.text_input("Scenario ID", value=scenario_default)

    stored_inputs = st.session_state.get("sld_pro_jp_inputs", {}) or {}

    site_ac_block_total = int(ac_output.get("num_blocks") or ac_output.get("ac_blocks_total") or 0)
    site_dc_block_total = int(stage13_output.get("dc_block_total_qty") or 0)
    if site_dc_block_total <= 0:
        site_dc_block_total = int(stage13_output.get("container_count") or 0) + int(
            stage13_output.get("cabinet_count") or 0
        )
    if site_dc_block_total <= 0:
        dc_block = dc_summary.get("dc_block") if isinstance(dc_summary, dict) else None
        if dc_block is not None:
            site_dc_block_total = int(getattr(dc_block, "count", 0))

    ratio_default = None
    if site_ac_block_total > 0 and site_dc_block_total > 0:
        ratio_default = max(1, round(site_dc_block_total / site_ac_block_total))

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

    st.subheader("Diagram Scope")
    scope_options = ["one_ac_block_group", "site_summary"]
    scope_default = stored_inputs.get("diagram_scope")
    scope_index = 0
    if scope_default in scope_options:
        scope_index = scope_options.index(scope_default)
    diagram_scope = st.selectbox(
        "Scope",
        scope_options,
        index=scope_index,
        help="Default shows one AC block group to avoid misreading site totals.",
    )

    use_site_ratio_default = bool(stored_inputs.get("use_site_ratio"))
    use_site_ratio = st.checkbox(
        "Use site ratio for DC blocks per AC block group",
        value=use_site_ratio_default,
        help="Uses site totals (DC/AC) to estimate blocks per AC block group.",
    )

    default_dc_blocks_group = stored_inputs.get("dc_blocks_for_one_ac_block_group")
    if default_dc_blocks_group is None:
        if use_site_ratio and ratio_default:
            default_dc_blocks_group = ratio_default
        else:
            default_dc_blocks_group = 4

    dc_blocks_for_one_ac_block_group = st.number_input(
        "DC blocks per AC block group",
        min_value=1,
        value=int(default_dc_blocks_group),
        step=1,
        help=f"Site ratio estimate: {ratio_default}" if ratio_default else "Default is 4 (one per feeder).",
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
            "diagram_scope": diagram_scope,
            "dc_blocks_for_one_ac_block_group": dc_blocks_for_one_ac_block_group,
            "use_site_ratio": use_site_ratio,
            "site_ac_block_total": site_ac_block_total,
            "site_dc_block_total": site_dc_block_total,
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

    generate = st.button("Generate JP Pro SLD")

    sld_inputs = {
        "mv_nominal_kv_ac": mv_kv,
        "pcs_lv_voltage_v_ll": pcs_lv_v,
        "transformer_rating_mva": transformer_rating_mva,
        "pcs_rating_each_kva": pcs_rating_each_kva,
        "dc_block_energy_mwh": dc_block_energy_mwh,
        "dc_blocks_by_feeder": dc_blocks_by_feeder,
        "diagram_scope": diagram_scope,
        "dc_blocks_for_one_ac_block_group": dc_blocks_for_one_ac_block_group,
        "use_site_ratio": use_site_ratio,
        "site_ac_block_total": site_ac_block_total,
        "site_dc_block_total": site_dc_block_total,
        **electrical_inputs,
    }
    st.session_state["sld_pro_jp_inputs"] = sld_inputs

    if generate:
        try:
            snapshot = build_single_unit_snapshot(
                stage13_output, ac_output, dc_summary, sld_inputs, scenario_id
            )
            validate_single_unit_snapshot(snapshot)

            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                pro_svg_path = tmp_path / "sld_pro_en.svg"
                render_jp_pro_svg(snapshot, pro_svg_path)

                st.session_state["sld_pro_jp_svg_bytes"] = pro_svg_path.read_bytes()
                st.session_state["sld_pro_jp_snapshot_json"] = json.dumps(
                    snapshot, indent=2, sort_keys=True
                )
        except Exception as exc:
            st.error(f"SLD Pro generation failed: {exc}")
            return

        st.success("SLD Pro SVG generated.")

    pro_svg_bytes = st.session_state.get("sld_pro_jp_svg_bytes")
    if pro_svg_bytes:
        st.subheader("Preview")
        st.components.v1.html(pro_svg_bytes.decode("utf-8"), height=720, scrolling=True)

        st.subheader("Downloads")
        st.download_button(
            "Download snapshot.json",
            st.session_state.get("sld_pro_jp_snapshot_json", ""),
            "sld_single_unit_snapshot.json",
            "application/json",
        )
        st.download_button(
            "Download sld_pro_en.svg",
            st.session_state.get("sld_pro_jp_svg_bytes"),
            "sld_pro_en.svg",
            "image/svg+xml",
        )
