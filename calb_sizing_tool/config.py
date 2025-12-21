import os
import glob
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.absolute()
DATA_DIR = PROJECT_ROOT / "data"

def get_excel_path(pattern: str, default: str) -> Path:
    """Finds file in data dir, robust to naming variations."""
    # 1. Exact match
    exact = DATA_DIR / default
    if exact.exists():
        return exact
    # 2. Glob match
    candidates = list(DATA_DIR.glob(pattern))
    if candidates:
        return sorted(candidates)[-1]
    return exact

AC_DATA_PATH = get_excel_path("AC_Block_Data*.xlsx", "AC_Block_Data_Dictionary_v1_1.xlsx")
DC_DATA_PATH = get_excel_path("ess_sizing_data*.xlsx", "ess_sizing_data_dictionary_v13_dc_automation.xlsx")