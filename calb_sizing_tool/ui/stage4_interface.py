# calb_sizing_tool/ui/stage4_interface.py
from typing import Any, Dict

def pack_stage13_output(
    stage1: Dict[str, Any],
    stage2: Dict[str, Any],
    stage3: Dict[str, Any],
    dc_block_total_qty: int,
    selected_scenario: str,
    poi_nominal_voltage_kv: float
) -> Dict[str, Any]:
    """
    Helper to package Stage 1-3 results into a standardized dictionary
    that Stage 4 (AC Block Sizing) can consume.
    """
    # Create a base dictionary from stage1 inputs
    output = stage1.copy()
    
    # Merge AC/DC block relevant info from Stage 2
    output.update({
        "dc_block_total_qty": dc_block_total_qty,
        "dc_total_blocks": dc_block_total_qty, # Alias
        "container_count": int(stage2.get("container_count", 0)),
        "cabinet_count": int(stage2.get("cabinet_count", 0)),
        "selected_scenario": selected_scenario,
        "poi_nominal_voltage_kv": poi_nominal_voltage_kv,
        # Pass through the raw Stage 2 configuration table if needed
        "stage2_raw": stage2,
        # Pass through Stage 3 meta data if needed
        "stage3_meta": stage3
    })
    
    return output