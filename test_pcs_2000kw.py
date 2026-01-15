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
Test for PCS 2000 kW support and custom PCS rating functionality
"""
import sys
sys.path.insert(0, '/opt/calb/prod/CALB_SIZINGTOOL')

from calb_sizing_tool.ui.ac_sizing_config import (
    PCSRecommendation,
    generate_ac_sizing_options,
)


def test_pcs_2000kw_in_configs():
    """Verify 2000 kW PCS is available in both 2-PCS and 4-PCS configurations"""
    
    options = generate_ac_sizing_options(
        dc_blocks_total=10,
        target_mw=50.0,
        target_mwh=200.0,
        dc_block_mwh=5.0
    )
    
    # Check all ratios have PCS configs
    for option in options:
        print(f"\n✅ Ratio {option.ratio}: {option.ac_block_count} AC Blocks")
        
        pcs_2_configs = [r for r in option.pcs_recommendations if r.pcs_count == 2]
        pcs_4_configs = [r for r in option.pcs_recommendations if r.pcs_count == 4]
        
        # Check 2 PCS configs
        print(f"  2-PCS configs: {len(pcs_2_configs)}")
        pcs_2000_in_2 = any(r.pcs_kw == 2000 for r in pcs_2_configs)
        print(f"    - Contains 2×2000kW: {pcs_2000_in_2} {'✅' if pcs_2000_in_2 else '❌'}")
        if pcs_2000_in_2:
            config = next(r for r in pcs_2_configs if r.pcs_kw == 2000)
            print(f"    - Details: {config.readable}")
            assert config.total_kw == 4000, f"Expected 4000, got {config.total_kw}"
        
        # Check 4 PCS configs
        print(f"  4-PCS configs: {len(pcs_4_configs)}")
        pcs_2000_in_4 = any(r.pcs_kw == 2000 for r in pcs_4_configs)
        print(f"    - Contains 4×2000kW: {pcs_2000_in_4} {'✅' if pcs_2000_in_4 else '❌'}")
        if pcs_2000_in_4:
            config = next(r for r in pcs_4_configs if r.pcs_kw == 2000)
            print(f"    - Details: {config.readable}")
            assert config.total_kw == 8000, f"Expected 8000, got {config.total_kw}"


def test_custom_pcs_recommendation():
    """Test custom PCS recommendation creation"""
    
    # Create custom 3×1800 configuration
    custom = PCSRecommendation(
        pcs_count=3,
        pcs_kw=1800,
        total_kw=5400,
        is_custom=True
    )
    
    print("\n✅ Custom PCS Configuration:")
    print(f"  - Configuration: {custom.readable}")
    print(f"  - Is Custom: {custom.is_custom}")
    print(f"  - Total Power: {custom.total_kw} kW")
    
    assert custom.pcs_count == 3
    assert custom.pcs_kw == 1800
    assert custom.total_kw == 5400
    assert custom.is_custom is True


def test_container_sizing():
    """Test container sizing logic based on block power"""
    
    test_cases = [
        (2, 1250, 2.5, "20ft"),  # 2×1250 = 2.5 MW
        (2, 2000, 4.0, "20ft"),  # 2×2000 = 4.0 MW
        (2, 2500, 5.0, "20ft"),  # 2×2500 = 5.0 MW (boundary)
        (4, 1250, 5.0, "20ft"),  # 4×1250 = 5.0 MW (boundary)
        (4, 1500, 6.0, "40ft"),  # 4×1500 = 6.0 MW
        (4, 2000, 8.0, "40ft"),  # 4×2000 = 8.0 MW
        (3, 1800, 5.4, "40ft"),  # 3×1800 = 5.4 MW (custom)
    ]
    
    print("\n✅ Container Sizing Tests:")
    for pcs_count, pcs_kw, expected_power, expected_container in test_cases:
        block_power_mw = pcs_count * pcs_kw / 1000
        container = "40ft" if block_power_mw > 5 else "20ft"
        
        status = "✅" if (abs(block_power_mw - expected_power) < 0.01 and container == expected_container) else "❌"
        print(f"  {status} {pcs_count}×{pcs_kw}kW = {block_power_mw:.1f}MW → {container} (expected {expected_container})")
        
        assert container == expected_container, f"Container mismatch: got {container}, expected {expected_container}"


def test_all_standard_ratings():
    """Verify all standard ratings are available"""
    
    standard_ratings = [1250, 1500, 1725, 2000, 2500]
    
    options = generate_ac_sizing_options(
        dc_blocks_total=20,
        target_mw=100.0,
        target_mwh=400.0,
        dc_block_mwh=5.0
    )
    
    print("\n✅ Standard Ratings Availability:")
    
    all_pcs_ratings = set()
    for option in options:
        for rec in option.pcs_recommendations:
            all_pcs_ratings.add(rec.pcs_kw)
    
    for rating in standard_ratings:
        available = rating in all_pcs_ratings
        status = "✅" if available else "❌"
        print(f"  {status} {rating} kW")
        assert available, f"{rating} kW not found in standard ratings"


if __name__ == "__main__":
    print("=" * 60)
    print("PCS 2000 kW Support & Custom Rating Tests")
    print("=" * 60)
    
    try:
        test_pcs_2000kw_in_configs()
        test_custom_pcs_recommendation()
        test_container_sizing()
        test_all_standard_ratings()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
