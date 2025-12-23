import pytest
import pandas as pd
from calb_sizing_tool.models import ProjectSizingResult, ACBlockResult, DCBlockResult
from calb_sizing_tool.reporting.export_docx import create_combined_report

def test_generate_report():
    # 1. Setup Mock Data
    dc = DCBlockResult(
        block_id="DC1",
        container_model="CALB-314Ah-20ft",
        capacity_mwh=5.015,
        voltage_v=1250,
        count=20
    )
    
    ac = ACBlockResult(
        block_id="AC1",
        transformer_kva=5000,
        mv_voltage_kv=33,
        lv_voltage_v=800,
        pcs_power_kw=1250,
        num_pcs=4,
        dc_blocks_connected=[dc]
    )
    
    res = ProjectSizingResult(
        project_name="Test Project Alpha",
        system_power_mw=100.0,
        system_capacity_mwh=400.0,
        ac_blocks=[ac] * 20 # 20 AC blocks
    )
    
    # Mock degradation table
    deg_data = pd.DataFrame({
        "Year": range(21),
        "SOH_Display_Pct": [100 - i*2 for i in range(21)],
        "POI_Usable_Energy_MWh": [400 - i*5 for i in range(21)]
    })
    
    context = {"degradation_table": deg_data, "inputs": {"Test Input": 123}}
    
    # 2. Run Generation
    report_bytes = create_combined_report(res, "combined", context)
    
    # 3. Assert
    assert report_bytes is not None
    assert len(report_bytes.getvalue()) > 0
    print("Report generated successfully (size: {} bytes)".format(len(report_bytes.getvalue())))

if __name__ == "__main__":
    test_generate_report()