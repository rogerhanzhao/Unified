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

def _is_nan(value) -> bool:
    try:
        return value != value  # NaN check
    except Exception:
        return False


def format_percent(value, input_is_fraction=None) -> str:
    if value is None or _is_nan(value):
        return ""
    try:
        numeric = float(value)
    except Exception:
        return str(value)

    if input_is_fraction is None:
        is_fraction = numeric <= 1.2
    else:
        is_fraction = bool(input_is_fraction)

    percent = numeric * 100 if is_fraction else numeric
    return f"{percent:.2f}%"


def format_value(value, unit: str) -> str:
    if value is None or _is_nan(value):
        return ""
    try:
        numeric = float(value)
    except Exception:
        return str(value)

    unit_key = (unit or "").lower()
    if unit_key in ("mw", "mwh"):
        return f"{numeric:.2f}"
    if unit_key == "kv":
        return f"{numeric:.2f}"
    if unit_key == "v":
        return f"{numeric:.0f}"
    if unit_key == "kva":
        return f"{numeric:.0f}"
    if unit_key == "mva":
        return f"{numeric:.3f}"
    if unit_key == "hz":
        return f"{numeric:.0f}"
    if unit_key in ("pf",):
        return f"{numeric:.2f}"
    if unit_key in ("%", "percent"):
        return format_percent(numeric)
    return str(value)
