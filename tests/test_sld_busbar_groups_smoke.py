from pathlib import Path

import pytest

pytest.importorskip("svgwrite")

from calb_diagrams.specs import build_sld_group_spec
from calb_diagrams.sld_pro_renderer import render_sld_pro_svg


def test_sld_busbar_groups_smoke(tmp_path: Path):
    stage13_output = {
        "project_name": "Busbar Group Test",
        "poi_nominal_voltage_kv": 33.0,
        "dc_block_total_qty": 6,
    }
    ac_output = {
        "num_blocks": 1,
        "grid_kv": 33.0,
        "inverter_lv_v": 690.0,
        "block_size_mw": 5.0,
        "pcs_power_kw": 2500.0,
        "pcs_count_by_block": [4],
        "dc_blocks_total_by_block": [6],
    }
    sld_inputs = {
        "mv_nominal_kv_ac": 33.0,
        "pcs_lv_voltage_v_ll": 690.0,
        "transformer_rating_mva": 5.0,
        "pcs_rating_each_kw": 1250.0,
        "dc_block_energy_mwh": 5.106,
        "dc_blocks_per_feeder": [2, 1, 2, 1],
        "rmu": {"rated_kv": 36.0, "rated_a": 630, "short_circuit_ka_3s": 25.0},
        "transformer": {"vector_group": "Dyn11", "uk_percent": 7.0, "cooling": "ONAN"},
        "lv_busbar": {"rated_a": 2500.0, "short_circuit_ka": 25.0},
        "cables": {"mv_cable_spec": "TBD", "lv_cable_spec": "TBD", "dc_cable_spec": "TBD"},
        "dc_fuse": {"fuse_spec": "TBD"},
    }

    spec = build_sld_group_spec(stage13_output, ac_output, {}, sld_inputs, group_index=1)
    svg_path = tmp_path / "sld_busbars.svg"
    result_path, warning = render_sld_pro_svg(spec, svg_path)
    assert result_path is not None
    assert warning is None or isinstance(warning, str)

    svg_text = svg_path.read_text(encoding="utf-8")
    assert "DC BUSBAR A" in svg_text
    assert "DC BUSBAR B" in svg_text
    assert "DC Combiner" not in svg_text
