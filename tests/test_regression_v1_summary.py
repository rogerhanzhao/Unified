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
