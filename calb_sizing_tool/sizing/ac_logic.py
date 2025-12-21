import pandas as pd

def load_ac_data(data_path: str):
    """
    Load AC Block related data dictionary.
    """
    return pd.read_excel(data_path, sheet_name=None)

def ac_power_limit(ac_params: dict, poi_power: float):
    """
    Simple AC power limit logic.
    """
    return min(ac_params.get("ac_max_kw", poi_power), poi_power)

def ac_efficiency(ac_params: dict):
    """
    Return AC efficiency from parameters.
    """
    return ac_params.get("rte_ac", 0.97)
