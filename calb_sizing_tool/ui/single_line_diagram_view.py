import datetime
import json
import tempfile
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import streamlit as st

from calb_diagrams.specs import build_sld_group_spec
from calb_diagrams.sld_pro_renderer import render_sld_pro_svg
from calb_sizing_tool.common.allocation import evenly_distribute
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


def _safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def _resolve_pcs_count_by_block(ac_output: dict) -> list[int]:
    pcs_counts = ac_output.get("pcs_count_by_block")
    if isinstance(pcs_counts, list) and pcs_counts:
        return [_safe_int(v, 0) for v in pcs_counts]

    num_blocks = _safe_int(ac_output.get("num_blocks"), 0)
    total_pcs = _safe_int(ac_output.get("total_pcs"), 0)
    pcs_per_block = _safe_int(ac_output.get("pcs_per_block"), 0)
    if num_blocks > 0 and total_pcs > 0:
        return evenly_distribute(total_pcs, num_blocks)
    if num_blocks > 0 and pcs_per_block > 0:
        return [pcs_per_block for _ in range(num_blocks)]
    return [4]


def _resolve_dc_blocks_per_feeder(
    stage13_output: dict,
    ac_output: dict,
    dc_summary: dict,
    pcs_count: int,
    group_index: int,
) -> list[int]:
    dc_blocks_per_feeder_by_block = ac_output.get("dc_blocks_per_feeder_by_block")
    if isinstance(dc_blocks_per_feeder_by_block, list) and dc_blocks_per_feeder_by_block:
        idx = max(0, min(group_index - 1, len(dc_blocks_per_feeder_by_block) - 1))
        candidate = dc_blocks_per_feeder_by_block[idx]
        if isinstance(candidate, list) and candidate:
            return [_safe_int(v, 0) for v in candidate]

    dc_blocks_total_by_block = ac_output.get("dc_blocks_total_by_block")
    if isinstance(dc_blocks_total_by_block, list) and dc_blocks_total_by_block:
        idx = max(0, min(group_index - 1, len(dc_blocks_total_by_block) - 1))
        return evenly_distribute(_safe_int(dc_blocks_total_by_block[idx], 0), pcs_count)

    total_dc_blocks = _safe_int(stage13_output.get("dc_block_total_qty"), 0)
    if total_dc_blocks <= 0:
        total_dc_blocks = _safe_int(stage13_output.get("container_count"), 0) + _safe_int(
            stage13_output.get("cabinet_count"), 0
        )
    if total_dc_blocks <= 0 and isinstance(dc_summary, dict):
        dc_block = dc_summary.get("dc_block")
        if dc_block is not None:
            total_dc_blocks = _safe_int(getattr(dc_block, "count", 0))

    ac_blocks_total = _safe_int(ac_output.get("num_blocks"), 0) or 1
    per_block_total = evenly_distribute(total_dc_blocks, ac_blocks_total)
    idx = max(0, min(group_index - 1, len(per_block_total) - 1))
    return evenly_distribute(per_block_total[idx], pcs_count)


