from typing import Dict


def _require(container: Dict, key: str, context: str):
    if key not in container:
        raise ValueError(f"Missing '{key}' in {context}.")


def validate_snapshot_v1(snapshot: dict) -> None:
    if not isinstance(snapshot, dict):
        raise ValueError("Snapshot must be a dict.")

    if snapshot.get("schema_version") != "sld_snapshot_v1":
        raise ValueError("Unsupported snapshot schema_version.")

    project = snapshot.get("project")
    if not isinstance(project, dict):
        raise ValueError("Snapshot 'project' must be a dict.")
    for key in (
        "project_name",
        "scenario_id",
        "poi_power_requirement_mw",
        "poi_energy_requirement_mwh",
        "poi_energy_guarantee_mwh",
    ):
        _require(project, key, "project")

    ac_system = snapshot.get("ac_system")
    if not isinstance(ac_system, dict):
        raise ValueError("Snapshot 'ac_system' must be a dict.")
    for key in (
        "ac_block_template_id",
        "ac_blocks_total",
        "pcs_per_block",
        "feeders_per_block",
        "grid_mv_voltage_kv_ac",
        "pcs_lv_voltage_v_ll_rms_ac",
    ):
        _require(ac_system, key, "ac_system")

    feeders = snapshot.get("feeders")
    if not isinstance(feeders, list) or not feeders:
        raise ValueError("Snapshot 'feeders' must be a non-empty list.")
    for feeder in feeders:
        if not isinstance(feeder, dict):
            raise ValueError("Each feeder entry must be a dict.")
        _require(feeder, "feeder_id", "feeders[]")
        _require(feeder, "pcs_id", "feeders[]")

    dc_blocks_by_feeder = snapshot.get("dc_blocks_by_feeder")
    if not isinstance(dc_blocks_by_feeder, list) or not dc_blocks_by_feeder:
        raise ValueError("Snapshot 'dc_blocks_by_feeder' must be a non-empty list.")
    for entry in dc_blocks_by_feeder:
        if not isinstance(entry, dict):
            raise ValueError("Each dc_blocks_by_feeder entry must be a dict.")
        _require(entry, "feeder_id", "dc_blocks_by_feeder[]")
        _require(entry, "dc_blocks", "dc_blocks_by_feeder[]")

    feeder_ids = {f["feeder_id"] for f in feeders}
    dc_feeder_ids = {d["feeder_id"] for d in dc_blocks_by_feeder}
    if feeder_ids != dc_feeder_ids:
        raise ValueError("Feeder IDs in feeders and dc_blocks_by_feeder must match.")
