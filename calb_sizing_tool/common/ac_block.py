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

def _normalize_power_factor(value, default=0.9):
    if value is None:
        return default
    try:
        pf = float(value)
    except Exception:
        return default
    if pf > 1.5:
        pf = pf / 100.0
    if pf <= 0:
        return default
    return min(pf, 1.0)


def derive_ac_template_fields(ac_output: dict) -> dict:
    pcs_per_block = int(ac_output.get("pcs_per_block") or 0)
    if pcs_per_block <= 0:
        pcs_per_block = 2

    block_size_mw = float(ac_output.get("block_size_mw") or 0.0)
    pcs_power_kw = ac_output.get("pcs_power_kw")
    if pcs_power_kw is None and pcs_per_block:
        pcs_power_kw = block_size_mw * 1000 / pcs_per_block

    template_id = ac_output.get("ac_block_template_id")
    if not template_id:
        if pcs_power_kw:
            template_id = f"{pcs_per_block}x{int(round(pcs_power_kw))}kw"
        else:
            template_id = f"{pcs_per_block}xpcs"

    feeders_per_block = int(ac_output.get("feeders_per_block") or pcs_per_block or 0)

    grid_power_factor = ac_output.get("grid_power_factor")
    if grid_power_factor is None:
        transformer_kva = ac_output.get("transformer_kva")
        if transformer_kva:
            grid_power_factor = block_size_mw * 1000 / transformer_kva

    grid_power_factor = _normalize_power_factor(grid_power_factor, default=0.9)

    return {
        "ac_block_template_id": template_id,
        "pcs_per_block": pcs_per_block,
        "feeders_per_block": feeders_per_block,
        "grid_power_factor": grid_power_factor,
    }