def show():
    st.header("Single Line Diagram")
    st.caption("Deliverable SLD (template) + raw PowSyBl debug view.")

    stage13_output = st.session_state.get("stage13_output", {}) or {}
    ac_output = st.session_state.get("ac_output", {}) or {}
    dc_summary = st.session_state.get("dc_result_summary", {}) or {}

    if not stage13_output or not ac_output:
        st.warning("Run DC sizing and AC sizing first to generate SLD inputs.")
        return

    scenario_default = stage13_output.get("selected_scenario", "container_only")
    scenario_id = st.text_input("Scenario ID", value=scenario_default)

    stored_inputs = st.session_state.get("sld_diagram_inputs", {}) or {}

    pcs_counts = _resolve_pcs_count_by_block(ac_output)
    ac_blocks_total = max(len(pcs_counts), _safe_int(ac_output.get("num_blocks"), 0), 1)
    group_default = _safe_int(stored_inputs.get("group_index"), 1)
    if group_default < 1:
        group_default = 1
    if group_default > ac_blocks_total:
        group_default = ac_blocks_total
    group_index = st.selectbox(
        "AC Block Group",
        list(range(1, ac_blocks_total + 1)),
        index=group_default - 1,
    )
    pcs_count = pcs_counts[group_index - 1] if pcs_counts else 4
    st.caption(f"Selected group PCS count: {pcs_count}")

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
        stored_inputs.get("transformer_rating_mva"),
        _safe_float(ac_output.get("transformer_kva"), 0.0) / 1000.0,
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
    pcs_rating_default = _safe_float(stored_inputs.get("pcs_rating_each_kw"), 0.0)
    if pcs_rating_default <= 0 and _safe_float(ac_output.get("pcs_power_kw"), 0.0) > 0:
        pcs_rating_default = _safe_float(ac_output.get("pcs_power_kw"), 0.0)
    if pcs_rating_default <= 0 and _safe_float(ac_output.get("block_size_mw"), 0.0) > 0 and pcs_count > 0:
        pcs_rating_default = _safe_float(ac_output.get("block_size_mw"), 5.0) * 1000 / pcs_count
    pcs_rating_each_kw = d1.number_input(
        "PCS rating each (kW)",
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

    st.subheader("DC Block Allocation (per feeder)")
    dc_blocks_per_feeder = _resolve_dc_blocks_per_feeder(
        stage13_output, ac_output, dc_summary, pcs_count, group_index
    )
    dc_df = pd.DataFrame(
        {
            "feeder_id": [f"F{idx + 1}" for idx in range(pcs_count)],
            "dc_block_count": dc_blocks_per_feeder,
        }
    )
    dc_df = st.data_editor(dc_df, use_container_width=True, num_rows="fixed")
    dc_blocks_per_feeder = [
        _safe_int(row.get("dc_block_count"), 0) for row in dc_df.to_dict("records")
    ]

    electrical_inputs = render_electrical_inputs(stored_inputs)

    sld_inputs = {
        "group_index": group_index,
        "mv_nominal_kv_ac": mv_kv,
        "pcs_lv_voltage_v_ll": pcs_lv_v,
        "transformer_rating_mva": transformer_rating_mva,
        "pcs_rating_each_kw": pcs_rating_each_kw,
        "pcs_rating_each_kva": pcs_rating_each_kw,
        "pcs_rating_kw_list": [pcs_rating_each_kw for _ in range(pcs_count)],
        "dc_block_energy_mwh": dc_block_energy_mwh,
        "dc_blocks_per_feeder": dc_blocks_per_feeder,
        **electrical_inputs,
    }
    st.session_state["sld_diagram_inputs"] = sld_inputs

    tab_pro, tab_raw = st.tabs(["Pro (Deliverable)", "Raw (Debug)"])

    with tab_pro:
        st.caption("Template layout for customer delivery. Outputs SVG + PNG.")
        generate_pro = st.button("Generate SLD Pro", key="generate_sld_pro")
        if generate_pro:
            try:
                spec = build_sld_group_spec(
                    stage13_output, ac_output, dc_summary, sld_inputs, group_index
                )
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp_path = Path(tmpdir)
                    svg_path = tmp_path / "sld_pro.svg"
                    png_path = tmp_path / "sld_pro.png"
                    svg_result, warning = render_sld_pro_svg(spec, svg_path, png_path)
                    if svg_result is None:
                        st.error(warning or "SLD Pro renderer unavailable.")
                        st.code("pip install svgwrite")
                    else:
                        if warning:
                            st.warning(warning)
                            if "cairosvg" in warning.lower():
                                st.code("pip install cairosvg")

                        if svg_path.exists():
                            st.session_state["sld_pro_svg_bytes"] = svg_path.read_bytes()
                        if png_path.exists():
                            png_bytes = png_path.read_bytes()
                            st.session_state["sld_pro_png_bytes"] = png_bytes
                            st.session_state["sld_pro_png_meta"] = {
                                "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                                "hash": __import__("hashlib")
                                .sha256(png_bytes)
                                .hexdigest()[:12],
                            }
                        spec_dict = asdict(spec)
                        spec_dict["schema_version"] = "sld_group_spec_v1"
                        st.session_state["sld_snapshot"] = {
                            "schema_version": "sld_group_spec_v1",
                            "group_index": spec.group_index,
                            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                            "spec": spec_dict,
                        }
                        st.session_state["sld_pro_spec_json"] = json.dumps(
                            spec_dict, indent=2, sort_keys=True
                        )
            except Exception as exc:
                st.error(f"SLD Pro generation failed: {exc}")

        pro_png = st.session_state.get("sld_pro_png_bytes")
        pro_svg = st.session_state.get("sld_pro_svg_bytes")
        if pro_png or pro_svg:
            st.subheader("Preview")
            if pro_png:
                st.image(pro_png, use_container_width=True)
            else:
                st.components.v1.html(pro_svg.decode("utf-8"), height=700, scrolling=True)

            st.subheader("Downloads")
            if st.session_state.get("sld_pro_spec_json"):
                st.download_button(
                    "Download sld_pro_spec.json",
                    st.session_state.get("sld_pro_spec_json"),
                    "sld_pro_spec.json",
                    "application/json",
                )
            if pro_svg:
                st.download_button(
                    "Download sld_pro.svg",
                    pro_svg,
                    "sld_pro.svg",
                    "image/svg+xml",
                )
            if pro_png:
                st.download_button(
                    "Download sld_pro.png",
                    pro_png,
                    "sld_pro.png",
                    "image/png",
                )

    with tab_raw:
        st.caption("Debug only (topology validation), not for customer deliverable.")
        if not POWSYBL_AVAILABLE:
            st.warning("pypowsybl is not installed. Install it to enable raw SLD generation.")
            st.code("pip install pypowsybl")
        else:
            generate_raw = st.button("Generate Raw SLD", key="generate_sld_raw")
            if generate_raw:
                try:
                    dc_blocks_by_feeder = []
                    for idx, count in enumerate(dc_blocks_per_feeder, start=1):
                        dc_blocks_by_feeder.append(
                            {
                                "feeder_id": f"FDR-{idx:02d}",
                                "dc_block_count": int(count),
                                "dc_block_energy_mwh": float(count) * dc_block_energy_mwh,
                            }
                        )
                    raw_inputs = dict(sld_inputs)
                    raw_inputs["dc_blocks_by_feeder"] = dc_blocks_by_feeder
                    snapshot = build_single_unit_snapshot(
                        stage13_output, ac_output, dc_summary, raw_inputs, scenario_id
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

            raw_svg_bytes = st.session_state.get("sld_raw_svg_bytes")
            if raw_svg_bytes:
                st.subheader("Preview")
                st.components.v1.html(raw_svg_bytes.decode("utf-8"), height=640, scrolling=True)

                st.subheader("Downloads")
                st.download_button(
                    "Download snapshot.json",
                    st.session_state.get("sld_raw_snapshot_json", ""),
                    "sld_raw_snapshot.json",
                    "application/json",
                )
                st.download_button(
                    "Download raw.svg",
                    raw_svg_bytes,
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
