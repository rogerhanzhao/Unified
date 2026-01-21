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
DC_DATA_FILE_NEW = "ess_sizing_data_dictionary_v13_dc_autofit_rte314_fix05_v1.xlsx"
DC_DATA_FILE_LEGACY = "ess_sizing_data_dictionary_v13_dc_autofit.xlsx"

def resolve_dc_data_path() -> tuple[Path, bool]:
    new_path = DATA_DIR / DC_DATA_FILE_NEW
    if new_path.exists():
        return new_path, False
    legacy_path = DATA_DIR / DC_DATA_FILE_LEGACY
    if legacy_path.exists():
        return legacy_path, True
    fallback = get_excel_path("ess_sizing_data*.xlsx", DC_DATA_FILE_LEGACY)
    return fallback, fallback.name != DC_DATA_FILE_NEW

DC_DATA_PATH, DC_DATA_IS_LEGACY = resolve_dc_data_path()
