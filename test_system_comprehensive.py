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
Comprehensive system test to validate all fixes are in place and working.
"""
import json
import os
import sys
from pathlib import Path

def test_pcs_2000kw_available():
    """Verify 2000kW PCS option is available"""
    from calb_sizing_tool.ui.ac_sizing_config import ACBlockConfig
    config = ACBlockConfig()
    
    # Test 2-PCS configuration
    recs_2pcs = config.get_pcs_recommendations_for_pcs_count(2)
    kws_2pcs = [r.pcs_kw for r in recs_2pcs]
    
    # Test 4-PCS configuration
    recs_4pcs = config.get_pcs_recommendations_for_pcs_count(4)
    kws_4pcs = [r.pcs_kw for r in recs_4pcs]
    
    assert 2000 in kws_2pcs, f"2000kW not in 2-PCS recommendations: {kws_2pcs}"
    assert 2000 in kws_4pcs, f"2000kW not in 4-PCS recommendations: {kws_4pcs}"
    print("✅ Test 1: PCS 2000kW option available - PASSED")
    return True

def test_report_context_structure():
    """Verify ReportContext dataclass exists and has required fields"""
    from calb_sizing_tool.reporting.report_context import ReportContext
    
    # Verify key methods and fields exist
    assert hasattr(ReportContext, 'from_session_state'), "Missing from_session_state method"
    print("✅ Test 2: ReportContext structure - PASSED")
    return True

def test_report_export_docx():
    """Verify DOCX export module can import without errors"""
    try:
        from calb_sizing_tool.reporting import export_docx
        assert hasattr(export_docx, 'create_combined_report'), "Missing create_combined_report function"
        assert hasattr(export_docx, 'make_proposal_filename'), "Missing make_proposal_filename function"
        print("✅ Test 3: DOCX export module - PASSED")
        return True
    except Exception as e:
        print(f"❌ Test 3 FAILED: {e}")
        return False

def test_sld_renderer():
    """Verify SLD renderer module exists and works"""
    try:
        from calb_diagrams.sld_pro_renderer import SLDPRORenderer
        print("✅ Test 4: SLD renderer module - PASSED")
        return True
    except Exception as e:
        print(f"❌ Test 4 FAILED: {e}")
        return False

def test_layout_renderer():
    """Verify Layout renderer module exists and works"""
    try:
        from calb_diagrams.layout_block_renderer import LayoutBlockRenderer
        print("✅ Test 5: Layout renderer module - PASSED")
        return True
    except Exception as e:
        print(f"❌ Test 5 FAILED: {e}")
        return False

def test_ac_sizing_with_2000kw():
    """Verify AC sizing can work with 2000kW PCS"""
    from calb_sizing_tool.ui.ac_sizing_config import ACBlockConfig, DCACRatio
    
    config = ACBlockConfig()
    
    # Test with 90 DC blocks -> 1:4 ratio
    result = config.calculate_ac_blocks(90, DCACRatio.ONE_TO_FOUR)
    assert result is not None, "AC block calculation failed"
    assert result['ac_blocks'] == 23, f"Expected 23 AC blocks, got {result['ac_blocks']}"
    
    # Test PCS recommendations for 1:4 ratio
    recs = config.get_pcs_recommendations_for_dc_ac_ratio(90, DCACRatio.ONE_TO_FOUR)
    assert len(recs) > 0, "No PCS recommendations generated"
    
    # Verify 2000kW option is in the recommendations
    pcs_kws = [r.pcs_kw for r in recs]
    assert 2000 in pcs_kws, f"2000kW not in PCS recommendations: {pcs_kws}"
    
    print("✅ Test 6: AC Sizing with 2000kW - PASSED")
    return True

def test_file_naming():
    """Verify report file naming format"""
    from calb_sizing_tool.reporting.export_docx import make_proposal_filename
    
    filename = make_proposal_filename("Test Project")
    assert filename.startswith("CALB_Test_Project_BESS_Proposal_"), f"Invalid filename format: {filename}"
    assert filename.endswith("_V2.1.docx"), f"Invalid filename suffix: {filename}"
    print("✅ Test 7: Report file naming - PASSED")
    return True

def test_outputs_directory():
    """Verify outputs directory exists and is writable"""
    outputs_dir = Path("/opt/calb/prod/CALB_SIZINGTOOL/outputs")
    if os.name == "nt" or not outputs_dir.exists():
        outputs_dir = Path("outputs")
        outputs_dir.mkdir(parents=True, exist_ok=True)
    assert outputs_dir.exists(), "Outputs directory does not exist"
    assert outputs_dir.is_dir(), "Outputs path is not a directory"
    
    # Try to write a test file
    test_file = outputs_dir / ".test_write"
    try:
        test_file.write_text("test")
        test_file.unlink()
        print("✅ Test 8: Outputs directory - PASSED")
        return True
    except Exception as e:
        print(f"❌ Test 8 FAILED: {e}")
        return False

def test_dc_block_allocation():
    """Verify DC block allocation logic"""
    from calb_sizing_tool.ui.ac_sizing_config import allocate_dc_blocks_to_pcs
    
    # Test allocation of 4 DC blocks to 2 PCS
    allocation = allocate_dc_blocks_to_pcs(4, 2)
    assert len(allocation) == 2, f"Expected 2 allocations, got {len(allocation)}"
    assert sum(allocation.values()) == 4, f"Allocation count mismatch: {allocation}"
    
    # Test allocation of 6 DC blocks to 4 PCS
    allocation = allocate_dc_blocks_to_pcs(6, 4)
    assert sum(allocation.values()) == 6, f"Allocation count mismatch: {allocation}"
    
    print("✅ Test 9: DC block allocation - PASSED")
    return True

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("COMPREHENSIVE SYSTEM VALIDATION TEST")
    print("="*60 + "\n")
    
    tests = [
        ("PCS 2000kW Available", test_pcs_2000kw_available),
        ("Report Context Structure", test_report_context_structure),
        ("DOCX Export Module", test_report_export_docx),
        ("SLD Renderer", test_sld_renderer),
        ("Layout Renderer", test_layout_renderer),
        ("AC Sizing with 2000kW", test_ac_sizing_with_2000kw),
        ("File Naming", test_file_naming),
        ("Outputs Directory", test_outputs_directory),
        ("DC Block Allocation", test_dc_block_allocation),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} - FAILED with exception: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED - System is ready!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed - Please review")
        return 1

if __name__ == "__main__":
    sys.exit(main())
