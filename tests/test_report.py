import io

from docx import Document

from calb_sizing_tool.config import DC_DATA_PATH
from calb_sizing_tool.reporting import export_docx
from calb_sizing_tool.ui import dc_view


def _doc_from_bytes(data):
    if hasattr(data, "getvalue"):
        data = data.getvalue()
    return Document(io.BytesIO(data))


def _paragraph_texts(doc: Document):
    return [p.text for p in doc.paragraphs]


def _strip_timestamp_lines(texts):
    cleaned = []
    for text in texts:
        lines = [line for line in text.splitlines() if not line.startswith("Date:")]
        cleaned.append("\n".join(lines))
    return cleaned


def _build_stage1():
    defaults, df_blocks, df_soh_profile, df_soh_curve, df_rte_profile, df_rte_curve = dc_view.load_data(DC_DATA_PATH)
    inputs = {
        "project_name": "Unit Test Project",
        "poi_power_req_mw": 100.0,
        "poi_energy_req_mwh": 400.0,
        "eff_dc_cables": 99.5,
        "eff_pcs": 98.5,
        "eff_mvt": 99.5,
        "eff_ac_cables_sw_rmu": 99.2,
        "eff_hvt_others": 100.0,
        "sc_time_months": 3,
        "dod_pct": 97.0,
        "dc_round_trip_efficiency_pct": 94.0,
        "project_life_years": 20,
        "cycles_per_year": 365,
        "poi_guarantee_year": 0,
    }
    stage1 = dc_view.run_stage1(inputs, defaults)
    return stage1, df_blocks, df_soh_profile, df_soh_curve, df_rte_profile, df_rte_curve


def test_setup_header_callable():
    assert callable(export_docx._setup_header)


def test_dc_dictionary_extraction_keys():
    spec = export_docx.extract_dc_equipment_spec()
    required = {
        "container_model",
        "cell_type",
        "configuration",
        "unit_capacity_mwh",
        "nominal_voltage_v",
        "voltage_range_v",
    }
    assert required.issubset(spec.keys())


def test_dc_report_unchanged_paragraphs():
    stage1, df_blocks, df_soh_profile, df_soh_curve, df_rte_profile, df_rte_curve = _build_stage1()
    selected = "container_only"

    s2, s3_df, s3_meta, iter_count, poi_g, converged = dc_view.size_with_guarantee(
        stage1,
        selected,
        df_blocks,
        df_soh_profile,
        df_soh_curve,
        df_rte_profile,
        df_rte_curve,
        k_max=dc_view.K_MAX_FIXED,
    )
    results = {selected: (s2, s3_df, s3_meta, iter_count, poi_g, converged)}
    report_order = [(selected, selected.replace("_", " ").title())]

    baseline = dc_view.build_report_bytes(stage1, results, report_order)
    baseline_doc = _doc_from_bytes(baseline)

    dc_output = {"stage1": stage1, "selected_scenario": selected}
    updated = export_docx.create_dc_report(dc_output, {})
    updated_doc = _doc_from_bytes(updated)

    baseline_texts = _strip_timestamp_lines(_paragraph_texts(baseline_doc))
    updated_texts = _strip_timestamp_lines(_paragraph_texts(updated_doc))
    assert baseline_texts == updated_texts


def test_combined_report_structure():
    stage1, *_ = _build_stage1()
    dc_output = {
        "stage1": stage1,
        "selected_scenario": "container_only",
        "dc_block_total_qty": 20,
    }

    ac_output = {
        "project_name": "Unit Test Project",
        "poi_power_mw": 100.0,
        "poi_energy_mwh": 400.0,
        "grid_kv": 33.0,
        "inverter_lv_v": 800.0,
        "block_size_mw": 5.0,
        "num_blocks": 20,
        "total_ac_mw": 100.0,
        "overhead_mw": 0.0,
        "pcs_power_kw": 2500.0,
        "pcs_per_block": 2,
        "total_pcs": 40,
        "transformer_kva": 5555.0,
        "transformer_count": 20,
        "dc_blocks_per_ac": 1,
        "mv_level_kv": 33.0,
    }

    ctx = {
        "project_name": "Unit Test Project",
        "inputs": {
            "Selected DC Scenario": "container_only",
            "Grid Voltage (kV)": "33",
            "Standard AC Block Size (MW)": "5.0",
        },
    }

    combined_bytes = export_docx.create_combined_report(dc_output, ac_output, ctx)
    combined_doc = _doc_from_bytes(combined_bytes)
    texts = _paragraph_texts(combined_doc)

    assert texts.count("1. Executive Summary") == 1
    assert texts.count("2. Project Inputs & Assumptions") == 1
    assert texts.count("3. DC Sizing Results") == 1

    assert "3.1 Project Summary" in texts
    assert "3.2 Equipment Summary (DC Blocks)" in texts
    assert "3.3 Lifetime POI Usable Energy & SOH (Per Configuration)" in texts

    assert "1. Project Summary" not in texts
    assert "2. Equipment Summary (DC Blocks)" not in texts
    assert "3. Lifetime POI Usable Energy & SOH (Per Configuration)" not in texts


def test_report_generation_bytes():
    ac_output = {
        "project_name": "Test Project",
        "poi_power_mw": 100.0,
        "poi_energy_mwh": 400.0,
        "grid_kv": 33.0,
        "inverter_lv_v": 800.0,
        "block_size_mw": 5.0,
        "num_blocks": 20,
        "total_ac_mw": 100.0,
        "overhead_mw": 0.0,
        "pcs_power_kw": 2500.0,
        "pcs_per_block": 2,
        "total_pcs": 40,
        "transformer_kva": 5555.0,
        "transformer_count": 20,
        "dc_blocks_per_ac": 1,
        "mv_level_kv": 33.0,
    }

    report_context = {
        "project_name": "Test Project",
        "inputs": {
            "Grid Voltage (kV)": "33",
            "Standard AC Block Size (MW)": "5.0",
        },
    }

    dc_output = {
        "stage1": {
            "project_name": "Test Project",
            "poi_power_req_mw": 100.0,
            "poi_energy_req_mwh": 400.0,
            "project_life_years": 20,
            "cycles_per_year": 365,
            "poi_guarantee_year": 0,
            "eff_dc_to_poi_frac": 0.95,
            "sc_loss_frac": 0.0,
            "dod_frac": 0.97,
            "dc_energy_capacity_required_mwh": 450.0,
            "dc_power_required_mw": 105.0,
        },
        "selected_scenario": "container_only",
        "dc_block_total_qty": 20,
    }

    ac_bytes = export_docx.create_ac_report(ac_output, report_context)
    assert isinstance(ac_bytes, (bytes, bytearray))
    assert len(ac_bytes) > 0

    combined_bytes = export_docx.create_combined_report(dc_output, ac_output, report_context)
    assert isinstance(combined_bytes, (bytes, bytearray))
    assert len(combined_bytes) > 0


if __name__ == "__main__":
    import pytest

    pytest.main([__file__])
