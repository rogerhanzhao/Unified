import pytest
from calb_sizing_tool.models import ProjectSizingResult, ACBlockResult
from calb_sizing_tool.sld.visualizer import generate_sld

def test_sld_generation():
    res = ProjectSizingResult(
        system_power_mw=10, ac_blocks=[ACBlockResult()]
    )
    dot = generate_sld(res)
    assert "POI" in dot.source
    assert "Trafo" in dot.source