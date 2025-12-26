import datetime
import inspect
import json
import tempfile
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import streamlit as st

from calb_diagrams.sld_pro_renderer import render_sld_pro_svg
from calb_diagrams.specs import build_sld_group_spec
from calb_sizing_tool.common.allocation import allocate_dc_blocks, evenly_distribute
from calb_sizing_tool.common.dependencies import check_dependencies
from calb_sizing_tool.sld.iidm_builder import build_network_for_single_unit
from calb_sizing_tool.sld.jp_pro_renderer import render_jp_pro_svg
from calb_sizing_tool.sld.renderer import render_raw_svg
from calb_sizing_tool.sld.snapshot_single_unit import (
    build_single_unit_snapshot,
    validate_single_unit_snapshot,
)
from calb_sizing_tool.sld.svg_postprocess_margin import add_margins
from calb_sizing_tool.sld.svg_postprocess_raw import apply_raw_style
from calb_sizing_tool.ui.sld_inputs import render_electrical_inputs
from calb_sizing_tool.state.project_state import init_project_state
from calb_sizing_tool.state.session_state import init_shared_state


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

    pcs_units = ac_output.get("pcs_units")
    if isinstance(pcs_units, list) and pcs_units:
        return [len(pcs_units)]

    num_blocks = _safe_int(ac_output.get("num_blocks"), 0)
    total_pcs = _safe_int(ac_output.get("total_pcs"), 0)
    pcs_per_block = _safe_int(
        ac_output.get("pcs_count_per_ac_block") or ac_output.get("pcs_per_block"), 0
    )
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
    direct = ac_output.get("dc_block_allocation_by_feeder")
    if isinstance(direct, dict) and direct:
        keys = sorted(
            direct.keys(),
            key=lambda k: _safe_int(str(k).lstrip("Ff"), 0),
        )
        return [_safe_int(direct.get(key), 0) for key in keys]

    allocation = ac_output.get("dc_block_allocation")
    if isinstance(allocation, dict):
        per_ac_block = allocation.get("per_ac_block")
        if isinstance(per_ac_block, list) and per_ac_block:
            idx = max(0, min(group_index - 1, len(per_ac_block) - 1))
            per_feeder = per_ac_block[idx].get("per_feeder")
            if isinstance(per_feeder, dict) and per_feeder:
                keys = sorted(
                    per_feeder.keys(),
                    key=lambda k: _safe_int(str(k).lstrip("Ff"), 0),
                )
                return [_safe_int(per_feeder.get(key), 0) for key in keys]
        per_feeder = allocation.get("per_feeder")
        if isinstance(per_feeder, dict) and per_feeder:
            keys = sorted(
                per_feeder.keys(),
                key=lambda k: _safe_int(str(k).lstrip("Ff"), 0),
            )
            return [_safe_int(per_feeder.get(key), 0) for key in keys]
        per_pcs_group = allocation.get("per_pcs_group")
        if isinstance(per_pcs_group, list) and per_pcs_group:
            return [_safe_int(item.get("dc_block_count"), 0) for item in per_pcs_group]

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
    return allocate_dc_blocks(per_block_total[idx], pcs_count)


