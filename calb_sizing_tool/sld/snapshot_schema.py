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


def _require_any(container: Dict, keys: tuple[str, ...], context: str) -> None:
    for key in keys:
        if key in container and container.get(key) is not None:
            return
    raise ValueError(f"Missing one of {keys} in {context}.")


def validate_snapshot_chain_v2(snapshot: dict) -> None:
    if not isinstance(snapshot, dict):
        raise ValueError("Snapshot must be a dict.")

    if snapshot.get("schema_version") != "sld_chain_v2":
        raise ValueError("Unsupported snapshot schema_version.")

    project = snapshot.get("project")
    if not isinstance(project, dict):
        raise ValueError("Snapshot 'project' must be a dict.")
    for key in ("name", "hz"):
        _require(project, key, "project")

    mv = snapshot.get("mv")
    if not isinstance(mv, dict):
        raise ValueError("Snapshot 'mv' must be a dict.")
    for key in ("kv", "node_id", "labels"):
        _require(mv, key, "mv")
    labels = mv.get("labels")
    if not isinstance(labels, dict):
        raise ValueError("Snapshot 'mv.labels' must be a dict.")
    for key in ("to_switchgear", "to_other_rmu"):
        _require(labels, key, "mv.labels")

    rmu = snapshot.get("rmu")
    if not isinstance(rmu, dict):
        raise ValueError("Snapshot 'rmu' must be a dict.")

    transformer = snapshot.get("transformer")
    if not isinstance(transformer, dict):
        raise ValueError("Snapshot 'transformer' must be a dict.")
    for key in ("hv_kv", "lv_v", "vector_group", "impedance_percent", "tap_range", "cooling"):
        _require(transformer, key, "transformer")
    _require_any(transformer, ("rated_kva", "rated_mva"), "transformer")

    ac_block = snapshot.get("ac_block")
    if not isinstance(ac_block, dict):
        raise ValueError("Snapshot 'ac_block' must be a dict.")
    for key in ("template_id", "feeders_per_block", "pcs_rating_each"):
        _require(ac_block, key, "ac_block")

    feeders = snapshot.get("feeders")
    if not isinstance(feeders, list) or not feeders:
        raise ValueError("Snapshot 'feeders' must be a non-empty list.")
    if len(feeders) != 4:
        raise ValueError("Snapshot 'feeders' must contain 4 feeders for a single chain.")
    for feeder in feeders:
        if not isinstance(feeder, dict):
            raise ValueError("Each feeder entry must be a dict.")
        _require(feeder, "feeder_id", "feeders[]")
        _require(feeder, "pcs_id", "feeders[]")
        _require(feeder, "pcs_rating", "feeders[]")

    dc_blocks_by_feeder = snapshot.get("dc_blocks_by_feeder")
    if not isinstance(dc_blocks_by_feeder, list) or not dc_blocks_by_feeder:
        raise ValueError("Snapshot 'dc_blocks_by_feeder' must be a non-empty list.")
    if len(dc_blocks_by_feeder) != 4:
        raise ValueError("Snapshot 'dc_blocks_by_feeder' must contain 4 entries.")
    for entry in dc_blocks_by_feeder:
        if not isinstance(entry, dict):
            raise ValueError("Each dc_blocks_by_feeder entry must be a dict.")
        _require(entry, "feeder_id", "dc_blocks_by_feeder[]")
        _require(entry, "dc_block_count", "dc_blocks_by_feeder[]")
        _require(entry, "dc_block_energy_mwh", "dc_blocks_by_feeder[]")

    feeder_ids = {f["feeder_id"] for f in feeders}
    dc_feeder_ids = {d["feeder_id"] for d in dc_blocks_by_feeder}
    if feeder_ids != dc_feeder_ids:
        raise ValueError("Feeder IDs in feeders and dc_blocks_by_feeder must match.")

    equipment_list = snapshot.get("equipment_list")
    if equipment_list is not None and not isinstance(equipment_list, list):
        raise ValueError("Snapshot 'equipment_list' must be a list when provided.")
