from pydantic import BaseModel
from typing import List, Optional

class ACBlockData(BaseModel):
    block_id: str
    mv_voltage_kv: float = 33.0
    lv_voltage_v: float = 800.0
    power_mw: float
    num_pcs: int
    pcs_power_kw: float
    transformer_name: str = "MV Trafo"

class DCBlockData(BaseModel):
    racks_per_cluster: int
    battery_voltage_v: float
    total_energy_mwh: float
    cluster_name: str = "Battery Cluster"

class ProjectSizingResult(BaseModel):
    project_name: str = "CALB Project"
    total_power_mw: float
    total_capacity_mwh: float
    ac_blocks: List[ACBlockData] = []
    dc_blocks: List[DCBlockData] = []