"""
Test suite for report context and validation.
Ensures report data sources are consistent and complete.
"""
import pytest
from dataclasses import asdict

from calb_sizing_tool.reporting.report_context import (
    build_report_context,
    validate_report_context,
)


def test_report_context_basic_build():
    """Test building a basic report context with minimal data."""
    stage13_output = {
        "project_name": "Test Project",
        "poi_power_req_mw": 100.0,
        "poi_energy_req_mwh": 500.0,
        "poi_guarantee_year": 10,
        "project_life_years": 25,
        "cycles_per_year": 365,
        "eff_dc_to_poi_frac": 0.85,
        "eff_dc_cables_frac": 0.97,
        "eff_pcs_frac": 0.97,
        "eff_mvt_frac": 0.98,
        "eff_ac_cables_sw_rmu_frac": 0.98,
        "eff_hvt_others_frac": 0.98,
        "dc_block_total_qty": 4,
        "container_count": 4,
        "cabinet_count": 0,
        "poi_frequency_hz": 50,
        "selected_scenario": "container_only",
        "stage2_raw": {
            "container_count": 4,
            "cabinet_count": 0,
            "dc_nameplate_bol_mwh": 500.0,
            "oversize_mwh": 10.0,
            "block_config_table_records": [],
        },
        "stage3_meta": {},
    }
    
    ac_output = {
        "num_blocks": 2,
        "block_size_mw": 50.0,
        "pcs_count_total": 8,
        "pcs_count_by_block": [4, 4],
        "mv_voltage_kv": 33.0,
        "lv_voltage_v": 690.0,
        "grid_power_factor": 0.95,
        "transformer_kva": 52631.6,
    }
    
    ctx = build_report_context(
        session_state={},
        stage_outputs={
            "stage13_output": stage13_output,
            "ac_output": ac_output,
        },
        project_inputs={
            "poi_power_mw": 100.0,
            "poi_energy_mwh": 500.0,
            "poi_energy_guarantee_mwh": 500.0,
            "poi_guarantee_year": 10,
        }
    )
    
    # Verify context is built
    assert ctx.project_name == "Test Project"
    assert ctx.poi_power_requirement_mw == 100.0
    assert ctx.poi_energy_requirement_mwh == 500.0
    assert ctx.poi_energy_guarantee_mwh == 500.0
    assert ctx.poi_guarantee_year == 10
    assert ctx.dc_blocks_total == 4
    assert ctx.ac_blocks_total == 2
    assert ctx.pcs_modules_total == 8


def test_report_context_with_stage3_data():
    """Test that stage3 DataFrame is properly stored in context."""
    import pandas as pd
    
    stage13_output = {
        "project_name": "Test Project",
        "poi_power_req_mw": 100.0,
        "poi_energy_req_mwh": 500.0,
        "poi_guarantee_year": 10,
        "project_life_years": 25,
        "cycles_per_year": 365,
        "eff_dc_to_poi_frac": 0.85,
        "eff_dc_cables_frac": 0.97,
        "eff_pcs_frac": 0.97,
        "eff_mvt_frac": 0.98,
        "eff_ac_cables_sw_rmu_frac": 0.98,
        "eff_hvt_others_frac": 0.98,
        "dc_block_total_qty": 4,
        "selected_scenario": "container_only",
        "stage2_raw": {},
        "stage3_meta": {},
    }
    
    # Create a simple stage3 DataFrame
    stage3_df = pd.DataFrame({
        "Year_Index": [0, 5, 10],
        "POI_Usable_Energy_MWh": [500.0, 485.0, 470.0],
        "DC_RTE_Pct": [88.0, 86.5, 85.0],
        "System_RTE_Pct": [62.0, 60.5, 59.0],
        "DC_Usable_MWh": [588.0, 561.0, 554.0],
        "SOH_Absolute_Pct": [100.0, 97.0, 94.0],
    })
    
    ac_output = {
        "num_blocks": 2,
        "block_size_mw": 50.0,
        "pcs_count_total": 8,
    }
    
    ctx = build_report_context(
        session_state={},
        stage_outputs={
            "stage13_output": stage13_output,
            "stage3_df": stage3_df,
            "ac_output": ac_output,
        },
        project_inputs={
            "poi_energy_guarantee_mwh": 500.0,
            "poi_guarantee_year": 10,
        }
    )
    
    # Verify stage3 data is stored
    assert ctx.stage3_df is not None
    assert not ctx.stage3_df.empty
    assert len(ctx.stage3_df) == 3
    assert ctx.poi_usable_energy_mwh_at_year0 == 500.0
    assert ctx.poi_usable_energy_mwh_at_guarantee_year == 470.0


def test_validate_report_context_power_mismatch():
    """Test validation detects AC power mismatch."""
    from calb_sizing_tool.reporting.report_context import ReportContext
    
    ctx = ReportContext(
        project_name="Test",
        scenario_id="test",
        poi_power_requirement_mw=100.0,
        poi_energy_requirement_mwh=500.0,
        poi_energy_guarantee_mwh=500.0,
        poi_usable_energy_mwh_at_guarantee_year=None,
        poi_usable_energy_mwh_at_year0=None,
        poi_guarantee_year=10,
        project_life_years=25,
        cycles_per_year=365,
        grid_mv_voltage_kv_ac=33.0,
        pcs_lv_voltage_v_ll_rms_ac=690.0,
        grid_power_factor=0.95,
        ac_block_template_id="2x1",
        pcs_per_block=2,
        feeders_per_block=1,
        dc_blocks_total=4,
        ac_blocks_total=2,
        pcs_modules_total=4,
        transformer_rating_kva=52000.0,
        ac_block_size_mw=45.0,  # Mismatch: 2 blocks × 45 = 90, but POI = 100
        dc_block_unit_mwh=125.0,
        dc_total_energy_mwh=500.0,
        efficiency_chain_oneway_frac=0.85,
        efficiency_components_frac={},
        avg_dc_blocks_per_ac_block=2.0,
        dc_blocks_allocation=[],
        qc_checks=[],
        dictionary_version_dc="v13",
        dictionary_version_ac="v5",
    )
    
    warnings = validate_report_context(ctx)
    assert len(warnings) > 0
    assert any("AC total power" in w for w in warnings)


