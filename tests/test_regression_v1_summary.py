import json
from pathlib import Path

import pytest

from tools.regress_export import build_summary_from_fixture_path


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _fixture_pairs():
    for fixture_path in sorted(FIXTURE_DIR.glob("*_input.json")):
        summary_path = fixture_path.with_name(fixture_path.name.replace("_input.json", "_summary.json"))
        yield fixture_path, summary_path


@pytest.mark.parametrize("fixture_path, summary_path", list(_fixture_pairs()))
def test_v1_summary_regression(fixture_path: Path, summary_path: Path):
    expected = json.loads(summary_path.read_text(encoding="utf-8"))
    actual = build_summary_from_fixture_path(fixture_path)
    assert actual == expected
