from pydantic import BaseModel
from typing import List, Optional

class DCBlockResult(BaseModel):
    block_id: str = "DC-Block"
    container_model: str = "CALB-314Ah"
    racks_per_container: int = 10
    voltage_v: float = 1200.0
    capacity_mwh: float = 5.0
    count: int = 0

class ACBlockResult(BaseModel):
    block_id: str = "AC-Block"
    transformer_kva: float = 2500.0
    mv_voltage_kv: float = 33.0
    lv_voltage_v: float = 800.0
    pcs_power_kw: float = 1250.0
    num_pcs: int = 2
    dc_blocks_connected: List[DCBlockResult] = []

class ProjectSizingResult(BaseModel):
    project_name: str = "Project"
    system_power_mw: float = 0.0
    system_capacity_mwh: float = 0.0
    ac_blocks: List[ACBlockResult] = []

    @property
    def total_dc_blocks(self):
        return sum(b.count for ac in self.ac_blocks for b in ac.dc_blocks_connected)

# Aliases for backward compatibility if needed
SizingResult = ProjectSizingResult