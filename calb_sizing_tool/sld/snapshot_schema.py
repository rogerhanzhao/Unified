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
    for key in ("project_name", "scenario_id", "poi_frequency_hz"):
        _require(project, key, "project")

    mv_node = snapshot.get("mv_node")
    if not isinstance(mv_node, dict):
        raise ValueError("Snapshot 'mv_node' must be a dict.")
    for key in ("node_id", "mv_kv_ac"):
        _require(mv_node, key, "mv_node")

    rmu = snapshot.get("rmu")
    if not isinstance(rmu, dict):
        raise ValueError("Snapshot 'rmu' must be a dict.")
    _require(rmu, "device_type", "rmu")

    transformer = snapshot.get("transformer")
    if not isinstance(transformer, dict):
        raise ValueError("Snapshot 'transformer' must be a dict.")
    for key in ("id", "hv_kv", "lv_kv"):
        _require(transformer, key, "transformer")
    if transformer.get("rated_kva") is None and transformer.get("rated_mva") is None:
        raise ValueError("Transformer rated_kva or rated_mva must be provided.")

    ac_block = snapshot.get("ac_block")
    if not isinstance(ac_block, dict):
        raise ValueError("Snapshot 'ac_block' must be a dict.")
    for key in ("template_id", "feeders_per_block", "pcs_per_block"):
        _require(ac_block, key, "ac_block")

    feeders = snapshot.get("feeders")
    if not isinstance(feeders, list) or not feeders:
        raise ValueError("Snapshot 'feeders' must be a non-empty list.")
    for feeder in feeders:
        if not isinstance(feeder, dict):
            raise ValueError("Each feeder entry must be a dict.")
        _require(feeder, "feeder_id", "feeders[]")
        _require(feeder, "pcs_id", "feeders[]")
        _require(feeder, "pcs_kw", "feeders[]")

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
