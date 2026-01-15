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
Quick test of AC Sizing logic without Streamlit
"""

def test_ac_sizing_logic():
    """Test AC sizing option generation"""
    from calb_sizing_tool.ui.ac_sizing_config import generate_ac_sizing_options
    
    # Test case 1: 10 DC Blocks, 100 MW power, 400 MWh energy
    print("Test Case 1: 10 DC Blocks, 100 MW, 400 MWh")
    options = generate_ac_sizing_options(
        dc_blocks_total=10,
        target_mw=100.0,
        target_mwh=400.0,
        dc_block_mwh=5.0
    )
    
    assert len(options) == 3, f"Expected 3 options, got {len(options)}"
    print(f"✅ Generated {len(options)} ratio options")
    
    for opt in options:
        print(f"\n  Ratio: {opt.ratio}")
        print(f"  - AC Blocks: {opt.ac_block_count}")
        print(f"  - DC Blocks per AC: {opt.dc_blocks_per_ac}")
        print(f"  - Recommended: {opt.is_recommended}")
        print(f"  - PCS Options:")
        for rec in opt.pcs_recommendations:
            print(f"    • {rec.readable}")
        
        # Verify each option is valid
        assert opt.ac_block_count > 0, f"AC block count must be > 0 for {opt.ratio}"
        assert len(opt.dc_blocks_per_ac) == opt.ac_block_count, \
            f"DC blocks distribution mismatch for {opt.ratio}"
        assert len(opt.pcs_recommendations) > 0, f"No PCS recommendations for {opt.ratio}"
    
    # Verify ratios
    assert options[0].ratio == "1:1", "Option A should be 1:1"
    assert options[1].ratio == "1:2", "Option B should be 1:2"
    assert options[2].ratio == "1:4", "Option C should be 1:4"
    
    # Verify recommended status (1:2 should be recommended for 10 blocks)
    assert options[1].is_recommended, "1:2 ratio should be recommended for 10 DC blocks"
    
    print("\n✅ All tests passed!")
    
    # Test case 2: Small system (4 DC Blocks)
    print("\n\nTest Case 2: 4 DC Blocks (small system)")
    options2 = generate_ac_sizing_options(
        dc_blocks_total=4,
        target_mw=10.0,
        target_mwh=40.0,
        dc_block_mwh=5.0
    )
    
    # For 4 blocks, 1:1 should be recommended
    assert options2[0].is_recommended, "1:1 ratio should be recommended for 4 DC blocks"
    print(f"✅ 1:1 ratio recommended for small system (4 blocks)")
    
    # Test case 3: Large system (12 DC Blocks)
    print("\n\nTest Case 3: 12 DC Blocks (large system)")
    options3 = generate_ac_sizing_options(
        dc_blocks_total=12,
        target_mw=120.0,
        target_mwh=600.0,
        dc_block_mwh=5.0
    )
    
    # For 12 blocks, 1:4 should be recommended
    assert options3[2].is_recommended, "1:4 ratio should be recommended for 12 DC blocks"
    print(f"✅ 1:4 ratio recommended for large system (12 blocks)")
    
    print("\n\n" + "="*60)
    print("All AC Sizing Logic Tests PASSED ✅")
    print("="*60)

if __name__ == "__main__":
    try:
        test_ac_sizing_logic()
    except AssertionError as e:
        print(f"\n❌ Test Failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
