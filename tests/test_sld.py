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