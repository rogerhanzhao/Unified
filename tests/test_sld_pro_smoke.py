import json
from pathlib import Path

import pytest

pytest.importorskip("pypowsybl")

from calb_sizing_tool.sld.iidm_builder import build_iidm_network_from_chain_snapshot
from calb_sizing_tool.sld.renderer import render_pow_sybl_svg
from calb_sizing_tool.sld.snapshot_schema import validate_snapshot_chain_v2
from calb_sizing_tool.sld.svg_pro_template import apply_pro_template


def test_sld_pro_smoke(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "sld_chain_v2_example.json"
    snapshot = json.loads(fixture_path.read_text(encoding="utf-8"))

    validate_snapshot_chain_v2(snapshot)
    network = build_iidm_network_from_chain_snapshot(snapshot)

    svg_path = tmp_path / "sld_raw.svg"
    metadata_path = tmp_path / "sld_metadata.json"
    pro_svg_path = tmp_path / "sld_pro.svg"

    render_pow_sybl_svg(network, "SUB_MV_NODE_01", svg_path, metadata_path)
    apply_pro_template(svg_path, metadata_path, snapshot, pro_svg_path)

    svg_text = pro_svg_path.read_text(encoding="utf-8")
    assert svg_text.strip()
    assert "PCS Container" in svg_text
    assert "To 20kV Switchgear" in svg_text
    assert "DC Block ×" in svg_text
