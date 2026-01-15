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

import json
from pathlib import Path

import pytest

pytest.importorskip("pypowsybl")

from calb_sizing_tool.sld.iidm_builder import build_iidm_network_from_snapshot
from calb_sizing_tool.sld.renderer import render_sld_svg
from calb_sizing_tool.sld.snapshot_schema import validate_snapshot_v1


def test_sld_smoke(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "sld_snapshot_v1_example_single_mv_node.json"
    snapshot = json.loads(fixture_path.read_text(encoding="utf-8"))

    validate_snapshot_v1(snapshot)
    network = build_iidm_network_from_snapshot(snapshot)

    svg_path = tmp_path / "sld.svg"
    metadata_path = tmp_path / "sld_metadata.json"
    render_sld_svg(network, "SUB_MV_NODE_01", svg_path, metadata_path)

    svg_text = svg_path.read_text(encoding="utf-8")
    assert svg_text.strip()
    assert "TR_01" in svg_text
    assert "PCS-01" in svg_text
