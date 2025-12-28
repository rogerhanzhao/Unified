# calb_sizing_tool/ui/stage4_interface.py
import time
from typing import Any, Dict


def pack_stage13_output(
    stage1: Dict[str, Any],
    stage2: Dict[str, Any],
    stage3: Dict[str, Any],
    dc_block_total_qty: int,
    selected_scenario: str,
    poi_nominal_voltage_kv: float,
    poi_frequency_hz: Any = None,
) -> Dict[str, Any]:
    """
    Helper to package Stage 1-3 results into a standardized dictionary
    that Stage 4 (AC Block Sizing) can consume.

    This normalises types and provides safe defaults so downstream code
    doesn't need to repeatedly validate presence and types.
    """
    # capture the pack timestamp
    packed_at = int(time.time())

    # Safe coercion helpers
    def _f(v, default=0.0):
        try:
            return float(v) if v is not None else default
        except Exception:
            return default

    def _i(v, default=0):
        try:
            # None or falsy -> default
            if v is None:
                return default
            return int(v)
        except Exception:
            try:
                return int(float(v))
            except Exception:
                return default

    output: Dict[str, Any] = {}

    # Stage 1 values (with defaults)
    output["packed_at_epoch"] = packed_at
    output["project_name"] = stage1.get("project_name") or "CALB ESS Project"
    output["poi_power_req_mw"] = _f(stage1.get("poi_power_req_mw"), 0.0)
    output["poi_energy_req_mwh"] = _f(stage1.get("poi_energy_req_mwh"), 0.0)
    output["eff_dc_to_poi_frac"] = _f(stage1.get("eff_dc_to_poi_frac"), 0.0)
    output["dc_power_required_mw"] = _f(stage1.get("dc_power_required_mw"), 0.0)

    # Merge Stage 2 (container / cabinet / block) values
    output["dc_block_total_qty"] = int(dc_block_total_qty)
    output["dc_total_blocks"] = int(dc_block_total_qty)
    output["container_count"] = _i(stage2.get("container_count"))
    output["cabinet_count"] = _i(stage2.get("cabinet_count"))
    output["busbars_needed"] = _i(stage2.get("busbars_needed"))
    output["dc_nameplate_bol_mwh"] = _f(stage2.get("dc_nameplate_bol_mwh"), 0.0)
    output["block_config_table_records"] = stage2.get("block_config_table_records") or []
    output["oversize_mwh"] = _f(stage2.get("oversize_mwh"), 0.0)

    # Selection + nominal values
    output["selected_scenario"] = selected_scenario
    output["poi_nominal_voltage_kv"] = float(poi_nominal_voltage_kv)
    output["poi_frequency_hz"] = poi_frequency_hz

    # Stage 3 metadata
    output["effective_c_rate"] = _f(stage3.get("effective_c_rate"), 0.0)
    output["soh_profile_id"] = _i(stage3.get("soh_profile_id"))
    output["rte_profile_id"] = _i(stage3.get("rte_profile_id"))

    # Raw passthroughs for reference
    output["stage2_raw"] = stage2
    output["stage3_meta"] = stage3

    return output
