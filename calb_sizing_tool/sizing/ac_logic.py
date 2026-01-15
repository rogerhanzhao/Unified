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
