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
from calb_sizing_tool.common.preferences import load_preferences, save_preferences
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
from calb_sizing_tool.state.project_state import get_project_state, init_project_state
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


@st.cache_data(show_spinner=False)
def _svg_bytes_to_png(svg_bytes: bytes) -> bytes | None:
    if not svg_bytes:
        return None
    try:
        import cairosvg
    except Exception:
        return None
    try:
        return cairosvg.svg2png(bytestring=svg_bytes, background_color="white")
    except Exception:
        return None


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
    override_total_blocks: int = 0,
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

    ac_blocks_total = override_total_blocks
    if ac_blocks_total <= 0:
        ac_blocks_total = _safe_int(ac_output.get("num_blocks"), 0) or 1
    per_block_total = evenly_distribute(total_dc_blocks, ac_blocks_total)
    idx = max(0, min(group_index - 1, len(per_block_total) - 1))
    return allocate_dc_blocks(per_block_total[idx], pcs_count)


def show():
    state = init_shared_state()
    init_project_state()
    project_state = get_project_state()

    st.header("Single Line Diagram")
    st.caption("Engineering-readable SLD for one AC block group.")

    deps = check_dependencies()
    svgwrite_ok = deps.get("svgwrite", False)
    cairosvg_ok = deps.get("cairosvg", False)
    pypowsybl_ok = deps.get("pypowsybl", False)

    def _pick_value(*values):
        for value in values:
            if value is not None:
                return value
        return None

    dc_results = project_state.get("dc_results") or state.dc_results
    ac_inputs = project_state.get("ac_inputs") or state.ac_inputs
    ac_results = project_state.get("ac_results") or state.ac_results
    diagram_outputs = state.diagram_outputs
    diagram_inputs = project_state.get("diagram_inputs") or st.session_state.setdefault(
        "diagram_inputs", {}
    )
    diagram_results = project_state.get("diagram_outputs") or st.session_state.setdefault(
        "diagram_results", {}
    )
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
    mv_kv_value = _pick_value(
        ac_inputs.get("grid_kv"),
        ac_inputs.get("mv_kv"),
        ac_output.get("mv_voltage_kv"),
        ac_output.get("mv_kv"),
        ac_output.get("grid_kv"),
    )
    lv_v_value = _pick_value(
        ac_inputs.get("lv_voltage_v"),
        ac_inputs.get("pcs_lv_v"),
        ac_output.get("lv_voltage_v"),
        ac_output.get("lv_v"),
        ac_output.get("inverter_lv_v"),
    )
    mv_kv_status = mv_kv_value if mv_kv_value is not None else "TBD"
    lv_v_status = lv_v_value if lv_v_value is not None else "TBD"
    pcs_counts = _resolve_pcs_count_by_block(ac_output)
    pcs_count_status = pcs_counts[0] if pcs_counts else "TBD"
    if isinstance(pcs_count_status, (list, tuple)):
        pcs_count_status = sum(pcs_count_status) if pcs_count_status else "TBD"
    dc_blocks_status = ac_output.get("dc_block_allocation", {}).get("total_dc_blocks")
    if dc_blocks_status is None:
        dc_blocks_status_raw = ac_output.get("dc_blocks_per_ac")
        # Ensure dc_blocks_status is a scalar, not a list
        if isinstance(dc_blocks_status_raw, (list, tuple)):
            # If it's a list, sum all numeric values to get total DC blocks
            try:
                dc_blocks_status = sum(int(x) for x in dc_blocks_status_raw if isinstance(x, (int, float)))
            except (ValueError, TypeError):
                dc_blocks_status = len(dc_blocks_status_raw) if dc_blocks_status_raw else "TBD"
        else:
            dc_blocks_status = dc_blocks_status_raw
    c_status1, c_status2, c_status3 = st.columns(3)
    c_status1.metric("DC Run", dc_time)
    c_status2.metric("AC Run", ac_time)
    c_status3.metric("MV/LV", f"{mv_kv_status} kV / {lv_v_status} V")
    c_status4, c_status5 = st.columns(2)
    c_status4.metric("PCS Count (group)", str(pcs_count_status) if pcs_count_status != "TBD" else pcs_count_status)
    c_status5.metric("DC Blocks (group)", str(dc_blocks_status) if dc_blocks_status != "TBD" else "TBD")

    if not svgwrite_ok:
        st.error("Missing dependency: svgwrite. Install with `pip install -r requirements.txt`.")
        if not pypowsybl_ok:
            st.error("Raw fallback also requires pypowsybl. Install with `pip install pypowsybl`.")

    scenario_default = diagram_inputs.get("scenario_id")
    if scenario_default is None:
        scenario_default = stage13_output.get("selected_scenario", "container_only")
    scenario_id = st.text_input(
        "Scenario ID",
        value=str(scenario_default) if scenario_default is not None else "",
        key="diagram_inputs.scenario_id",
    )
    diagram_inputs["scenario_id"] = scenario_id

    style_options = ["Raw V0.5 (Stable)", "Pro English V1.0"]
    style_default = diagram_inputs.get("style")
    if style_default is None:
        style_default = style_options[0]
    if style_default not in style_options:
        style_default = style_options[0]
    style = st.selectbox(
        "Style",
        style_options,
        index=style_options.index(style_default),
        key="diagram_inputs.style",
    )
    diagram_inputs["style"] = style

    ac_blocks_total = max(len(pcs_counts), _safe_int(ac_output.get("num_blocks"), 0), 1)
    group_default = _safe_int(diagram_inputs.get("group_index"), 1)
    group_default = max(1, min(group_default, ac_blocks_total))
    group_index = st.selectbox(
        "AC Block Group",
        list(range(1, ac_blocks_total + 1)),
        index=group_default - 1,
        key="diagram_inputs.group_index",
        disabled=not has_prereq,
    )
    diagram_inputs["group_index"] = group_index

    pcs_count = pcs_counts[group_index - 1] if pcs_counts and group_index > 0 else 0
    st.caption(f"Selected group PCS count: {pcs_count or 'TBD'}")

    st.subheader("Chain Parameters")
    c1, c2, c3 = st.columns(3)
    mv_kv_default = diagram_inputs.get("mv_kv")
    if mv_kv_default is None:
        mv_kv_default = mv_kv_value if mv_kv_value is not None else 33.0
    mv_kv = c1.number_input(
        "MV nominal voltage (kV)",
        min_value=1.0,
        value=float(mv_kv_default),
        key="diagram_inputs.mv_kv",
        step=0.1,
        disabled=not has_prereq,
    )
    diagram_inputs["mv_kv"] = mv_kv

    lv_v_default = diagram_inputs.get("lv_v")
    if lv_v_default is None:
        lv_v_default = lv_v_value if lv_v_value is not None else 690.0
    pcs_lv_v = c2.number_input(
        "PCS LV voltage (V_LL,rms)",
        min_value=100.0,
        value=float(lv_v_default),
        key="diagram_inputs.lv_v",
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
        value=float(transformer_mva_default or 5.0),
        key="diagram_inputs.transformer_mva",
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
        value=float(pcs_rating_default or 1250.0),
        key="diagram_inputs.pcs_rating_kw",
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
        value=float(dc_block_default or 5.106),
        key="diagram_inputs.dc_block_energy_mwh",
        step=0.001,
        disabled=not has_prereq,
    )
    diagram_inputs["dc_block_energy_mwh"] = dc_block_energy_mwh

    st.subheader("DC Block Allocation (per feeder)")
    ac_blocks_override = _safe_int(diagram_inputs.get("ac_blocks_total_override"), 0)
    default_dc_blocks = _resolve_dc_blocks_per_feeder(
        stage13_output, ac_output, dc_summary, pcs_count or 0, group_index, ac_blocks_override
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

    dc_df_key = "diagram_inputs.dc_blocks_df"
    stored_df = st.session_state.get(dc_df_key)
    if isinstance(stored_df, pd.DataFrame) and len(stored_df) != len(dc_df):
        st.session_state.pop(dc_df_key)
    st.session_state.setdefault(dc_df_key, dc_df)

    # Use a simpler key that doesn't conflict with session_state assignment
    dc_df = st.data_editor(
        st.session_state[dc_df_key],
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        disabled=not has_prereq,
    )
    st.session_state[dc_df_key] = dc_df

    dc_blocks_per_feeder = [
        _safe_int(row.get("dc_block_count"), 0) for row in dc_df.to_dict("records")
    ]
    diagram_inputs["dc_blocks_per_feeder"] = dc_blocks_per_feeder

    with st.expander("Advanced Settings (Manual Debugging)"):
        st.caption("Adjust layout parameters for the generated diagram.")
        prefs = load_preferences()
        default_width = prefs.get("sld_svg_width", 1400)
        default_height = prefs.get("sld_svg_height", 900)

        adv_c1, adv_c2 = st.columns(2)
        svg_width = adv_c1.number_input(
            "SVG Width", value=int(diagram_inputs.get("svg_width", default_width)), step=50, key="diagram_inputs.svg_width"
        )
        svg_height = adv_c2.number_input(
            "SVG Height", value=int(diagram_inputs.get("svg_height", default_height)), step=50, key="diagram_inputs.svg_height"
        )
        diagram_inputs["svg_width"] = svg_width
        diagram_inputs["svg_height"] = svg_height

        st.caption("Layout Spacing & Scaling")
        l1, l2, l3 = st.columns(3)
        pcs_gap = l1.slider("PCS Gap (px)", 20, 100, int(diagram_inputs.get("pcs_gap", 60)), key="diagram_inputs.pcs_gap")
        busbar_gap = l2.slider("Busbar Gap (px)", 10, 50, int(diagram_inputs.get("busbar_gap", 22)), key="diagram_inputs.busbar_gap")
        font_scale = l3.slider("Font Scale", 0.5, 1.5, float(diagram_inputs.get("font_scale", 1.0)), 0.1, key="diagram_inputs.font_scale")
        
        diagram_inputs["pcs_gap"] = pcs_gap
        diagram_inputs["busbar_gap"] = busbar_gap
        diagram_inputs["font_scale"] = font_scale

        st.caption("Override Calculations")
        manual_ac_blocks = st.number_input(
            "Total AC Blocks (for allocation)", 
            min_value=1, 
            value=int(diagram_inputs.get("ac_blocks_total_override") or ac_blocks_total),
            key="diagram_inputs.ac_blocks_total_override"
        )
        diagram_inputs["ac_blocks_total_override"] = manual_ac_blocks

        if st.button("Save SLD Settings as Default", key="save_sld_defaults"):
            save_preferences({
                "sld_svg_width": svg_width,
                "sld_svg_height": svg_height
            })
            st.success("SLD settings saved as default.")

        st.caption("Override Calculations")
        manual_ac_blocks = st.number_input(
            "Total AC Blocks (for allocation)", 
            min_value=1, 
            value=int(ac_blocks_total),
            key="diagram_inputs.ac_blocks_total_override"
        )
        if manual_ac_blocks != ac_blocks_total:
            # If user overrides, we might need to re-calculate defaults.
            # But defaults are calculated before this.
            # We can store it in session state and trigger rerun?
            # Or just use it for next run.
            # For now, let's just update the variable used for allocation logic if possible.
            # But allocation logic is in `_resolve_dc_blocks_per_feeder` which is called earlier.
            # So we need to move this input up or reload.
            pass

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
        "svg_width": svg_width,
        "svg_height": svg_height,
        "pcs_gap": pcs_gap,
        "busbar_gap": busbar_gap,
        "font_scale": font_scale,
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
                        svg_result, warning = render_sld_pro_svg(spec, svg_path)
                        if svg_result is None:
                            st.error(warning or "SLD renderer unavailable.")
                        else:
                            if warning:
                                st.warning(warning)
                            svg_bytes = svg_path.read_bytes() if svg_path.exists() else None
                            png_bytes = _svg_bytes_to_png(svg_bytes) if svg_bytes and cairosvg_ok else None
                            if svg_bytes and png_bytes is None and not cairosvg_ok:
                                st.warning("Missing dependency: cairosvg. PNG export skipped.")
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
                        png_bytes = _svg_bytes_to_png(svg_bytes) if svg_bytes and cairosvg_ok else None
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
                        png_bytes = _svg_bytes_to_png(svg_bytes) if svg_bytes and cairosvg_ok else None

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
                outputs_dir = Path("outputs")
                outputs_dir.mkdir(exist_ok=True)
                if svg_bytes:
                    svg_path = outputs_dir / "sld_latest.svg"
                    svg_path.write_bytes(svg_bytes)
                    diagram_outputs.sld_svg_path = str(svg_path)
                    st.session_state["sld_svg_path"] = str(svg_path)
                if png_bytes:
                    png_path = outputs_dir / "sld_latest.png"
                    png_path.write_bytes(png_bytes)
                    diagram_outputs.sld_png_path = str(png_path)
                    st.session_state["sld_png_path"] = str(png_path)
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
            value=int(diagram_inputs.get("zoom") if diagram_inputs.get("zoom") is not None else 100),
            key="diagram_inputs.zoom",
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
