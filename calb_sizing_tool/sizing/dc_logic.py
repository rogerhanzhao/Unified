import pandas as pd

def load_dc_data(data_path: str):
    """
    Load DC Block related data from Data Dictionary.
    """
    return pd.read_excel(data_path, sheet_name=None)

def calculate_dc_energy(dc_params: dict, profile: list):
    """
    Compute DC energy deliverable based on profile and DC Block params.
    """
    # 只是示例，按真实逻辑替换
    total_energy = dc_params.get("capacity_nominal", 0)
    delivered = sum(profile) / len(profile) * total_energy
    return delivered

def dc_rte_calculation(dc_params: dict):
    """
    Compute DC round-trip efficiency.
    """
    # 用简单公式作为示例
    return dc_params.get("rte_dc", 0.94)