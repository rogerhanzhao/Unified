import json
from pathlib import Path

import pytest

pytest.importorskip("pypowsybl")

from calb_sizing_tool.sld.iidm_builder import build_network_for_single_unit
from calb_sizing_tool.sld.renderer import render_raw_svg
from calb_sizing_tool.sld.snapshot_single_unit import validate_single_unit_snapshot


def test_sld_raw_smoke(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "sld_single_unit_snapshot.json"
    snapshot = json.loads(fixture_path.read_text(encoding="utf-8"))

    validate_single_unit_snapshot(snapshot)
    network = build_network_for_single_unit(snapshot)

    svg_path = tmp_path / "raw.svg"
    metadata_path = tmp_path / "raw_metadata.json"
    render_raw_svg(network, "SUB_MV_NODE_01", svg_path, metadata_path)

    svg_text = svg_path.read_text(encoding="utf-8")
    assert svg_text.strip()
    assert "PCS-01" in svg_text
    assert "LV Bus" in svg_text
