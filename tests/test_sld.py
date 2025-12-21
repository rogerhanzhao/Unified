import pytest
from calb_sizing_tool.models import ProjectSizingResult, ACBlockData
from calb_sizing_tool.sld.topology import ElectricalTopology

def test_topology_nodes():
    data = ProjectSizingResult(
        total_power_mw=10,
        total_capacity_mwh=40,
        ac_blocks=[
            ACBlockData(
                block_id="B1", 
                mv_voltage_kv=33, 
                lv_voltage_v=800, 
                power_mw=5, 
                num_pcs=2, 
                pcs_power_kw=2500
            )
        ]
    )
    
    topo = ElectricalTopology(data)
    g = topo.get_graph()
    
    assert "POI" in g.nodes
    assert "Trafo_1" in g.nodes
    assert "T1_PCS_1" in g.nodes
    # Check Edge
    assert g.has_edge("POI", "Trafo_1")