def show():
    state = init_shared_state()
    init_project_state()

    st.header("Single Line Diagram")
    st.caption("Engineering-readable SLD for one AC block group.")

    deps = check_dependencies()
    svgwrite_ok = deps.get("svgwrite", False)
    cairosvg_ok = deps.get("cairosvg", False)
    pypowsybl_ok = deps.get("pypowsybl", False)

    dc_results = state.dc_results or {}
    ac_results = state.ac_results or {}
    diagram_outputs = state.diagram_outputs
    diagram_inputs = st.session_state.setdefault("diagram_inputs", {})
    diagram_results = st.session_state.setdefault("diagram_results", {})
    artifacts = state.artifacts

    stage13_output = st.session_state.get("stage13_output") or dc_results.get("stage13_output") or {}
    dc_summary = st.session_state.get("dc_result_summary") or dc_results.get("dc_result_summary") or {}
    ac_output = st.session_state.get("ac_output") or ac_results or {}
    if stage13_output.get("project_name"):
        st.session_state["project_name"] = stage13_output.get("project_name")

    has_prereq = bool(stage13_output) and bool(ac_output)

    st.subheader("Data Status")
    if not has_prereq:
        st.warning("Please run DC Sizing + AC Sizing first.")
    dc_time = dc_results.get("last_run_time") or "Not run"
    ac_time = ac_results.get("last_run_time") or "Not run"
    mv_kv_status = ac_output.get("mv_voltage_kv") or ac_output.get("mv_kv") or ac_output.get("grid_kv") or "TBD"
    lv_v_status = ac_output.get("lv_voltage_v") or ac_output.get("lv_v") or ac_output.get("inverter_lv_v") or "TBD"
    pcs_counts = _resolve_pcs_count_by_block(ac_output)
    pcs_count_status = pcs_counts[0] if pcs_counts else "TBD"
    dc_blocks_status = ac_output.get("dc_block_allocation", {}).get("total_dc_blocks")
    if dc_blocks_status is None:
        dc_blocks_status = ac_output.get("dc_blocks_per_ac")
    c_status1, c_status2, c_status3 = st.columns(3)
    c_status1.metric("DC Run", dc_time)
    c_status2.metric("AC Run", ac_time)
    c_status3.metric("MV/LV", f"{mv_kv_status} kV / {lv_v_status} V")
    c_status4, c_status5 = st.columns(2)
    c_status4.metric("PCS Count (group)", pcs_count_status)
    c_status5.metric("DC Blocks (group)", dc_blocks_status or "TBD")

    if not svgwrite_ok:
        st.error("Missing dependency: svgwrite. Install with `pip install -r requirements.txt`.")
        if not pypowsybl_ok:
            st.error("Raw fallback also requires pypowsybl. Install with `pip install pypowsybl`.")

    def _init_input(field: str, default_value):
        key = f"diagram_inputs.{field}"
        if key not in st.session_state:
            st.session_state[key] = default_value
        if field not in diagram_inputs:
            diagram_inputs[field] = st.session_state[key]
        return key

    scenario_default = diagram_inputs.get("scenario_id") or stage13_output.get("selected_scenario", "container_only")
    scenario_id = st.text_input(
        "Scenario ID",
        key=_init_input("scenario_id", scenario_default),
    )
    diagram_inputs["scenario_id"] = scenario_id

    style_options = ["Raw V0.5 (Stable)", "Pro English V1.0"]
    style_default = diagram_inputs.get("style") or style_options[0]
    if style_default not in style_options:
        style_default = style_options[0]
    style = st.selectbox(
        "Style",
        style_options,
        index=style_options.index(style_default),
        key=_init_input("style", style_default),
    )
    diagram_inputs["style"] = style

    ac_blocks_total = max(len(pcs_counts), _safe_int(ac_output.get("num_blocks"), 0), 1)
    group_default = _safe_int(diagram_inputs.get("group_index"), 1)
    group_default = max(1, min(group_default, ac_blocks_total))
    group_index = st.selectbox(
        "AC Block Group",
        list(range(1, ac_blocks_total + 1)),
        index=group_default - 1,
        key=_init_input("group_index", group_default),
        disabled=not has_prereq,
    )
    diagram_inputs["group_index"] = group_index

    pcs_count = pcs_counts[group_index - 1] if pcs_counts and group_index > 0 else 0
    st.caption(f"Selected group PCS count: {pcs_count or 'TBD'}")

    st.subheader("Chain Parameters")
    c1, c2, c3 = st.columns(3)
    mv_kv_default = diagram_inputs.get("mv_kv")
    if mv_kv_default is None:
        mv_kv_default = mv_kv_status if mv_kv_status != "TBD" else 33.0
    mv_kv = c1.number_input(
        "MV nominal voltage (kV)",
        min_value=1.0,
        key=_init_input("mv_kv", float(mv_kv_default)),
        step=0.1,
        disabled=not has_prereq,
    )
    diagram_inputs["mv_kv"] = mv_kv

    lv_v_default = diagram_inputs.get("lv_v")
    if lv_v_default is None:
        lv_v_default = lv_v_status if lv_v_status != "TBD" else 690.0
    pcs_lv_v = c2.number_input(
        "PCS LV voltage (V_LL,rms)",
        min_value=100.0,
        key=_init_input("lv_v", float(lv_v_default)),
        step=10.0,
        disabled=not has_prereq,
    )
    diagram_inputs["lv_v"] = pcs_lv_v

    transformer_mva_default = diagram_inputs.get("transformer_mva")
    if transformer_mva_default is None:
        transformer_mva_default = _safe_float(ac_output.get("transformer_mva"), 0.0)
    if transformer_mva_default <= 0:
        transformer_mva_default = _safe_float(ac_output.get("transformer_kva"), 0.0) / 1000.0
    if transformer_mva_default <= 0 and _safe_float(ac_output.get("block_size_mw"), 0.0) > 0:
        transformer_mva_default = _safe_float(ac_output.get("block_size_mw"), 5.0) / 0.9
    transformer_rating_mva = c3.number_input(
        "Transformer rating (MVA)",
        min_value=0.1,
        key=_init_input("transformer_mva", float(transformer_mva_default or 5.0)),
        step=0.1,
        disabled=not has_prereq,
    )
    diagram_inputs["transformer_mva"] = transformer_rating_mva

    d1, d2 = st.columns(2)
    pcs_rating_default = diagram_inputs.get("pcs_rating_kw")
    if pcs_rating_default is None:
        pcs_rating_default = _safe_float(ac_output.get("pcs_rating_kw_each"), 0.0)
    if pcs_rating_default <= 0:
        pcs_rating_default = _safe_float(ac_output.get("pcs_power_kw"), 0.0)
    if pcs_rating_default <= 0 and _safe_float(ac_output.get("block_size_mw"), 0.0) > 0 and pcs_count > 0:
        pcs_rating_default = _safe_float(ac_output.get("block_size_mw"), 5.0) * 1000 / pcs_count
    pcs_rating_each_kw = d1.number_input(
        "PCS rating each (kW)",
        min_value=0.0,
        key=_init_input("pcs_rating_kw", float(pcs_rating_default or 1250.0)),
        step=10.0,
        disabled=not has_prereq,
    )
    diagram_inputs["pcs_rating_kw"] = pcs_rating_each_kw

    dc_block_default = diagram_inputs.get("dc_block_energy_mwh")
    if dc_block_default is None:
        dc_block_default = _safe_float(ac_output.get("dc_block_energy_mwh_each"), 0.0)
    if dc_block_default <= 0:
        dc_block_default = _safe_float(ac_output.get("dc_block_mwh_each"), 0.0)
    if dc_block_default <= 0 and isinstance(dc_summary, dict):
        dc_block = dc_summary.get("dc_block")
        if dc_block is not None:
            dc_block_default = getattr(dc_block, "capacity_mwh", None)
    dc_block_energy_mwh = d2.number_input(
        "DC block energy (MWh)",
        min_value=0.0,
        key=_init_input("dc_block_energy_mwh", float(dc_block_default or 5.106)),
        step=0.001,
        disabled=not has_prereq,
    )
    diagram_inputs["dc_block_energy_mwh"] = dc_block_energy_mwh

    st.subheader("DC Block Allocation (per feeder)")
    default_dc_blocks = _resolve_dc_blocks_per_feeder(
        stage13_output, ac_output, dc_summary, pcs_count or 0, group_index
    )
    stored_blocks = diagram_inputs.get("dc_blocks_per_feeder")
    if isinstance(stored_blocks, list) and len(stored_blocks) == len(default_dc_blocks):
        dc_blocks_per_feeder = stored_blocks
    else:
        dc_blocks_per_feeder = default_dc_blocks
    dc_df = pd.DataFrame(
        {
            "feeder_id": [f"F{idx + 1}" for idx in range(len(dc_blocks_per_feeder))],
            "dc_block_count": dc_blocks_per_feeder,
        }
    )
    table_key = _init_input("dc_blocks_table", dc_df)
    dc_df = st.data_editor(
        dc_df,
        use_container_width=True,
        num_rows="fixed",
        key=table_key,
        disabled=not has_prereq,
    )
    dc_blocks_per_feeder = [
        _safe_int(row.get("dc_block_count"), 0) for row in dc_df.to_dict("records")
    ]
    diagram_inputs["dc_blocks_per_feeder"] = dc_blocks_per_feeder

    if "key_prefix" in inspect.signature(render_electrical_inputs).parameters:
        electrical_inputs = render_electrical_inputs(
            diagram_inputs, key_prefix="diagram_inputs"
        )
    else:
        electrical_inputs = render_electrical_inputs(diagram_inputs)

    sld_inputs = {
        "group_index": group_index,
        "mv_nominal_kv_ac": mv_kv,
        "pcs_lv_voltage_v_ll": pcs_lv_v,
        "transformer_rating_mva": transformer_rating_mva,
        "pcs_rating_each_kw": pcs_rating_each_kw,
        "pcs_rating_each_kva": pcs_rating_each_kw,
        "pcs_rating_kw_list": [pcs_rating_each_kw for _ in range(pcs_count or 0)],
        "dc_block_energy_mwh": dc_block_energy_mwh,
        "dc_blocks_per_feeder": dc_blocks_per_feeder,
        **electrical_inputs,
    }

    style_id = "raw_v05" if style.startswith("Raw") else "pro_v10"
    if style_id not in diagram_results:
        diagram_results[style_id] = {}

    generate_disabled = not has_prereq
    if style_id == "raw_v05" and not svgwrite_ok and not pypowsybl_ok:
        generate_disabled = True
    if style_id == "pro_v10" and not svgwrite_ok:
        generate_disabled = True

    generate = st.button(
        "Generate SLD",
        key="sld_generate_button",
        disabled=generate_disabled,
    )
    if generate:
        try:
            if style_id == "raw_v05":
                if svgwrite_ok:
                    spec = build_sld_group_spec(
                        stage13_output, ac_output, dc_summary, sld_inputs, group_index
                    )
                    with tempfile.TemporaryDirectory() as tmpdir:
                        tmp_path = Path(tmpdir)
                        svg_path = tmp_path / "sld_raw_v05.svg"
                        png_path = tmp_path / "sld_raw_v05.png"
                        svg_result, warning = render_sld_pro_svg(spec, svg_path, png_path)
                        if svg_result is None:
                            st.error(warning or "SLD renderer unavailable.")
                        else:
                            if warning:
                                st.warning(warning)
                            svg_bytes = svg_path.read_bytes() if svg_path.exists() else None
                            png_bytes = png_path.read_bytes() if png_path.exists() else None
                elif not pypowsybl_ok:
                    st.error("Raw fallback requires pypowsybl. Install with `pip install pypowsybl`.")
                    svg_bytes = None
                    png_bytes = None
                else:
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
                    raw_inputs["diagram_scope"] = "one_ac_block_group"
                    snapshot = build_single_unit_snapshot(
                        stage13_output, ac_output, dc_summary, raw_inputs, scenario_id
                    )
                    validate_single_unit_snapshot(snapshot)
                    with tempfile.TemporaryDirectory() as tmpdir:
                        tmp_path = Path(tmpdir)
                        raw_svg_path = tmp_path / "sld_raw.svg"
                        styled_svg_path = tmp_path / "sld_raw_styled.svg"
                        final_svg_path = tmp_path / "sld_raw_final.svg"
                        network = build_network_for_single_unit(snapshot)
                        render_raw_svg(
                            network,
                            container_id="SUB_MV_NODE_01",
                            out_svg=raw_svg_path,
                        )
                        labels = snapshot.get("mv", {}).get("labels", {})
                        apply_raw_style(
                            raw_svg_path,
                            styled_svg_path,
                            to_switchgear=labels.get("to_switchgear"),
                            to_other_rmu=labels.get("to_other_rmu"),
                        )
                        add_margins(styled_svg_path, final_svg_path, left_margin_px=140, top_margin_px=40)
                        svg_bytes = final_svg_path.read_bytes() if final_svg_path.exists() else None
                        png_bytes = None
                        if svg_bytes and cairosvg_ok:
                            try:
                                import cairosvg

                                png_bytes = cairosvg.svg2png(bytestring=svg_bytes)
                            except Exception:
                                png_bytes = None
            else:
                if style_id == "pro_v10" and not svgwrite_ok:
                    st.error("Pro rendering requires svgwrite. Install with `pip install svgwrite`.")
                    svg_bytes = None
                    png_bytes = None
                else:
                    dc_blocks_by_feeder = []
                    for idx, count in enumerate(dc_blocks_per_feeder, start=1):
                        dc_blocks_by_feeder.append(
                            {
                                "feeder_id": f"FDR-{idx:02d}",
                                "dc_block_count": int(count),
                                "dc_block_energy_mwh": float(count) * dc_block_energy_mwh,
                            }
                        )
                    jp_inputs = dict(sld_inputs)
                    jp_inputs["dc_blocks_by_feeder"] = dc_blocks_by_feeder
                    jp_inputs["diagram_scope"] = "one_ac_block_group"
                    snapshot = build_single_unit_snapshot(
                        stage13_output, ac_output, dc_summary, jp_inputs, scenario_id
                    )
                    validate_single_unit_snapshot(snapshot)
                    with tempfile.TemporaryDirectory() as tmpdir:
                        tmp_path = Path(tmpdir)
                        svg_path = tmp_path / "sld_pro_v10.svg"
                        render_jp_pro_svg(snapshot, svg_path)
                        svg_bytes = svg_path.read_bytes()
                        png_bytes = None
                        if cairosvg_ok:
                            try:
                                import cairosvg

                                png_bytes = cairosvg.svg2png(bytestring=svg_bytes)
                            except Exception:
                                png_bytes = None

            if svg_bytes or png_bytes:
                dc_blocks_total = sum(dc_blocks_per_feeder) if dc_blocks_per_feeder else 0
                meta = {
                    "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                    "style": style_id,
                    "group_index": group_index,
                    "mv_kv": mv_kv,
                    "lv_v": pcs_lv_v,
                    "pcs_count": pcs_count,
                    "dc_blocks_total": dc_blocks_total,
                    "transformer_mva": transformer_rating_mva,
                    "pcs_rating_kw_each": pcs_rating_each_kw,
                    "dc_block_energy_mwh": dc_block_energy_mwh,
                }
                diagram_results[style_id] = {
                    "svg": svg_bytes,
                    "png": png_bytes,
                    "meta": meta,
                }
                diagram_results["last_style"] = style_id
                st.session_state["diagram_results"] = diagram_results
                if svg_bytes:
                    artifacts["sld_svg_bytes"] = svg_bytes
                    diagram_outputs.sld_svg = svg_bytes
                if png_bytes:
                    artifacts["sld_png_bytes"] = png_bytes
                    diagram_outputs.sld_png = png_bytes
                artifacts["sld_meta"] = meta
        except Exception as exc:
            st.error(f"SLD generation failed: {exc}")

    cached = diagram_results.get(style_id) or {}
    svg_bytes = cached.get("svg")
    png_bytes = cached.get("png")
    if svg_bytes or png_bytes:
        st.subheader("Preview")
        zoom = st.slider(
            "Zoom (%)",
            min_value=50,
            max_value=200,
            value=int(diagram_inputs.get("zoom", 100) or 100),
            key=_init_input("zoom", 100),
        )
        diagram_inputs["zoom"] = zoom
        if png_bytes:
            st.image(png_bytes, width=int(800 * zoom / 100))
        else:
            scale = zoom / 100.0
            height = int(720 * scale)
            svg_html = f"<div style='transform: scale({scale}); transform-origin: 0 0;'>{svg_bytes.decode('utf-8')}</div>"
            st.components.v1.html(svg_html, height=height, scrolling=True)

        st.subheader("Downloads")
        if svg_bytes:
            st.download_button(
                "Download SLD SVG",
                svg_bytes,
                f"sld_{style_id}.svg",
                "image/svg+xml",
            )
        if png_bytes:
            st.download_button(
                "Download SLD PNG",
                png_bytes,
                f"sld_{style_id}.png",
                "image/png",
            )
