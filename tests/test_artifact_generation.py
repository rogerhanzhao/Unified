from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from artifact_generation import generate_stage4_report, render_block_sld, render_layout_plot


@pytest.fixture
def sample_stage13() -> dict:
    return {
        "project_name": "Sample CALB ESS Project",
        "selected_scenario": "container_only",
        "poi_power_req_mw": 50.0,
        "poi_energy_req_mwh": 200.0,
        "poi_nominal_voltage_kv": 22.0,
        "dc_block_total_qty": 24,
        "container_count": 24,
        "cabinet_count": 0,
        "busbars_needed": 12,
        "dc_nameplate_bol_mwh": 210.0,
        "oversize_mwh": 10.0,
        "eff_dc_to_poi_frac": 0.97,
    }


@pytest.mark.sld
def test_render_block_sld_creates_files(tmp_path: Path, sample_stage13: dict):
    pytest.importorskip("matplotlib")
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "outputs"
    temp_path, output_path = render_block_sld(sample_stage13, temp_dir=temp_dir, output_dir=output_dir)

    assert temp_path.exists(), "Temp SLD should be created"
    assert output_path.exists(), "Output SLD should be created"
    assert temp_path.stat().st_size > 0
    assert output_path.stat().st_size > 0


@pytest.mark.layout
def test_render_layout_plot_creates_files(tmp_path: Path, sample_stage13: dict):
    pytest.importorskip("matplotlib")
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "outputs"
    temp_path, output_path = render_layout_plot(sample_stage13, temp_dir=temp_dir, output_dir=output_dir)

    assert temp_path.exists(), "Temp layout should be created"
    assert output_path.exists(), "Output layout should be created"
    assert temp_path.stat().st_size > 0
    assert output_path.stat().st_size > 0


@pytest.mark.report
def test_generate_stage4_report_writes_docx(tmp_path: Path, sample_stage13: dict):
    pytest.importorskip("matplotlib")
    pytest.importorskip("docx")
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "outputs"
    _, sld_output = render_block_sld(sample_stage13, temp_dir=temp_dir, output_dir=output_dir)
    _, layout_output = render_layout_plot(sample_stage13, temp_dir=temp_dir, output_dir=output_dir)

    docx_path = generate_stage4_report(
        sample_stage13,
        sld_path=sld_output,
        layout_path=layout_output,
        output_dir=output_dir,
        filename="SampleReport.docx",
    )

    assert docx_path.exists(), "DOCX should be written to outputs directory"
    assert docx_path.suffix == ".docx"
    assert docx_path.stat().st_size > 0
