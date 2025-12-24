from typing import Optional

from calb_sizing_tool.sld.snapshot_schema import validate_snapshot_v1

try:
    import pypowsybl as pp
except Exception:  # pragma: no cover - import guarded in caller
    pp = None


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def build_iidm_network_from_snapshot(snapshot: dict) -> "pp.network.Network":
    if pp is None:
        raise ImportError("pypowsybl is required to build the IIDM network.")

    validate_snapshot_v1(snapshot)

    ac_system = snapshot["ac_system"]
    feeders = snapshot["feeders"]

    substation_id = "SUB_BESS_01"
    vl_mv_id = "VL_MV_01"
    vl_lv_id = "VL_LV_01"
    bus_mv_id = "BBS_MV_01"
    bus_lv_id = "BBS_LV_01"

    grid_mv_kv = _safe_float(ac_system.get("grid_mv_voltage_kv_ac"), 33.0)
    pcs_lv_kv = _safe_float(ac_system.get("pcs_lv_voltage_v_ll_rms_ac"), 800.0) / 1000.0
    transformer_rating_kva = _safe_float(ac_system.get("transformer_rating_kva"), 5000.0)
    transformer_rating_mva = transformer_rating_kva / 1000.0 if transformer_rating_kva else 5.0

    net = pp.network.create_empty()
    net.create_substations(id=substation_id)

    net.create_voltage_levels(
        id=vl_mv_id,
        substation_id=substation_id,
        topology_kind="BUS_BREAKER",
        nominal_v=grid_mv_kv,
        low_voltage_limit=grid_mv_kv * 0.9,
        high_voltage_limit=grid_mv_kv * 1.1,
    )
    net.create_voltage_levels(
        id=vl_lv_id,
        substation_id=substation_id,
        topology_kind="BUS_BREAKER",
        nominal_v=pcs_lv_kv,
        low_voltage_limit=pcs_lv_kv * 0.9,
        high_voltage_limit=pcs_lv_kv * 1.1,
    )

    net.create_buses(id=bus_mv_id, voltage_level_id=vl_mv_id)
    net.create_buses(id=bus_lv_id, voltage_level_id=vl_lv_id)

    net.create_2_windings_transformers(
        id="TR_01",
        voltage_level1_id=vl_mv_id,
        bus1_id=bus_mv_id,
        voltage_level2_id=vl_lv_id,
        bus2_id=bus_lv_id,
        rated_u1=grid_mv_kv,
        rated_u2=pcs_lv_kv,
        rated_s=transformer_rating_mva,
        r=0.01,
        x=0.1,
    )

    for idx, feeder in enumerate(feeders, start=1):
        feeder_bus_id = f"FDR_BUS_{idx:02d}"
        switch_id = f"BRK_FDR_{idx:02d}"
        pcs_id = feeder.get("pcs_id") or f"PCS-{idx:02d}"
        pcs_rating_kw = _safe_float(feeder.get("pcs_rating_kw"), 0.0)
        pcs_rating_mw = pcs_rating_kw / 1000.0 if pcs_rating_kw else 0.1

        net.create_buses(id=feeder_bus_id, voltage_level_id=vl_lv_id)
        net.create_switches(
            id=switch_id,
            voltage_level_id=vl_lv_id,
            bus1_id=bus_lv_id,
            bus2_id=feeder_bus_id,
            kind="BREAKER",
            open=False,
        )
        net.create_generators(
            id=pcs_id,
            voltage_level_id=vl_lv_id,
            bus_id=feeder_bus_id,
            min_p=0.0,
            max_p=pcs_rating_mw,
            target_p=0.0,
            target_q=0.0,
            rated_s=pcs_rating_mw,
            target_v=pcs_lv_kv,
            voltage_regulator_on=False,
        )

    return net
