"""
AC block sizing helpers extracted from the Stage 4 workflow.

The functions are designed to accept plain dictionaries, perform validation,
and return serialisable metrics dictionaries that match the behaviour of the
existing Streamlit page logic.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


def _require_dict(name: str, value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dictionary.")
    return value


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


def _default_candidates() -> List[Dict[str, float]]:
    return [
        {"pcs_units": 2, "pcs_unit_kw": 1250, "ac_block_mw": 2.5},
        {"pcs_units": 2, "pcs_unit_kw": 1725, "ac_block_mw": 3.45},
        {"pcs_units": 4, "pcs_unit_kw": 1250, "ac_block_mw": 5.0},
        {"pcs_units": 4, "pcs_unit_kw": 1725, "ac_block_mw": 6.9},
    ]


def compute_ac_capacity(
    inputs: Dict[str, Any],
    *,
    candidates: Optional[List[Dict[str, float]]] = None,
    allow_mixed: bool = True,
) -> Dict[str, Any]:
    """
    Compute an AC block configuration that satisfies POI power requirements.

    Args:
        inputs: Dictionary containing ``poi_mw``, ``container_count``, ``cabinet_count``,
            and optional ``search_extra`` (defaults to 40).
        candidates: Optional list of AC block templates; defaults mirror the UI logic.
        allow_mixed: Whether mixed container+cabinet DC blocks are allowed as a fallback.

    Returns:
        A metrics dictionary describing the chosen AC block configuration.

    Raises:
        TypeError: If ``inputs`` is not a dictionary.
        ValueError: If parameters are invalid or no configuration can be found.
    """
    _require_dict("inputs", inputs)
    poi_mw = _to_float(inputs.get("poi_mw", inputs.get("poi_power_mw", 0.0)))
    container_cnt = int(_to_float(inputs.get("container_count", 0)))
    cabinet_cnt = int(_to_float(inputs.get("cabinet_count", 0)))
    search_extra = int(_to_float(inputs.get("search_extra", 40)))

    if poi_mw <= 0:
        raise ValueError("poi_mw must be positive.")
    if container_cnt < 0 or cabinet_cnt < 0:
        raise ValueError("container_count and cabinet_count cannot be negative.")
    if search_extra < 0:
        raise ValueError("search_extra cannot be negative.")

    candidates = candidates or _default_candidates()
    if not candidates:
        raise ValueError("At least one AC block candidate is required.")

    def _score_container_only() -> Optional[Dict[str, Any]]:
        if container_cnt <= 0:
            return None
        best: Optional[Dict[str, Any]] = None
        best_score: Optional[tuple] = None
        for cand in candidates:
            p_ac = _to_float(cand.get("ac_block_mw", 0.0), 0.0)
            if p_ac <= 0:
                continue
            n_min = max(1, int(math.ceil(poi_mw / p_ac)))
            for ac_qty in range(n_min, n_min + search_extra + 1):
                if container_cnt % ac_qty != 0:
                    continue
                dc_per_block = container_cnt // ac_qty
                if dc_per_block == 3:
                    continue
                total_ac = ac_qty * p_ac
                if total_ac < poi_mw:
                    continue
                oversize = total_ac - poi_mw
                score = (oversize, ac_qty)
                if best_score is None or score < best_score:
                    best_score = score
                    best = {
                        "strategy": "container_only",
                        "ac_block_qty": ac_qty,
                        "ac_block_rated_mw": p_ac,
                        "pcs_units": int(cand.get("pcs_units", 0)),
                        "pcs_unit_kw": _to_float(cand.get("pcs_unit_kw", 0.0)),
                        "dc_blocks_per_block": dc_per_block,
                        "total_ac_mw": total_ac,
                        "oversize_mw": oversize,
                    }
        return best

    def _score_mixed() -> Optional[Dict[str, Any]]:
        dc_total = container_cnt + cabinet_cnt
        if not allow_mixed or dc_total <= 0:
            return None
        best: Optional[Dict[str, Any]] = None
        best_score: Optional[tuple] = None
        for cand in candidates:
            p_ac = _to_float(cand.get("ac_block_mw", 0.0))
            if p_ac <= 0:
                continue
            n_min = max(1, int(math.ceil(poi_mw / p_ac)))
            for ac_qty in range(n_min, n_min + search_extra + 1):
                cont_per_block = container_cnt // ac_qty
                cab_per_block = cabinet_cnt // ac_qty
                cont_rem = container_cnt % ac_qty
                cab_rem = cabinet_cnt % ac_qty
                base_dc_each = cont_per_block + cab_per_block
                if base_dc_each == 0 and (cont_rem + cab_rem) == 0:
                    continue
                max_dc_each = base_dc_each + (1 if cont_rem > 0 or cab_rem > 0 else 0)
                if base_dc_each == 3 or max_dc_each == 3:
                    continue
                total_dc_calc = (cont_per_block * ac_qty + cont_rem) + (cab_per_block * ac_qty + cab_rem)
                if total_dc_calc != dc_total:
                    continue
                total_ac = ac_qty * p_ac
                if total_ac < poi_mw:
                    continue
                oversize = total_ac - poi_mw
                score = (oversize, max_dc_each - base_dc_each, ac_qty)
                if best_score is None or score < best_score:
                    best_score = score
                    best = {
                        "strategy": "mixed",
                        "ac_block_qty": ac_qty,
                        "ac_block_rated_mw": p_ac,
                        "pcs_units": int(cand.get("pcs_units", 0)),
                        "pcs_unit_kw": _to_float(cand.get("pcs_unit_kw", 0.0)),
                        "container_per_block": cont_per_block,
                        "cabinet_per_block": cab_per_block,
                        "container_rem": cont_rem,
                        "cabinet_rem": cab_rem,
                        "dc_blocks_per_block_base": base_dc_each,
                        "dc_blocks_per_block_max": max_dc_each,
                        "total_ac_mw": total_ac,
                        "oversize_mw": oversize,
                    }
        return best

    best_container = _score_container_only()
    if best_container:
        return best_container

    best_mixed = _score_mixed()
    if best_mixed:
        return best_mixed

    raise ValueError("No feasible AC block configuration found for the given inputs.")


def compute_ac_efficiency(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate AC-side efficiency chain and losses.

    Args:
        inputs: Dictionary containing optional efficiency entries (fraction or percent):
            ``pcs_efficiency``, ``transformer_efficiency``, ``ac_cable_efficiency``,
            ``hvt_efficiency``, ``dc_cable_efficiency``.

    Returns:
        A metrics dictionary with component efficiencies, aggregate chain efficiency,
        and total loss percentage.

    Raises:
        TypeError: If ``inputs`` is not a dictionary.
        ValueError: If any efficiency is outside (0, 1].
    """
    _require_dict("inputs", inputs)
    components = {
        "dc_cable_efficiency": _to_frac(inputs.get("dc_cable_efficiency", inputs.get("eff_dc_cables", 1.0)), 1.0),
        "pcs_efficiency": _to_frac(inputs.get("pcs_efficiency", inputs.get("eff_pcs", 1.0)), 1.0),
        "transformer_efficiency": _to_frac(
            inputs.get("transformer_efficiency", inputs.get("eff_mvt", 1.0)), 1.0
        ),
        "ac_cable_efficiency": _to_frac(
            inputs.get("ac_cable_efficiency", inputs.get("eff_ac_cables_sw_rmu", 1.0)), 1.0
        ),
        "hvt_efficiency": _to_frac(inputs.get("hvt_efficiency", inputs.get("eff_hvt_others", 1.0)), 1.0),
    }

    for name, val in components.items():
        if val <= 0 or val > 1.0:
            raise ValueError(f"{name} must be within (0, 1].")

    eff_chain = (
        components["dc_cable_efficiency"]
        * components["pcs_efficiency"]
        * components["transformer_efficiency"]
        * components["ac_cable_efficiency"]
        * components["hvt_efficiency"]
    )
    return {
        "components": components,
        "ac_to_poi_efficiency": eff_chain,
        "total_loss_fraction": 1.0 - eff_chain,
        "total_loss_pct": (1.0 - eff_chain) * 100.0,
    }
