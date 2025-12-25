from calb_sizing_tool.sld.snapshot_schema import validate_snapshot_v1


def run_sld_qc(snapshot: dict) -> list[str]:
    warnings = []
    try:
        validate_snapshot_v1(snapshot)
    except ValueError as exc:
        warnings.append(str(exc))
        return warnings

    feeders = snapshot["feeders"]
    dc_blocks_by_feeder = snapshot["dc_blocks_by_feeder"]
    if len(feeders) != 4:
        warnings.append(f"Feeder count mismatch: expected 4, got {len(feeders)}.")

    if len(dc_blocks_by_feeder) != len(feeders):
        warnings.append(
            "dc_blocks_by_feeder entries do not match feeders count."
        )

    ac_block = snapshot.get("ac_block", {})
    if ac_block.get("feeders_per_block") not in (None, 4):
        warnings.append("Snapshot feeders_per_block is not 4 for the single-chain SLD.")
    if ac_block.get("pcs_per_block") not in (None, 4):
        warnings.append("Snapshot pcs_per_block is not 4 for the single-chain SLD.")

    mv_node = snapshot.get("mv_node", {})
    transformer = snapshot.get("transformer", {})
    if mv_node.get("mv_kv_ac") is None:
        warnings.append("MV voltage (mv_kv_ac) is missing.")
    if transformer.get("hv_kv") is None or transformer.get("lv_kv") is None:
        warnings.append("Transformer HV/LV voltage is missing.")
    if transformer.get("rated_kva") is None and transformer.get("rated_mva") is None:
        warnings.append("Transformer rating is missing.")

    for feeder in feeders:
        if feeder.get("pcs_kw") is None:
            warnings.append("PCS rating (pcs_kw) missing on one or more feeders.")
            break

    dc_total = snapshot.get("dc_block_summary", {}).get("dc_blocks_total")
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
