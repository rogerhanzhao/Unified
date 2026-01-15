#!/usr/bin/env python3
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
Validation script for report generation logic.
Checks data consistency, efficiency chain, AC block aggregation, etc.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Sample golden test cases
GOLDEN_TEST_CASES = [
    {
        "name": "100MW_400MWh",
        "poi_power_mw": 100.0,
        "poi_energy_mwh": 400.0,
        "guarantee_year": 10,
        "expected_dc_blocks": 90,
        "expected_ac_blocks": 23,
        "expected_pcs_per_block": 2,
        "expected_pcs_total": 46,
    },
    {
        "name": "75MW_300MWh",
        "poi_power_mw": 75.0,
        "poi_energy_mwh": 300.0,
        "guarantee_year": 10,
        "expected_dc_blocks": 68,
        "expected_ac_blocks": 17,
        "expected_pcs_per_block": 2,
        "expected_pcs_total": 34,
    },
    {
        "name": "50MW_200MWh",
        "poi_power_mw": 50.0,
        "poi_energy_mwh": 200.0,
        "guarantee_year": 10,
        "expected_dc_blocks": 45,
        "expected_ac_blocks": 12,
        "expected_pcs_per_block": 2,
        "expected_pcs_total": 24,
    },
]


def check_efficiency_chain(ctx: Dict[str, Any]) -> List[str]:
    """
    Validate efficiency chain data consistency.
    Returns list of issues found (empty if OK).
    """
    issues = []
    
    efficiency_chain = ctx.get("efficiency_chain_oneway_frac", 0.0)
    components = ctx.get("efficiency_components_frac", {})
    
    if not efficiency_chain or efficiency_chain <= 0:
        issues.append("Efficiency chain is zero or missing")
        return issues
    
    # Calculate product of components
    product = 1.0
    component_names = [
        "eff_dc_cables_frac",
        "eff_pcs_frac",
        "eff_mvt_frac",
        "eff_ac_cables_sw_rmu_frac",
        "eff_hvt_others_frac",
    ]
    
    for comp_name in component_names:
        val = components.get(comp_name, 0.0)
        if val <= 0:
            issues.append(f"Component '{comp_name}' is zero or missing")
        else:
            product *= val
    
    # Check if product matches total (within 2% tolerance)
    if abs(product - efficiency_chain) / efficiency_chain > 0.02:
        issues.append(
            f"Efficiency chain mismatch: product={product:.6f}, total={efficiency_chain:.6f}. "
            f"Relative error={abs(product - efficiency_chain) / efficiency_chain * 100:.2f}%"
        )
    
    return issues


def check_ac_block_aggregation(ac_blocks_total: int, pcs_per_block: int, pcs_modules_total: int) -> List[str]:
    """
    Validate AC block configuration consistency.
    Returns list of issues found (empty if OK).
    """
    issues = []
    
    expected_pcs = ac_blocks_total * pcs_per_block
    if expected_pcs != pcs_modules_total:
        issues.append(
            f"PCS count mismatch: expected={expected_pcs} "
            f"(AC blocks={ac_blocks_total} × PCS/block={pcs_per_block}), "
            f"got={pcs_modules_total}"
        )
    
    return issues


def check_power_consistency(
    ac_blocks_total: int,
    ac_block_size_mw: float,
    poi_power_mw: float,
) -> List[str]:
    """
    Validate power balance consistency.
    Returns list of issues found (empty if OK).
    """
    issues = []
    
    if not ac_block_size_mw or ac_block_size_mw <= 0:
        issues.append("AC block size is zero or missing")
        return issues
    
    total_ac_power = ac_blocks_total * ac_block_size_mw
    
    # Allow 10% overbuild (common in BESS sizing)
    margin = 0.1
    if total_ac_power < poi_power_mw * (1 - margin):
        issues.append(
            f"AC power undersized: total={total_ac_power:.2f}MW < "
            f"POI requirement={poi_power_mw:.2f}MW"
        )
    
    if total_ac_power > poi_power_mw * (1 + margin):
        overbuild_pct = (total_ac_power - poi_power_mw) / poi_power_mw * 100
        if overbuild_pct > 15:  # Only warn if > 15%
            issues.append(
                f"AC power overbuild is {overbuild_pct:.1f}% "
                f"(total={total_ac_power:.2f}MW, POI requirement={poi_power_mw:.2f}MW)"
            )
    
    return issues


