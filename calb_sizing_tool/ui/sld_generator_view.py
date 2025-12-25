import json
import tempfile
from pathlib import Path

import streamlit as st

from calb_sizing_tool.sld import (
    append_dc_block_function_blocks,
    build_iidm_network_from_snapshot,
    build_sld_snapshot_v1,
    render_sld_svg,
    run_sld_qc,
)

try:
    import pypowsybl  # noqa: F401

    POWSYBL_AVAILABLE = True
except Exception:
    POWSYBL_AVAILABLE = False


def _build_project_inputs(stage13_output: dict) -> dict:
    return {
        "project_name": stage13_output.get("project_name"),
        "poi_power_requirement_mw": stage13_output.get("poi_power_req_mw"),
        "poi_energy_requirement_mwh": stage13_output.get("poi_energy_req_mwh"),
        "poi_energy_guarantee_mwh": stage13_output.get("poi_energy_req_mwh"),
        "poi_nominal_voltage_kv": stage13_output.get("poi_nominal_voltage_kv"),
        "poi_frequency_hz": stage13_output.get("poi_frequency_hz"),
    }


def _build_stage4_output(stage13_output: dict, ac_output: dict, dc_summary: dict) -> dict:
    output = {}
    output.update(ac_output or {})
    output["project_name"] = stage13_output.get("project_name")
    output["dc_block_total_qty"] = stage13_output.get("dc_block_total_qty")
    output["container_count"] = stage13_output.get("container_count")
    output["cabinet_count"] = stage13_output.get("cabinet_count")
    output["ac_blocks_total"] = ac_output.get("num_blocks") if ac_output else None

    dc_block = dc_summary.get("dc_block") if isinstance(dc_summary, dict) else None
    if dc_block is not None:
        output["dc_block_unit_mwh"] = getattr(dc_block, "capacity_mwh", None)
        output["dc_total_energy_mwh"] = (
            getattr(dc_block, "capacity_mwh", 0.0) * getattr(dc_block, "count", 0)
        )
    return output


def show():
    st.header("SLD Generator (PowSyBl)")
    st.caption("Beta: generates a single MV-node chain (RMU -> TR -> 1 AC block with 4 feeders).")

    if not POWSYBL_AVAILABLE:
        st.warning("pypowsybl is not installed. Install it to enable SLD generation.")
        st.code("pip install pypowsybl")
        return

    if "stage13_output" not in st.session_state:
        st.warning("Run DC sizing first to generate SLD snapshot inputs.")
        return
    if "ac_output" not in st.session_state:
        st.warning("Run AC sizing first to generate SLD snapshot inputs.")
        return

    stage13_output = st.session_state.get("stage13_output", {})
    ac_output = st.session_state.get("ac_output", {})
    dc_summary = st.session_state.get("dc_result_summary", {})

    scenario_default = stage13_output.get("selected_scenario", "container_only")
    scenario_id = st.selectbox("Scenario ID", [scenario_default], index=0)

    generate = st.button("Generate SLD Snapshot + SVG")

    if generate:
        project_inputs = _build_project_inputs(stage13_output)
        stage4_output = _build_stage4_output(stage13_output, ac_output, dc_summary)

        snapshot = build_sld_snapshot_v1(stage4_output, project_inputs, scenario_id)
        qc_warnings = run_sld_qc(snapshot)
        st.session_state["sld_snapshot"] = snapshot

        if qc_warnings:
            st.warning("QC warnings detected:")
            for item in qc_warnings:
                st.write(f"- {item}")
        else:
            st.success("Snapshot QC passed.")

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                svg_path = tmp_path / "sld.svg"
                metadata_path = tmp_path / "sld_metadata.json"
                final_svg_path = tmp_path / "sld_final.svg"

            network = build_iidm_network_from_snapshot(snapshot)
            render_sld_svg(
                network,
                container_id="SUB_MV_NODE_01",
                out_svg=svg_path,
                out_metadata=metadata_path,
            )

                metadata = None
                if metadata_path.exists():
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

                append_dc_block_function_blocks(svg_path, final_svg_path, snapshot, metadata)

                st.session_state["sld_svg_bytes"] = svg_path.read_bytes()
                st.session_state["sld_final_svg_bytes"] = final_svg_path.read_bytes()
                st.session_state["sld_metadata_bytes"] = (
                    metadata_path.read_bytes() if metadata_path.exists() else None
                )
                st.session_state["sld_snapshot_json"] = json.dumps(
                    snapshot, indent=2, sort_keys=True
                )
        except Exception as exc:
            st.error(f"SLD generation failed: {exc}")
            return

        st.success("SLD SVG generated.")

    final_svg_bytes = st.session_state.get("sld_final_svg_bytes")
    if final_svg_bytes:
        st.subheader("Preview")
        st.components.v1.html(final_svg_bytes.decode("utf-8"), height=600, scrolling=True)

        st.subheader("Downloads")
        st.download_button(
            "Download snapshot.json",
            st.session_state.get("sld_snapshot_json", ""),
            "sld_snapshot.json",
            "application/json",
        )
        st.download_button(
            "Download sld.svg",
            st.session_state.get("sld_svg_bytes"),
            "sld.svg",
            "image/svg+xml",
        )
        if st.session_state.get("sld_metadata_bytes"):
            st.download_button(
                "Download sld_metadata.json",
                st.session_state.get("sld_metadata_bytes"),
                "sld_metadata.json",
                "application/json",
            )
        st.download_button(
            "Download sld_final.svg",
            st.session_state.get("sld_final_svg_bytes"),
            "sld_final.svg",
            "image/svg+xml",
        )
