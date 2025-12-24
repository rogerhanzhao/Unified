from calb_sizing_tool.sld.snapshot_schema import validate_snapshot_v1


def run_sld_qc(snapshot: dict) -> list[str]:
    warnings = []
    try:
        validate_snapshot_v1(snapshot)
    except ValueError as exc:
        warnings.append(str(exc))
        return warnings

    ac_system = snapshot["ac_system"]
    feeders = snapshot["feeders"]
    dc_blocks_by_feeder = snapshot["dc_blocks_by_feeder"]

    ac_blocks_total = int(ac_system.get("ac_blocks_total", 0))
    feeders_per_block = int(ac_system.get("feeders_per_block", 0))
    pcs_per_block = int(ac_system.get("pcs_per_block", 0))
    expected_feeders = ac_blocks_total * feeders_per_block if ac_blocks_total and feeders_per_block else 0

    if expected_feeders and len(feeders) != expected_feeders:
        warnings.append(
            f"Feeder count mismatch: expected {expected_feeders}, got {len(feeders)}."
        )

    expected_pcs = ac_blocks_total * pcs_per_block if ac_blocks_total and pcs_per_block else 0
    pcs_ids = {f.get("pcs_id") for f in feeders if f.get("pcs_id")}
    if expected_pcs and len(pcs_ids) != expected_pcs:
        warnings.append(f"PCS count mismatch: expected {expected_pcs}, got {len(pcs_ids)}.")

    if len(dc_blocks_by_feeder) != len(feeders):
        warnings.append(
            "dc_blocks_by_feeder entries do not match feeders count."
        )

    dc_total = snapshot.get("dc_system", {}).get("dc_blocks_total")
    if dc_total is not None:
        try:
            dc_total = int(dc_total)
        except Exception:
            dc_total = None
    if dc_total is not None:
        dc_alloc = sum(int(item.get("dc_blocks", 0)) for item in dc_blocks_by_feeder)
        if dc_alloc != dc_total:
            warnings.append(
                f"DC block allocation mismatch: expected {dc_total}, got {dc_alloc}."
            )

    return warnings
