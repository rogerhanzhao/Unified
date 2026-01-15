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

from tools.regress_export import build_summary_from_fixture_path


GOLDEN_DIR = Path(__file__).parent / "golden"


def _fixture_pairs():
    for case_dir in sorted(GOLDEN_DIR.iterdir()):
        if not case_dir.is_dir():
            continue
        fixture_path = case_dir / "input.json"
        summary_path = case_dir / "v1_summary.json"
        if fixture_path.exists() and summary_path.exists():
            yield fixture_path, summary_path


@pytest.mark.parametrize("fixture_path, summary_path", list(_fixture_pairs()))
def test_v1_summary_regression(fixture_path: Path, summary_path: Path):
    expected = json.loads(summary_path.read_text(encoding="utf-8"))
    actual = build_summary_from_fixture_path(fixture_path)
    assert actual == expected