def validate_report_context(ctx: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Run comprehensive validation of report context.
    Returns (is_valid, list_of_issues).
    """
    issues = []
    
    # Efficiency chain validation
    eff_issues = check_efficiency_chain(ctx)
    issues.extend(eff_issues)
    
    # AC block count validation
    ac_issues = check_ac_block_aggregation(
        ctx.get("ac_blocks_total", 0),
        ctx.get("pcs_per_block", 0),
        ctx.get("pcs_modules_total", 0),
    )
    issues.extend(ac_issues)
    
    # Power consistency validation
    power_issues = check_power_consistency(
        ctx.get("ac_blocks_total", 0),
        ctx.get("ac_block_size_mw", 0.0),
        ctx.get("poi_power_requirement_mw", 0.0),
    )
    issues.extend(power_issues)
    
    is_valid = len(issues) == 0
    return is_valid, issues


def print_validation_report(name: str, ctx: Dict[str, Any]):
    """Pretty-print validation report for a context."""
    print(f"\n{'='*70}")
    print(f"Validation Report: {name}")
    print(f"{'='*70}")
    
    is_valid, issues = validate_report_context(ctx)
    
    if is_valid:
        print("✅ All validation checks passed!")
    else:
        print("❌ Validation issues found:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    
    # Print key metrics
    print(f"\nKey Metrics:")
    print(f"  POI Power: {ctx.get('poi_power_requirement_mw', 'N/A')} MW")
    print(f"  POI Energy: {ctx.get('poi_energy_requirement_mwh', 'N/A')} MWh")
    print(f"  DC Blocks: {ctx.get('dc_blocks_total', 'N/A')}")
    print(f"  AC Blocks: {ctx.get('ac_blocks_total', 'N/A')}")
    print(f"  PCS/Block: {ctx.get('pcs_per_block', 'N/A')}")
    print(f"  Total PCS: {ctx.get('pcs_modules_total', 'N/A')}")
    print(f"  AC Block Size: {ctx.get('ac_block_size_mw', 'N/A')} MW")
    print(f"  Efficiency Chain: {ctx.get('efficiency_chain_oneway_frac', 'N/A')}")
    
    return is_valid


if __name__ == "__main__":
    # Example golden contexts (would be loaded from saved outputs in real scenario)
    example_ctx = {
        "poi_power_requirement_mw": 100.0,
        "poi_energy_requirement_mwh": 400.0,
        "dc_blocks_total": 90,
        "ac_blocks_total": 23,
        "pcs_per_block": 2,
        "pcs_modules_total": 46,
        "ac_block_size_mw": 5.0,
        "efficiency_chain_oneway_frac": 0.9674,  # 96.74%
        "efficiency_components_frac": {
            "eff_dc_cables_frac": 0.97,
            "eff_pcs_frac": 0.97,
            "eff_mvt_frac": 0.985,
            "eff_ac_cables_sw_rmu_frac": 0.98,
            "eff_hvt_others_frac": 0.98,
        },
    }
    
    print_validation_report("Example: 100MW/400MWh", example_ctx)
    
    # Test with incorrect efficiency chain
    bad_ctx = example_ctx.copy()
    bad_ctx["efficiency_chain_oneway_frac"] = 0.85  # Wrong!
    print_validation_report("Example: Bad Efficiency", bad_ctx)
    
    # Test with PCS count mismatch
    mismatch_ctx = example_ctx.copy()
    mismatch_ctx["pcs_modules_total"] = 50  # Should be 46
    print_validation_report("Example: PCS Count Mismatch", mismatch_ctx)
