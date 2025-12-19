"""
Core DC sizing logic extracted from the Stage 1–3 workflows.

The helpers here provide pure calculation utilities that accept plain
dictionaries and return serialisable metrics dictionaries, mirroring the
behaviour of the existing UI logic while adding validation and
error-handling for standalone use.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, str):
            value = value.replace("%", "").replace(",", "").strip()
        return float(value)
    except Exception:
        return float(default)


def _to_frac(value: Any, default: float = 0.0) -> float:
    val = _to_float(value, default)
    if val > 1.5:
        return val / 100.0
    return val


def _safe_div(numer: float, denom: float, default: float = 0.0) -> float:
    try:
        if denom is None or abs(float(denom)) < 1e-12:
            return default
        return float(numer) / float(denom)
    except Exception:
        return default


def _calc_sc_loss_pct(sc_months: float) -> float:
    months = int(round(_to_float(sc_months, 0.0)))
    if months <= 0:
        return 0.0

    mapping = {
        1: 2.0,
        2: 2.0,
        3: 2.0,
        4: 2.5,
        5: 2.8,
        6: 3.0,
        7: 3.2,
        8: 3.5,
        9: 3.8,
        10: 4.1,
        11: 4.3,
        12: 4.5,
    }
    if months in mapping:
        return mapping[months]
    if months > 12:
        return 4.5 + 0.25 * (months - 12)
    return 0.0


def _require_dict(name: str, value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dictionary.")
    return value


def _extract_template(template: Dict[str, Any], label: str) -> Dict[str, Any]:
    if not template:
        raise ValueError(f"{label} template is required.")
    for required_key in ("capacity_mwh", "code", "name"):
        if required_key not in template:
            raise ValueError(f"{label} template missing required field '{required_key}'.")

    capacity = _to_float(template["capacity_mwh"], 0.0)
    if capacity <= 0:
        raise ValueError(f"{label} template capacity must be positive.")
    return {
        "capacity_mwh": capacity,
        "code": str(template["code"]),
        "name": str(template["name"]),
    }


def compute_dc_capacity(inputs: Dict[str, Any], defaults: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
    """
    Compute the theoretical DC capacity and power requirements (Stage 1).

    Args:
        inputs: User-supplied parameters (POI power/energy, efficiencies, etc.).
        defaults: Optional fallback values for any missing inputs.

    Returns:
        A metrics dictionary containing DC requirement, efficiencies, and
        lifecycle parameters.

    Raises:
        TypeError: If inputs/defaults are not dictionaries.
        ValueError: If numeric parameters are invalid.
    """
    defaults = defaults or {}
    _require_dict("inputs", inputs)
    _require_dict("defaults", defaults)

    def get(key: str, fallback: Any = None) -> Any:
        if key in inputs and inputs[key] is not None:
            return inputs[key]
        if key in defaults:
            return defaults[key]
        return fallback

    project_name = str(get("project_name", "CALB ESS Project"))
    poi_mw = _to_float(get("poi_power_req_mw", 100.0))
    poi_mwh = _to_float(get("poi_energy_req_mwh", 400.0))
    project_life_years = int(_to_float(get("project_life_years", 20)))
    cycles_per_year = int(_to_float(get("cycles_per_year", 365)))
    poi_guarantee_year = int(_to_float(get("poi_guarantee_year", 0)))

    for val, key in [
        (poi_mw, "poi_power_req_mw"),
        (poi_mwh, "poi_energy_req_mwh"),
        (project_life_years, "project_life_years"),
        (cycles_per_year, "cycles_per_year"),
    ]:
        if val < 0:
            raise ValueError(f"{key} cannot be negative.")

    eff_dc_cables = _to_frac(get("eff_dc_cables", 0.995))
    eff_pcs = _to_frac(get("eff_pcs", 0.985))
    eff_mvt = _to_frac(get("eff_mvt", 0.995))
    eff_ac_sw = _to_frac(get("eff_ac_cables_sw_rmu", 0.992))
    eff_hvt = _to_frac(get("eff_hvt_others", 1.0))
    eff_chain = eff_dc_cables * eff_pcs * eff_mvt * eff_ac_sw * eff_hvt

    sc_val = _to_float(get("sc_time_months", 3.0))
    if sc_val < 3.0:
        sc_val = 3.0
    sc_time_months = sc_val
    sc_loss_pct = _calc_sc_loss_pct(sc_time_months)
    sc_loss_frac = sc_loss_pct / 100.0

    dod_frac = _to_frac(get("dod_pct", 97.0))
    dc_rte_frac = _to_frac(get("dc_round_trip_efficiency_pct", 94.0))
    dc_one_way_eff = math.sqrt(dc_rte_frac) if dc_rte_frac >= 0 else 0.0
    dc_usable_bol_frac = dod_frac * dc_one_way_eff

    denom = (1.0 - sc_loss_frac) * dc_usable_bol_frac * eff_chain
    dc_energy_required = _safe_div(poi_mwh, denom, default=0.0)
    dc_power_required_mw = _safe_div(poi_mw, eff_chain, default=0.0) if eff_chain > 0 else 0.0

    return {
        "project_name": project_name,
        "poi_power_req_mw": poi_mw,
        "poi_energy_req_mwh": poi_mwh,
        "project_life_years": project_life_years,
        "cycles_per_year": cycles_per_year,
        "poi_guarantee_year": poi_guarantee_year,
        "eff_dc_cables_frac": eff_dc_cables,
        "eff_pcs_frac": eff_pcs,
        "eff_mvt_frac": eff_mvt,
        "eff_ac_cables_sw_rmu_frac": eff_ac_sw,
        "eff_hvt_others_frac": eff_hvt,
        "eff_dc_to_poi_frac": eff_chain,
        "sc_time_months": sc_time_months,
        "sc_loss_pct": sc_loss_pct,
        "sc_loss_frac": sc_loss_frac,
        "dod_frac": dod_frac,
        "dc_round_trip_efficiency_frac": dc_rte_frac,
        "dc_one_way_efficiency_frac": dc_one_way_eff,
        "dc_usable_bol_frac": dc_usable_bol_frac,
        "dc_energy_capacity_required_mwh": dc_energy_required,
        "dc_power_required_mw": dc_power_required_mw,
    }


def compute_dc_energy(
    required_dc_mwh: float,
    container_template: Dict[str, Any],
    *,
    cabinet_template: Optional[Dict[str, Any]] = None,
    mode: str = "container_only",
    k_max: int = 10,
) -> Dict[str, Any]:
    """
    Determine DC block counts for the requested capacity (Stage 2).

    Args:
        required_dc_mwh: Theoretical DC capacity required at BOL.
        container_template: Template describing container blocks (code/name/capacity_mwh).
        cabinet_template: Optional template describing cabinet blocks (required for hybrid/cabinet_only).
        mode: One of ``container_only``, ``hybrid``, ``cabinet_only``.
        k_max: Maximum cabinets per DC busbar (used in cabinet/hybrid modes).

    Returns:
        A metrics dictionary with block counts, oversize and configuration table records.

    Raises:
        ValueError: On invalid mode or missing/invalid template data.
    """
    required_dc_mwh = _to_float(required_dc_mwh, 0.0)
    if required_dc_mwh < 0:
        raise ValueError("required_dc_mwh cannot be negative.")
    if k_max <= 0:
        raise ValueError("k_max must be positive.")

    container = _extract_template(container_template, "Container")
    cabinet = _extract_template(cabinet_template or {}, "Cabinet") if mode in ("hybrid", "cabinet_only") else None

    def _format_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        total = sum(_to_float(r["Unit Capacity (MWh)"]) * int(r["Count"]) for r in rows) if rows else 0.0
        for row in rows:
            row["Subtotal (MWh)"] = _to_float(row["Unit Capacity (MWh)"]) * int(row["Count"])
        return rows, total

    mode_lower = str(mode or "").lower()
    if mode_lower not in ("container_only", "hybrid", "cabinet_only"):
        raise ValueError(f"Unknown mode: {mode}")

    if mode_lower == "container_only":
        count = int(math.ceil(required_dc_mwh / container["capacity_mwh"])) if required_dc_mwh > 0 else 0
        rows, total = _format_rows(
            [
                {
                    "Block Code": container["code"],
                    "Block Name": container["name"],
                    "Form": "container",
                    "Unit Capacity (MWh)": float(container["capacity_mwh"]),
                    "Count": count,
                }
            ]
        )
        busbars = 0
        cab_count = 0
        cont_count = count
    elif mode_lower == "cabinet_only":
        cab_count = int(math.ceil(required_dc_mwh / cabinet["capacity_mwh"])) if required_dc_mwh > 0 else 0
        busbars = int(math.ceil(cab_count / k_max)) if cab_count > 0 else 0
        rows, total = _format_rows(
            [
                {
                    "Block Code": cabinet["code"],
                    "Block Name": cabinet["name"],
                    "Form": "cabinet",
                    "Unit Capacity (MWh)": float(cabinet["capacity_mwh"]),
                    "Count": cab_count,
                }
            ]
        )
        cont_count = 0
    else:  # hybrid
        if required_dc_mwh <= 0:
            cont_count = 0
            cab_count = 0
        else:
            cont_count = int(math.floor(required_dc_mwh / container["capacity_mwh"]))
            remainder = required_dc_mwh - cont_count * container["capacity_mwh"]
            if remainder <= 1e-9:
                cab_count = 0
            else:
                cab_count = int(math.ceil(remainder / cabinet["capacity_mwh"]))

        busbars = 1 if cab_count > 0 else 0
        rows = []
        if cont_count > 0:
            rows.append(
                {
                    "Block Code": container["code"],
                    "Block Name": container["name"],
                    "Form": "container",
                    "Unit Capacity (MWh)": float(container["capacity_mwh"]),
                    "Count": cont_count,
                }
            )
        if cab_count > 0:
            rows.append(
                {
                    "Block Code": cabinet["code"],
                    "Block Name": cabinet["name"],
                    "Form": "cabinet",
                    "Unit Capacity (MWh)": float(cabinet["capacity_mwh"]),
                    "Count": cab_count,
                }
            )
        rows, total = _format_rows(rows)

    oversize = total - required_dc_mwh
    config_adjustment = (total / required_dc_mwh - 1.0) if required_dc_mwh > 0 else 0.0

    return {
        "mode": mode_lower,
        "dc_nameplate_bol_mwh": total,
        "oversize_mwh": oversize,
        "config_adjustment_frac": config_adjustment,
        "container_count": cont_count,
        "cabinet_count": cab_count,
        "busbars_needed": busbars,
        "block_config_table_records": rows,
    }


def _select_soh_value(curve: List[Dict[str, Any]], year: int) -> float:
    if not curve:
        raise ValueError("SOH curve cannot be empty.")
    sorted_curve = sorted(curve, key=lambda r: int(_to_float(r.get("Life_Year_Index", 0))))
    for entry in sorted_curve:
        if int(_to_float(entry.get("Life_Year_Index", -1))) == int(year):
            return _to_frac(entry.get("Soh_Dc_Pct", entry.get("Soh_Dc", 0.0)))
    last = sorted_curve[-1]
    return _to_frac(last.get("Soh_Dc_Pct", last.get("Soh_Dc", 0.0)))


def _select_rte_value(curve: List[Dict[str, Any]], soh_abs: float) -> float:
    if not curve:
        raise ValueError("RTE curve cannot be empty.")
    curve_sorted = sorted(
        curve,
        key=lambda r: _to_frac(r.get("Soh_Band_Min_Pct", r.get("Soh_Band_Min", 0.0))),
        reverse=True,
    )
    for entry in curve_sorted:
        threshold = _to_frac(entry.get("Soh_Band_Min_Pct", entry.get("Soh_Band_Min", 0.0)))
        if threshold <= soh_abs:
            return _to_frac(entry.get("Rte_Dc_Pct", entry.get("Rte_Dc", 0.0)))
    return _to_frac(curve_sorted[-1].get("Rte_Dc_Pct", curve_sorted[-1].get("Rte_Dc", 0.0)))


def compute_dc_lifecycle(
    stage1: Dict[str, Any],
    stage2: Dict[str, Any],
    lifecycle_inputs: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Evaluate lifecycle performance for the configured DC blocks (Stage 3).

    Args:
        stage1: Output from :func:`compute_dc_capacity`.
        stage2: Output from :func:`compute_dc_energy`.
        lifecycle_inputs: Dictionary containing ``soh_curve`` and ``rte_curve`` lists,
            plus optional ``guarantee_year``.

    Returns:
        A metrics dictionary with lifecycle profile, guarantee-year performance,
        and supporting metadata.

    Raises:
        TypeError: If parameters are not dictionaries.
        ValueError: If required numeric values or curves are invalid.
    """
    _require_dict("stage1", stage1)
    _require_dict("stage2", stage2)
    _require_dict("lifecycle_inputs", lifecycle_inputs)

    dc_nameplate_bol_mwh = _to_float(stage2.get("dc_nameplate_bol_mwh", 0.0), 0.0)
    if dc_nameplate_bol_mwh <= 0:
        raise ValueError("dc_nameplate_bol_mwh must be positive for lifecycle evaluation.")

    project_life_years = int(_to_float(stage1.get("project_life_years", 0)))
    eff_chain = _to_float(stage1.get("eff_dc_to_poi_frac", 0.0))
    sc_loss_frac = _to_float(stage1.get("sc_loss_frac", 0.0))
    dod_frac = _to_float(stage1.get("dod_frac", 0.0))
    poi_energy_mwh = _to_float(stage1.get("poi_energy_req_mwh", 0.0))
    guarantee_year = int(
        _to_float(
            lifecycle_inputs.get("guarantee_year", stage1.get("poi_guarantee_year", 0)),
            0,
        )
    )

    dc_power_mw = _safe_div(stage1.get("poi_power_req_mw", 0.0), eff_chain, default=0.0) if eff_chain > 0 else 0.0
    effective_c_rate = _safe_div(dc_power_mw, dc_nameplate_bol_mwh, default=0.0)

    soh_curve: List[Dict[str, Any]] = lifecycle_inputs.get("soh_curve") or []
    rte_curve: List[Dict[str, Any]] = lifecycle_inputs.get("rte_curve") or []
    if not isinstance(soh_curve, Iterable) or not soh_curve:
        raise ValueError("soh_curve must be a non-empty iterable of records.")
    if not isinstance(rte_curve, Iterable) or not rte_curve:
        raise ValueError("rte_curve must be a non-empty iterable of records.")

    records: List[Dict[str, Any]] = []
    guarantee_energy = None

    for year in range(0, project_life_years + 1):
        soh_rel = _select_soh_value(list(soh_curve), year)
        soh_abs = soh_rel * (1.0 - sc_loss_frac)
        dc_rte_frac_year = max(0.0, min(1.0, _select_rte_value(list(rte_curve), soh_abs)))
        dc_one_way_eff_year = math.sqrt(dc_rte_frac_year)

        dc_gross_capacity_mwh_year = dc_nameplate_bol_mwh * soh_abs
        dc_usable_mwh_year = dc_gross_capacity_mwh_year * dod_frac * dc_one_way_eff_year
        poi_usable_mwh_year = max(dc_usable_mwh_year * eff_chain, 0.0)
        system_rte_frac_year = max(0.0, min(1.0, dc_rte_frac_year * (eff_chain**2)))
        meets_poi_energy = poi_usable_mwh_year >= poi_energy_mwh

        row = {
            "year_index": int(year),
            "soh_relative": soh_rel,
            "soh_absolute": soh_abs,
            "dc_nameplate_bol_mwh": dc_nameplate_bol_mwh,
            "dc_gross_capacity_mwh": dc_gross_capacity_mwh_year,
            "dc_usable_mwh": dc_usable_mwh_year,
            "dc_rte_frac": dc_rte_frac_year,
            "system_rte_frac": system_rte_frac_year,
            "poi_usable_energy_mwh": poi_usable_mwh_year,
            "meets_poi_requirement": meets_poi_energy,
            "is_guarantee_year": year == guarantee_year,
        }
        records.append(row)

        if year == guarantee_year:
            guarantee_energy = poi_usable_mwh_year

    meets_guarantee = guarantee_energy is not None and guarantee_energy + 1e-6 >= poi_energy_mwh

    return {
        "meta": {
            "poi_power_mw": _to_float(stage1.get("poi_power_req_mw", 0.0)),
            "dc_power_mw": dc_power_mw,
            "effective_c_rate": effective_c_rate,
            "guarantee_year": guarantee_year,
        },
        "yearly_profile": records,
        "guarantee_energy_mwh": guarantee_energy,
        "meets_guarantee_requirement": bool(meets_guarantee),
    }
