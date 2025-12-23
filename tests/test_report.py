import pytest

from calb_sizing_tool.reporting import export_docx


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

    stage1 = {
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
    }

    dc_output = {
        "stage1": stage1,
        "selected_scenario": "container_only",
    }

    ac_bytes = export_docx.create_ac_report(ac_output, report_context)
    assert isinstance(ac_bytes, (bytes, bytearray))
    assert len(ac_bytes) > 0

    combined_bytes = export_docx.create_combined_report(dc_output, ac_output, report_context)
    assert isinstance(combined_bytes, (bytes, bytearray))
    assert len(combined_bytes) > 0


if __name__ == "__main__":
    pytest.main([__file__])
