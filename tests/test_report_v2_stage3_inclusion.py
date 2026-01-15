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

import sys
import types
import pandas as pd


def _inject_dummy_dc_view():
    # Provide a lightweight dummy for calb_sizing_tool.ui.dc_view so that
    # report_context can be imported without pulling heavy dependencies
    mod = types.SimpleNamespace()

    def load_data(path):
        # returns the expected tuple shape; the actual contents aren't used in
        # the first test
        return {}, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    def run_stage3(stage1, stage2, df_soh_profile, df_soh_curve, df_rte_profile, df_rte_curve):
        df = pd.DataFrame({"Year_Index": [0], "POI_Usable_Energy_MWh": [123.45]})
        meta = {"effective_c_rate": 1.0}
        return df, meta

    mod.load_data = load_data
    mod.run_stage3 = run_stage3
    sys.modules["calb_sizing_tool.ui.dc_view"] = mod


def test_build_report_context_uses_embedded_stage3_df():
    _inject_dummy_dc_view()

    from calb_sizing_tool.reporting.report_context import build_report_context

    stage1 = {
        "project_name": "p",
        "poi_power_req_mw": 100.0,
        "poi_energy_req_mwh": 400.0,
        "project_life_years": 20,
        "cycles_per_year": 365,
        "poi_guarantee_year": 0,
    }
    stage2 = {"dc_nameplate_bol_mwh": 500.0, "container_count": 10, "cabinet_count": 0}
    s3_df = pd.DataFrame({"Year_Index": [0, 1], "POI_Usable_Energy_MWh": [999.0, 888.0]})

    stage13_output = {**stage1, "stage2_raw": stage2, "stage3_meta": {"eff": 1.0}, "stage3_df": s3_df}

    ctx = build_report_context(
        session_state={"dc_results": {}},
        stage_outputs={"stage13_output": stage13_output, "ac_output": {}},
        project_inputs={"poi_energy_guarantee_mwh": 400.0},
        scenario_ids=stage13_output.get("selected_scenario"),
    )

    assert ctx.stage3_df is not None
    assert int(ctx.poi_usable_energy_mwh_at_year0) == 999


def test_build_report_context_recomputes_stage3_when_missing():
    _inject_dummy_dc_view()

    from calb_sizing_tool.reporting.report_context import build_report_context

    stage1 = {
        "project_name": "p",
        "poi_power_req_mw": 100.0,
        "poi_energy_req_mwh": 400.0,
        "project_life_years": 20,
        "cycles_per_year": 365,
        "poi_guarantee_year": 0,
    }
    stage2 = {"dc_nameplate_bol_mwh": 500.0, "container_count": 10, "cabinet_count": 0}

    stage13_output = {**stage1, "stage2_raw": stage2, "stage3_meta": {"eff": 1.0}}

    ctx = build_report_context(
        session_state={"dc_results": {}},
        stage_outputs={"stage13_output": stage13_output, "ac_output": {}},
        project_inputs={"poi_energy_guarantee_mwh": 400.0},
        scenario_ids=stage13_output.get("selected_scenario"),
    )

    # Dummy run_stage3 returns 123.45 for year0
    assert ctx.poi_usable_energy_mwh_at_year0 == 123.45
