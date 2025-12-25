import json
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from calb_sizing_tool.sld import (
    apply_pro_template,
    build_iidm_network_from_chain_snapshot,
    build_sld_chain_snapshot_v2,
    render_pow_sybl_svg,
    validate_snapshot_chain_v2,
)

try:
    import pypowsybl  # noqa: F401

    POWSYBL_AVAILABLE = True
except Exception:
    POWSYBL_AVAILABLE = False


def _safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _default_value(store: dict, key: str, fallback):
    value = store.get(key)
    return fallback if value is None else value


def show():
    st.header("SLD Generator Pro (Engineering)")
    st.caption("Generates a monochrome single-chain SLD (RMU -> TR -> 1 AC block with 4 feeders).")

    if not POWSYBL_AVAILABLE:
        st.warning("pypowsybl is not installed. Install it to enable SLD Pro generation.")
        st.code("pip install pypowsybl")
        return

    stage13_output = st.session_state.get("stage13_output", {}) or {}
    ac_output = st.session_state.get("ac_output", {}) or {}
    dc_summary = st.session_state.get("dc_result_summary", {}) or {}

    if not stage13_output:
        st.warning("Stage 1-3 sizing data not found. Defaults will be used.")
    if not ac_output:
        st.warning("AC sizing data not found. Defaults will be used.")

    scenario_default = stage13_output.get("selected_scenario", "container_only")
    scenario_id = st.text_input("Scenario ID", value=scenario_default)

    stored_inputs = st.session_state.get("sld_pro_inputs", {}) or {}
    if not stored_inputs:
        stage_saved = ac_output.get("sld_electrical_inputs") or stage13_output.get(
            "sld_electrical_inputs"
        )
        if isinstance(stage_saved, dict):
            stored_inputs = stage_saved

    st.subheader("Chain Parameters")
    c1, c2, c3 = st.columns(3)
    mv_kv_default = _safe_float(
        ac_output.get("grid_kv") or stage13_output.get("poi_nominal_voltage_kv"), 33.0
    )
    mv_kv = c1.number_input(
        "MV nominal voltage (kV)",
        min_value=1.0,
        value=_safe_float(_default_value(stored_inputs, "mv_kv", mv_kv_default), mv_kv_default),
        step=0.1,
    )

    pcs_lv_v_default = _safe_float(ac_output.get("inverter_lv_v"), 800.0)
    pcs_lv_v = c2.number_input(
        "PCS LV voltage (V_LL,rms)",
        min_value=100.0,
        value=_safe_float(_default_value(stored_inputs, "pcs_lv_v", pcs_lv_v_default), pcs_lv_v_default),
        step=10.0,
    )

    block_size_mw_default = _safe_float(ac_output.get("block_size_mw"), 5.0)
    block_size_mw = c3.number_input(
        "AC block size (MW)",
        min_value=0.0,
        value=_safe_float(
            _default_value(stored_inputs, "block_size_mw", block_size_mw_default), block_size_mw_default
        ),
        step=0.1,
    )

    d1, d2, d3 = st.columns(3)
    pcs_rating_each_kw_default = block_size_mw * 1000 / 4 if block_size_mw > 0 else 0.0
    pcs_rating_each_kw = d1.number_input(
        "PCS rating per feeder (kW)",
        min_value=0.0,
        value=_safe_float(
            _default_value(stored_inputs, "pcs_rating_each_kw", pcs_rating_each_kw_default),
            pcs_rating_each_kw_default,
        ),
        step=50.0,
    )

    transformer_rating_kva_default = _safe_float(ac_output.get("transformer_kva"), 0.0)
    if transformer_rating_kva_default <= 0 and block_size_mw > 0:
        transformer_rating_kva_default = block_size_mw * 1000 / 0.9
    transformer_rating_kva = d2.number_input(
        "Transformer rating (kVA)",
        min_value=0.0,
        value=_safe_float(
            _default_value(stored_inputs, "transformer_rating_kva", transformer_rating_kva_default),
            transformer_rating_kva_default,
        ),
        step=50.0,
    )

    ac_block_template_id = d3.text_input(
        "AC block template ID",
        value=_default_value(
            stored_inputs,
            "ac_block_template_id",
            ac_output.get("ac_block_template_id") or f"4x{int(round(pcs_rating_each_kw))}kw",
        ),
    )

    st.subheader("DC Blocks by Feeder")
    dc_block_unit_default = None
    dc_block = dc_summary.get("dc_block") if isinstance(dc_summary, dict) else None
    if dc_block is not None:
        dc_block_unit_default = getattr(dc_block, "capacity_mwh", None)
    dc_block_unit_mwh = st.number_input(
        "DC block energy (MWh, per block)",
        min_value=0.0,
        value=_safe_float(
            _default_value(stored_inputs, "dc_block_unit_mwh", dc_block_unit_default or 0.0),
            dc_block_unit_default or 0.0,
        ),
        step=0.1,
    )

    temp_snapshot = build_sld_chain_snapshot_v2(
        stage13_output,
        ac_output,
        dc_summary,
        {
            "mv_kv": mv_kv,
            "pcs_lv_v": pcs_lv_v,
            "block_size_mw": block_size_mw,
            "pcs_rating_each_kw": pcs_rating_each_kw,
            "transformer_rating_kva": transformer_rating_kva,
            "ac_block_template_id": ac_block_template_id,
            "dc_block_unit_mwh": dc_block_unit_mwh or None,
        },
        scenario_id,
    )
    dc_blocks_default = temp_snapshot.get("dc_blocks_by_feeder", [])
    dc_df = pd.DataFrame(dc_blocks_default)
    if not dc_df.empty:
        dc_df = dc_df[["feeder_id", "dc_block_count", "dc_block_energy_mwh"]]
    dc_df = st.data_editor(dc_df, use_container_width=True, num_rows="fixed")
    dc_blocks_by_feeder = dc_df.to_dict("records")

    st.subheader("Electrical SLD Inputs")
    labels = stored_inputs.get("labels", {}) if isinstance(stored_inputs.get("labels"), dict) else {}
    label_c1, label_c2 = st.columns(2)
    to_switchgear = label_c1.text_input(
        "MV label: to switchgear",
        value=_default_value(labels, "to_switchgear", "To 20kV Switchgear"),
    )
    to_other_rmu = label_c2.text_input(
        "MV label: to other RMU",
        value=_default_value(labels, "to_other_rmu", "To Other RMU"),
    )

    rmu_defaults = stored_inputs.get("rmu", {}) if isinstance(stored_inputs.get("rmu"), dict) else {}
    tr_defaults = (
        stored_inputs.get("transformer", {})
        if isinstance(stored_inputs.get("transformer"), dict)
        else {}
    )
    bus_defaults = (
        stored_inputs.get("lv_busbar", {})
        if isinstance(stored_inputs.get("lv_busbar"), dict)
        else {}
    )
    feeder_defaults = (
        stored_inputs.get("feeder_breaker", {})
        if isinstance(stored_inputs.get("feeder_breaker"), dict)
        else {}
    )
    cable_defaults = stored_inputs.get("cables", {}) if isinstance(stored_inputs.get("cables"), dict) else {}

    st.markdown("**RMU**")
    r1, r2, r3 = st.columns(3)
    rmu_rated_voltage_kv = r1.number_input(
        "Rated voltage (kV)",
        min_value=0.0,
        value=_safe_float(_default_value(rmu_defaults, "rated_voltage_kv", mv_kv), mv_kv),
        step=0.1,
    )
    rmu_rated_current_a = r2.number_input(
        "Rated current (A)",
        min_value=0.0,
        value=_safe_float(_default_value(rmu_defaults, "rated_current_a", 630.0), 630.0),
        step=10.0,
    )
    rmu_short_circuit_ka_3s = r3.number_input(
        "Short-circuit (kA/3s)",
        min_value=0.0,
        value=_safe_float(_default_value(rmu_defaults, "short_circuit_ka_3s", 25.0), 25.0),
        step=1.0,
    )
    r4, r5, r6 = st.columns(3)
    rmu_ct_ratio = r4.text_input("CT ratio", value=_default_value(rmu_defaults, "ct_ratio", "200/1"))
    rmu_ct_class = r5.text_input("CT class", value=_default_value(rmu_defaults, "ct_class", "5P20"))
    rmu_ct_burden_va = r6.number_input(
        "CT burden (VA)",
        min_value=0.0,
        value=_safe_float(_default_value(rmu_defaults, "ct_burden_va", 10.0), 10.0),
        step=1.0,
    )

    st.markdown("**Transformer**")
    t1, t2, t3, t4 = st.columns(4)
    tr_vector_group = t1.text_input("Vector group", value=_default_value(tr_defaults, "vector_group", "Dyn11"))
    tr_impedance_percent = t2.number_input(
        "Impedance (%)",
        min_value=0.0,
        value=_safe_float(_default_value(tr_defaults, "impedance_percent", 6.0), 6.0),
        step=0.1,
    )
    tr_tap_range = t3.text_input("Tap range", value=_default_value(tr_defaults, "tap_range", "+/-2x2.5%"))
    tr_cooling = t4.text_input("Cooling", value=_default_value(tr_defaults, "cooling", "ONAN"))

    st.markdown("**LV Busbar**")
    b1, b2 = st.columns(2)
    lv_bus_rated_current_a = b1.number_input(
        "Rated current (A)",
        min_value=0.0,
        value=_safe_float(_default_value(bus_defaults, "rated_current_a", 2500.0), 2500.0),
        step=10.0,
    )
    lv_bus_short_circuit_ka = b2.number_input(
        "Short-circuit (kA)",
        min_value=0.0,
        value=_safe_float(_default_value(bus_defaults, "short_circuit_ka", 25.0), 25.0),
        step=1.0,
    )

    st.markdown("**Feeder Breaker**")
    f1, f2 = st.columns(2)
    feeder_rated_current_a = f1.number_input(
        "Rated current (A, optional)",
        min_value=0.0,
        value=_safe_float(_default_value(feeder_defaults, "rated_current_a", 1600.0), 1600.0),
        step=10.0,
    )
    feeder_short_circuit_ka = f2.number_input(
        "Short-circuit (kA, optional)",
        min_value=0.0,
        value=_safe_float(_default_value(feeder_defaults, "short_circuit_ka", 25.0), 25.0),
        step=1.0,
    )

    st.markdown("**Cables / Protection**")
    c1, c2, c3, c4 = st.columns(4)
    mv_cable_spec = c1.text_input(
        "MV cable spec",
        value=_default_value(cable_defaults, "mv_cable_spec", "3x1C-240mm2"),
    )
    lv_cable_spec = c2.text_input(
        "LV cable spec",
        value=_default_value(cable_defaults, "lv_cable_spec", "3x1C-400mm2"),
    )
    dc_cable_spec = c3.text_input(
        "DC cable spec",
        value=_default_value(cable_defaults, "dc_cable_spec", "1x1C-300mm2"),
    )
    dc_fuse_spec = c4.text_input(
        "DC fuse spec",
        value=_default_value(cable_defaults, "dc_fuse_spec", "TBD"),
    )

    persist_to_stage = st.checkbox("Save Electrical SLD Inputs into AC output", value=False)

    generate = st.button("Generate SLD Pro")

    sld_inputs = {
        "mv_kv": mv_kv,
        "pcs_lv_v": pcs_lv_v,
        "block_size_mw": block_size_mw,
        "pcs_rating_each_kw": pcs_rating_each_kw,
        "transformer_rating_kva": transformer_rating_kva,
        "ac_block_template_id": ac_block_template_id,
        "dc_block_unit_mwh": dc_block_unit_mwh or None,
        "dc_blocks_by_feeder": dc_blocks_by_feeder,
        "labels": {"to_switchgear": to_switchgear, "to_other_rmu": to_other_rmu},
        "rmu": {
            "rated_voltage_kv": rmu_rated_voltage_kv,
            "rated_current_a": rmu_rated_current_a,
            "short_circuit_ka_3s": rmu_short_circuit_ka_3s,
            "ct_ratio": rmu_ct_ratio,
            "ct_class": rmu_ct_class,
            "ct_burden_va": rmu_ct_burden_va,
        },
        "transformer": {
            "vector_group": tr_vector_group,
            "impedance_percent": tr_impedance_percent,
            "tap_range": tr_tap_range,
            "cooling": tr_cooling,
        },
        "lv_busbar": {
            "rated_current_a": lv_bus_rated_current_a,
            "short_circuit_ka": lv_bus_short_circuit_ka,
        },
        "feeder_breaker": {
            "rated_current_a": feeder_rated_current_a,
            "short_circuit_ka": feeder_short_circuit_ka,
        },
        "cables": {
            "mv_cable_spec": mv_cable_spec,
            "lv_cable_spec": lv_cable_spec,
            "dc_cable_spec": dc_cable_spec,
            "dc_fuse_spec": dc_fuse_spec,
        },
    }
    st.session_state["sld_pro_inputs"] = sld_inputs

    if generate:
        try:
            snapshot = build_sld_chain_snapshot_v2(
                stage13_output, ac_output, dc_summary, sld_inputs, scenario_id
            )
            validate_snapshot_chain_v2(snapshot)

            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                raw_svg_path = tmp_path / "sld_raw.svg"
                metadata_path = tmp_path / "sld_metadata.json"
                pro_svg_path = tmp_path / "sld_pro.svg"

                network = build_iidm_network_from_chain_snapshot(snapshot)
                render_pow_sybl_svg(
                    network,
                    container_id="SUB_MV_NODE_01",
                    out_svg=raw_svg_path,
                    out_metadata=metadata_path,
                )
                apply_pro_template(raw_svg_path, metadata_path, snapshot, pro_svg_path)

                st.session_state["sld_pro_raw_svg_bytes"] = raw_svg_path.read_bytes()
                st.session_state["sld_pro_svg_bytes"] = pro_svg_path.read_bytes()
                st.session_state["sld_pro_metadata_bytes"] = (
                    metadata_path.read_bytes() if metadata_path.exists() else None
                )
                st.session_state["sld_pro_snapshot_json"] = json.dumps(
                    snapshot, indent=2, sort_keys=True
                )
        except Exception as exc:
            st.error(f"SLD Pro generation failed: {exc}")
            return

        if persist_to_stage:
            if "ac_output" in st.session_state:
                st.session_state["ac_output"]["sld_electrical_inputs"] = sld_inputs
            if "stage13_output" in st.session_state:
                st.session_state["stage13_output"]["sld_electrical_inputs"] = sld_inputs

        st.success("SLD Pro SVG generated.")

    pro_svg_bytes = st.session_state.get("sld_pro_svg_bytes")
    if pro_svg_bytes:
        st.subheader("Preview")
        st.components.v1.html(pro_svg_bytes.decode("utf-8"), height=640, scrolling=True)

        st.subheader("Downloads")
        st.download_button(
            "Download snapshot.json",
            st.session_state.get("sld_pro_snapshot_json", ""),
            "sld_chain_snapshot.json",
            "application/json",
        )
        st.download_button(
            "Download sld_raw.svg",
            st.session_state.get("sld_pro_raw_svg_bytes"),
            "sld_raw.svg",
            "image/svg+xml",
        )
        if st.session_state.get("sld_pro_metadata_bytes"):
            st.download_button(
                "Download sld_metadata.json",
                st.session_state.get("sld_pro_metadata_bytes"),
                "sld_metadata.json",
                "application/json",
            )
        st.download_button(
            "Download sld_pro.svg",
            st.session_state.get("sld_pro_svg_bytes"),
            "sld_pro.svg",
            "image/svg+xml",
        )
