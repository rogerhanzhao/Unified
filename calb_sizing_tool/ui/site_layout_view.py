import json
import tempfile
from dataclasses import asdict
from pathlib import Path

import streamlit as st

from calb_diagrams.layout_block_renderer import render_layout_block_svg
from calb_diagrams.specs import build_layout_block_spec


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


def show():
    st.header("Site Layout")
    st.caption("Template block layout (abstract engineering view).")

    stage13_output = st.session_state.get("stage13_output", {}) or {}
    ac_output = st.session_state.get("ac_output", {}) or {}

    if not stage13_output or not ac_output:
        st.warning("Run DC sizing and AC sizing first to generate layout inputs.")
        return

    stored_inputs = st.session_state.get("layout_inputs", {}) or {}

    ac_blocks_total = _safe_int(ac_output.get("num_blocks"), 0) or 1
    block_options = list(range(1, ac_blocks_total + 1))
    default_blocks = stored_inputs.get("block_indices_to_render") or [1]
    if isinstance(default_blocks, int):
        default_blocks = [default_blocks]
    default_blocks = [b for b in default_blocks if b in block_options] or [1]

    selected_blocks = st.multiselect(
        "Blocks to render",
        block_options,
        default=default_blocks,
    )
    if not selected_blocks:
        selected_blocks = [1]

    arrangement = st.selectbox(
        "DC Block arrangement",
        ["2x2", "1x4", "4x1"],
        index=["2x2", "1x4", "4x1"].index(stored_inputs.get("arrangement", "2x2")),
    )
    show_skid = st.checkbox("Show PCS&MVT SKID", value=stored_inputs.get("show_skid", True))

    mv_kv = _safe_float(ac_output.get("grid_kv"), 33.0)
    lv_v = _safe_float(ac_output.get("inverter_lv_v"), 690.0)
    transformer_mva = _safe_float(ac_output.get("transformer_kva"), 0.0) / 1000.0
    if transformer_mva <= 0 and _safe_float(ac_output.get("block_size_mw"), 0.0) > 0:
        transformer_mva = _safe_float(ac_output.get("block_size_mw"), 5.0) / 0.9

    st.subheader("Labels")
    block_title = st.text_input(
        "Block title template",
        value=stored_inputs.get("block_title") or "Block {index}",
    )
    bess_range_text = st.text_input(
        "BESS range text template",
        value=stored_inputs.get("bess_range_text") or "BESS {start}~{end}",
    )
    skid_text = st.text_input(
        "SKID label",
        value=stored_inputs.get("skid_text") or "PCS&MVT SKID",
    )
    skid_subtext_default = f"{mv_kv:.1f} kV / {lv_v:.0f} V, {transformer_mva:.1f} MVA"
    skid_subtext = st.text_input(
        "SKID subtext",
        value=stored_inputs.get("skid_subtext") or skid_subtext_default,
    )

    labels = {
        "block_title": block_title,
        "bess_range_text": bess_range_text,
        "skid_text": skid_text,
        "skid_subtext": skid_subtext,
    }

    generate = st.button("Generate Layout")
    st.session_state["layout_inputs"] = {
        "block_indices_to_render": selected_blocks,
        "arrangement": arrangement,
        "show_skid": show_skid,
        **labels,
    }

    if generate:
        try:
            spec = build_layout_block_spec(
                ac_output=ac_output,
                block_indices_to_render=selected_blocks,
                labels=labels,
                arrangement=arrangement,
                show_skid=show_skid,
            )
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                svg_path = tmp_path / "layout_block.svg"
                png_path = tmp_path / "layout_block.png"
                svg_result, warning = render_layout_block_svg(spec, svg_path, png_path)
                if svg_result is None:
                    st.error(warning or "Layout renderer unavailable.")
                    st.code("pip install svgwrite")
                else:
                    if warning:
                        st.warning(warning)
                        if "cairosvg" in warning.lower():
                            st.code("pip install cairosvg")

                    if svg_path.exists():
                        st.session_state["layout_svg_bytes"] = svg_path.read_bytes()
                    if png_path.exists():
                        png_bytes = png_path.read_bytes()
                        st.session_state["layout_png_bytes"] = png_bytes
                        st.session_state["layout_png_meta"] = {
                            "generated_at": __import__("datetime")
                            .datetime.now()
                            .isoformat(timespec="seconds"),
                            "hash": __import__("hashlib")
                            .sha256(png_bytes)
                            .hexdigest()[:12],
                        }
                    st.session_state["layout_spec_json"] = json.dumps(
                        asdict(spec), indent=2, sort_keys=True
                    )
        except Exception as exc:
            st.error(f"Layout generation failed: {exc}")

    layout_png = st.session_state.get("layout_png_bytes")
    layout_svg = st.session_state.get("layout_svg_bytes")
    if layout_png or layout_svg:
        st.subheader("Preview")
        if layout_png:
            st.image(layout_png, use_container_width=True)
        else:
            st.components.v1.html(layout_svg.decode("utf-8"), height=640, scrolling=True)

        st.subheader("Downloads")
        if st.session_state.get("layout_spec_json"):
            st.download_button(
                "Download layout_spec.json",
                st.session_state.get("layout_spec_json"),
                "layout_spec.json",
                "application/json",
            )
        if layout_svg:
            st.download_button(
                "Download layout_block.svg",
                layout_svg,
                "layout_block.svg",
                "image/svg+xml",
            )
        if layout_png:
            st.download_button(
                "Download layout_block.png",
                layout_png,
                "layout_block.png",
                "image/png",
            )
