import time

from stage4_interface import pack_stage13_output


def test_pack_stage13_output_coerces_types(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1_700_000_000)

    stage1 = {
        "project_name": "Unit Test Project",
        "poi_power_req_mw": "5.5",
        "poi_energy_req_mwh": "10.2",
        "eff_dc_to_poi_frac": "0.9",
        "dc_power_required_mw": "6.1",
    }
    stage2 = {
        "container_count": "2",
        "cabinet_count": None,
        "busbars_needed": 1,
        "dc_nameplate_bol_mwh": "15.0",
        "block_config_table_records": [{"Block Name": "Example"}],
        "oversize_mwh": 0.5,
    }
    stage3 = {
        "effective_c_rate": "0.2",
        "soh_profile_id": "3",
        "rte_profile_id": "5",
    }

    packed = pack_stage13_output(
        stage1=stage1,
        stage2=stage2,
        stage3=stage3,
        dc_block_total_qty=3,
        selected_scenario="container_only",
        poi_nominal_voltage_kv="22",
    )

    assert packed["packed_at_epoch"] == 1_700_000_000
    assert packed["project_name"] == "Unit Test Project"
    assert packed["container_count"] == 2
    assert packed["cabinet_count"] == 0
    assert packed["busbars_needed"] == 1
    assert packed["dc_nameplate_bol_mwh"] == 15.0
    assert packed["dc_block_total_qty"] == 3
    assert packed["selected_scenario"] == "container_only"
    assert packed["poi_nominal_voltage_kv"] == 22.0
    assert packed["effective_c_rate"] == 0.2
    assert packed["soh_profile_id"] == 3
    assert packed["rte_profile_id"] == 5
    assert packed["block_config_table_records"] == [{"Block Name": "Example"}]
    assert packed["oversize_mwh"] == 0.5


def test_pack_stage13_output_defaults_when_missing(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1_700_000_123)

    packed = pack_stage13_output(
        stage1={},
        stage2={},
        stage3={},
        dc_block_total_qty=0,
        selected_scenario="hybrid",
        poi_nominal_voltage_kv=35,
    )

    assert packed["packed_at_epoch"] == 1_700_000_123
    assert packed["project_name"] == "CALB ESS Project"
    assert packed["poi_power_req_mw"] == 0.0
    assert packed["container_count"] == 0
    assert packed["cabinet_count"] == 0
    assert packed["busbars_needed"] == 0
    assert packed["dc_nameplate_bol_mwh"] == 0.0
    assert packed["selected_scenario"] == "hybrid"
    assert packed["poi_nominal_voltage_kv"] == 35.0
    assert packed["effective_c_rate"] == 0.0
    assert packed["soh_profile_id"] == 0
    assert packed["rte_profile_id"] == 0