def test_validate_report_context_guarantee_year_exceeded():
    """Test validation detects guarantee year exceeding project life."""
    from calb_sizing_tool.reporting.report_context import ReportContext
    
    ctx = ReportContext(
        project_name="Test",
        scenario_id="test",
        poi_power_requirement_mw=100.0,
        poi_energy_requirement_mwh=500.0,
        poi_energy_guarantee_mwh=500.0,
        poi_usable_energy_mwh_at_guarantee_year=None,
        poi_usable_energy_mwh_at_year0=None,
        poi_guarantee_year=30,  # Exceeds project life
        project_life_years=25,
        cycles_per_year=365,
        grid_mv_voltage_kv_ac=33.0,
        pcs_lv_voltage_v_ll_rms_ac=690.0,
        grid_power_factor=0.95,
        ac_block_template_id="2x1",
        pcs_per_block=2,
        feeders_per_block=1,
        dc_blocks_total=4,
        ac_blocks_total=2,
        pcs_modules_total=4,
        transformer_rating_kva=52000.0,
        ac_block_size_mw=50.0,
        dc_block_unit_mwh=125.0,
        dc_total_energy_mwh=500.0,
        efficiency_chain_oneway_frac=0.85,
        efficiency_components_frac={},
        avg_dc_blocks_per_ac_block=2.0,
        dc_blocks_allocation=[],
        qc_checks=[],
        dictionary_version_dc="v13",
        dictionary_version_ac="v5",
    )
    
    warnings = validate_report_context(ctx)
    assert len(warnings) > 0
    assert any("Guarantee year" in w and "exceeds" in w for w in warnings)


def test_validate_report_context_poi_usable_below_guarantee():
    """Test validation detects POI usable below guarantee."""
    from calb_sizing_tool.reporting.report_context import ReportContext
    
    ctx = ReportContext(
        project_name="Test",
        scenario_id="test",
        poi_power_requirement_mw=100.0,
        poi_energy_requirement_mwh=500.0,
        poi_energy_guarantee_mwh=500.0,
        poi_usable_energy_mwh_at_guarantee_year=480.0,  # Below guarantee
        poi_usable_energy_mwh_at_year0=500.0,
        poi_guarantee_year=10,
        project_life_years=25,
        cycles_per_year=365,
        grid_mv_voltage_kv_ac=33.0,
        pcs_lv_voltage_v_ll_rms_ac=690.0,
        grid_power_factor=0.95,
        ac_block_template_id="2x1",
        pcs_per_block=2,
        feeders_per_block=1,
        dc_blocks_total=4,
        ac_blocks_total=2,
        pcs_modules_total=4,
        transformer_rating_kva=52000.0,
        ac_block_size_mw=50.0,
        dc_block_unit_mwh=125.0,
        dc_total_energy_mwh=500.0,
        efficiency_chain_oneway_frac=0.85,
        efficiency_components_frac={},
        avg_dc_blocks_per_ac_block=2.0,
        dc_blocks_allocation=[],
        qc_checks=[],
        dictionary_version_dc="v13",
        dictionary_version_ac="v5",
    )
    
    warnings = validate_report_context(ctx)
    assert len(warnings) > 0
    assert any("POI usable energy" in w and "below" in w for w in warnings)


def test_validate_report_context_pcs_mismatch():
    """Test validation detects PCS count mismatch."""
    from calb_sizing_tool.reporting.report_context import ReportContext
    
    ctx = ReportContext(
        project_name="Test",
        scenario_id="test",
        poi_power_requirement_mw=100.0,
        poi_energy_requirement_mwh=500.0,
        poi_energy_guarantee_mwh=500.0,
        poi_usable_energy_mwh_at_guarantee_year=None,
        poi_usable_energy_mwh_at_year0=None,
        poi_guarantee_year=10,
        project_life_years=25,
        cycles_per_year=365,
        grid_mv_voltage_kv_ac=33.0,
        pcs_lv_voltage_v_ll_rms_ac=690.0,
        grid_power_factor=0.95,
        ac_block_template_id="4x1",
        pcs_per_block=4,
        feeders_per_block=1,
        dc_blocks_total=4,
        ac_blocks_total=2,
        pcs_modules_total=6,  # Should be 8 (2 blocks × 4 PCS)
        transformer_rating_kva=52000.0,
        ac_block_size_mw=50.0,
        dc_block_unit_mwh=125.0,
        dc_total_energy_mwh=500.0,
        efficiency_chain_oneway_frac=0.85,
        efficiency_components_frac={},
        avg_dc_blocks_per_ac_block=2.0,
        dc_blocks_allocation=[],
        qc_checks=[],
        dictionary_version_dc="v13",
        dictionary_version_ac="v5",
    )
    
    warnings = validate_report_context(ctx)
    assert len(warnings) > 0
    assert any("PCS module count mismatch" in w for w in warnings)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
