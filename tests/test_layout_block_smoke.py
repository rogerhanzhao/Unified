from pathlib import Path

import pytest

pytest.importorskip("svgwrite")

from calb_diagrams.layout_block_renderer import render_layout_block_svg
from calb_diagrams.specs import build_layout_block_spec


def test_layout_block_smoke(tmp_path: Path):
    labels = {
        "block_title": "Block {index}",
        "bess_range_text": "BESS {start}~{end}",
        "skid_text": "PCS&MVT SKID",
        "skid_subtext": "33.0 kV / 690 V, 5.0 MVA",
    }
    spec = build_layout_block_spec(
        ac_output={},
        block_indices_to_render=[1, 2],
        labels=labels,
        arrangement="2x2",
        show_skid=True,
    )
    svg_path = tmp_path / "layout_block.svg"
    result_path, warning = render_layout_block_svg(spec, svg_path)
    assert result_path is not None
    assert warning is None or isinstance(warning, str)

    svg_text = svg_path.read_text(encoding="utf-8")
    assert svg_text.strip()
    assert "Block 1" in svg_text
    assert "PCS&amp;MVT SKID" in svg_text
