import io
import json
from pathlib import Path

from docx import Document

from calb_sizing_tool.reporting.report_context import build_report_context
from calb_sizing_tool.reporting.report_v2 import export_report_v2
from tools.regress_export import run_ac_sizing, run_dc_sizing


def test_report_v2_smoke():
    fixture_path = Path(__file__).parent / "fixtures" / "v1_case01_container_input.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    dc_results = run_dc_sizing(fixture)
    ac_output = run_ac_sizing(fixture, dc_results["stage1"], dc_results["stage2"])

    ctx = build_report_context(
        session_state={},
        stage_outputs={
            "stage13_output": dc_results["stage1"],
            "stage2": dc_results["stage2"],
            "stage3_df": dc_results["stage3_df"],
            "stage3_meta": dc_results["stage3_meta"],
            "ac_output": ac_output,
        },
        project_inputs={"poi_energy_guarantee_mwh": fixture["poi_energy_req_mwh"]},
        scenario_ids=fixture["scenario_id"],
    )

    report_bytes = export_report_v2(ctx)
    doc = Document(io.BytesIO(report_bytes))
    texts = [p.text for p in doc.paragraphs]
    joined = "\n".join(texts)

    assert texts.count("Executive Summary") == 1
    assert "Inputs & Assumptions" in texts
    assert "314 Ah cell database" not in joined
