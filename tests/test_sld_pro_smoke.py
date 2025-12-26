import json
from pathlib import Path

from calb_sizing_tool.sld.jp_pro_renderer import render_jp_pro_svg
from calb_sizing_tool.sld.snapshot_single_unit import validate_single_unit_snapshot


def test_sld_pro_smoke(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "sld_single_unit_snapshot.json"
    snapshot = json.loads(fixture_path.read_text(encoding="utf-8"))

    validate_single_unit_snapshot(snapshot)
    pro_svg_path = tmp_path / "sld_pro_en.svg"
    render_jp_pro_svg(snapshot, pro_svg_path)
    svg_text = pro_svg_path.read_text(encoding="utf-8")
    assert svg_text.strip()
    assert "PCS&amp;MVT SKID (AC Block)" in svg_text
    assert "Transformer" in svg_text
    assert "DC Block Group" in svg_text
    assert "DC Block Allocation" in svg_text
    assert "5.106 MWh" in svg_text
