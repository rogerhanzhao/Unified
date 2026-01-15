# -----------------------------------------------------------------------------
# Personal Open-Source Notice
#
# Copyright (c) 2026 Alex.Zhao. All rights reserved.
#
# This repository is released under the MIT License (see LICENSE file).
# Intended use: learning, evaluation, and engineering reference for Utility-scale
# BESS/ESS sizing and Reporting workflows.
#
# DISCLAIMER: This software is provided "AS IS", without warranty of any kind,
# express or implied. In no event shall the author(s) be liable for any claim,
# damages, or other liability arising from, out of, or in connection with the
# software or the use or other dealings in the software.
#
# NOTE: This is a personal project. It is not an official product or statement
# of any company or organization.
# -----------------------------------------------------------------------------

"""
Test suite for DOCX export enhancements - efficiency chain and consistency validation.
"""
import pytest
import pandas as pd

from calb_sizing_tool.reporting.report_context import ReportContext
from calb_sizing_tool.reporting.report_v2 import (
    _validate_efficiency_chain,
    _aggregate_ac_block_configs,
    _validate_report_consistency,
)


def _make_test_context(**overrides):
    """Helper to create a ReportContext with sensible defaults."""
    defaults = {
        "project_name": "Test",
        "scenario_id": "test",
        "poi_power_requirement_mw": 100.0,
        "poi_energy_requirement_mwh": 500.0,
        "poi_energy_guarantee_mwh": 500.0,
        "poi_usable_energy_mwh_at_guarantee_year": None,
        "poi_usable_energy_mwh_at_year0": None,
        "poi_guarantee_year": 10,
        "project_life_years": 25,
        "cycles_per_year": 365,
        "grid_mv_voltage_kv_ac": 33.0,
        "pcs_lv_voltage_v_ll_rms_ac": 690.0,
        "grid_power_factor": 0.95,
        "ac_block_template_id": "2x1",
        "pcs_per_block": 2,
        "feeders_per_block": 1,
        "dc_blocks_total": 4,
        "ac_blocks_total": 2,
        "pcs_modules_total": 4,
        "transformer_rating_kva": 52000.0,
        "ac_block_size_mw": 50.0,
        "dc_block_unit_mwh": 125.0,
        "dc_total_energy_mwh": 500.0,
        "efficiency_chain_oneway_frac": 0.85,
        "efficiency_components_frac": {},
        "avg_dc_blocks_per_ac_block": 2.0,
        "dc_blocks_allocation": [],
        "qc_checks": [],
        "dictionary_version_dc": "v13",
        "dictionary_version_ac": "v5",
        "sld_snapshot_id": None,
        "sld_snapshot_hash": None,
        "sld_generated_at": None,
        "sld_group_index": None,
        "sld_preview_svg_bytes": None,
        "sld_pro_png_bytes": None,
        "layout_png_bytes": None,
        "stage1": {},
    }
    defaults.update(overrides)
    return ReportContext(**defaults)


class TestEfficiencyChainValidation:
    """Test efficiency chain validation."""
    
    def test_efficiency_chain_valid_when_all_present(self):
        """Test validation succeeds when all components are present."""
        ctx = _make_test_context(
            efficiency_chain_oneway_frac=0.890086,
            efficiency_components_frac={
                "eff_dc_cables_frac": 0.97,
                "eff_pcs_frac": 0.97,
                "eff_mvt_frac": 0.985,
                "eff_ac_cables_sw_rmu_frac": 0.98,
                "eff_hvt_others_frac": 0.98,
            },
            stage1={
                "eff_dc_cables_frac": 0.97,
                "eff_pcs_frac": 0.97,
                "eff_mvt_frac": 0.985,
                "eff_ac_cables_sw_rmu_frac": 0.98,
                "eff_hvt_others_frac": 0.98,
                "eff_dc_to_poi_frac": 0.890086,
            },
        )
        
        warnings = _validate_efficiency_chain(ctx)
        # Should have no product mismatch warnings
        assert len([w for w in warnings if "does not match product" in w]) == 0
    
    def test_efficiency_chain_warns_missing_stage1(self):
        """Test validation warns when stage1 is missing."""
        ctx = _make_test_context(stage1=None)
        
        warnings = _validate_efficiency_chain(ctx)
        assert len(warnings) > 0
        assert any("stage1" in w.lower() for w in warnings)
    
    def test_efficiency_chain_warns_missing_components(self):
        """Test validation warns when efficiency components are missing."""
        ctx = _make_test_context(
            efficiency_components_frac={
                "eff_dc_cables_frac": None,
                "eff_pcs_frac": 0.97,
            },
            stage1={},
        )
        
        warnings = _validate_efficiency_chain(ctx)
        assert len(warnings) > 0
        assert any("DC Cables" in w for w in warnings)


class TestACBlockAggregation:
    """Test AC Block configuration aggregation."""
    
    def test_aggregation_identical_blocks(self):
        """Test aggregation with identical block configs."""
        ctx = _make_test_context(
            ac_blocks_total=23,
            pcs_per_block=2,
            ac_block_size_mw=5.0,
            ac_output={
                "num_blocks": 23,
                "pcs_per_block": 2,
                "pcs_kw": 2500,
            },
        )
        
        result = _aggregate_ac_block_configs(ctx)
        assert len(result) == 1
        assert result[0]["count"] == 23
        assert result[0]["pcs_per_block"] == 2
    
    def test_aggregation_zero_blocks(self):
        """Test aggregation with zero AC blocks."""
        ctx = _make_test_context(ac_blocks_total=0)
        
        result = _aggregate_ac_block_configs(ctx)
        assert len(result) == 0


class TestReportConsistencyValidation:
    """Test report consistency checks."""
    
    def test_consistency_detects_pcs_mismatch(self):
        """Test that PCS count mismatch is detected."""
        ctx = _make_test_context(
            pcs_per_block=2,
            ac_blocks_total=2,
            pcs_modules_total=5,  # Should be 4
            stage1={},
        )
        
        warnings = _validate_report_consistency(ctx)
        assert any("PCS module count mismatch" in w for w in warnings)
    
    def test_consistency_detects_guarantee_year_exceeded(self):
        """Test that guarantee year exceeding project life is detected."""
        ctx = _make_test_context(
            poi_guarantee_year=30,
            project_life_years=25,
            stage1={},
        )
        
        warnings = _validate_report_consistency(ctx)
        assert any("Guarantee year" in w and "exceeds" in w for w in warnings)
    
    def test_consistency_warns_significant_ac_overbuild(self):
        """Test that significant AC overbuild is warned."""
        ctx = _make_test_context(
            poi_power_requirement_mw=100.0,
            ac_blocks_total=2,
            ac_block_size_mw=65.0,  # 130 MW total, 30% overbuild
            stage1={},
        )
        
        warnings = _validate_report_consistency(ctx)
        # Should have some warning about overbuild or AC power
        assert len([w for w in warnings if "overbuild" in w.lower() or "AC power" in w]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
