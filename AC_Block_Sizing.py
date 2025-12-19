# pages/4_Stage4_AC_Block.py
from __future__ import annotations
import math
from typing import Any, Dict, Optional

import streamlit as st

st.set_page_config(page_title="Stage 4 – AC Block", layout="wide")

# -----------------------------------------------------
# AC Block Sizing Functions
# -----------------------------------------------------

def find_ac_block_container_only(
    poi_mw: float,
    container_cnt: int,
    *,
    search_extra: int = 40
) -> Optional[Dict[str, Any]]:
    """
    Try container-only DC Blocks to match AC Blocks.
    """
    if container_cnt <= 0:
        return None

    candidates = [
        {"pcs_units": 2, "pcs_unit_kw": 1250, "ac_block_mw": 2.5},
        {"pcs_units": 2, "pcs_unit_kw": 1725, "ac_block_mw": 3.45},
        {"pcs_units": 4, "pcs_unit_kw": 1250, "ac_block_mw": 5.0},
        {"pcs_units": 4, "pcs_unit_kw": 1725, "ac_block_mw": 6.9},
    ]
    best = None
    best_score = None

    for cand in candidates:
        p_ac = cand["ac_block_mw"]
        n_min = max(1, int(math.ceil(poi_mw / p_ac)))

        for ac_qty in range(n_min, n_min + search_extra + 1):
            if container_cnt % ac_qty != 0:
                continue
            dc_per_block = container_cnt // ac_qty
            # Exclude exactly 3 DC Blocks per AC Block (design rule)
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
                    "pcs_units": cand["pcs_units"],
                    "pcs_unit_kw": cand["pcs_unit_kw"],
                    "dc_blocks_per_block": dc_per_block,
                    "total_ac_mw": total_ac,
                    "oversize_mw": oversize,
                }
    return best


def find_ac_block_mixed(
    poi_mw: float,
    container_cnt: int,
    cabinet_cnt: int,
    *,
    search_extra: int = 40
) -> Optional[Dict[str, Any]]:
    """
    Try mixed (container + cabinet) DC Blocks to match AC Blocks.
    """
    dc_total = container_cnt + cabinet_cnt
    if dc_total <= 0:
        return None

    candidates = [
        {"pcs_units": 2, "pcs_unit_kw": 1250, "ac_block_mw": 2.5},
        {"pcs_units": 2, "pcs_unit_kw": 1725, "ac_block_mw": 3.45},
        {"pcs_units": 4, "pcs_unit_kw": 1250, "ac_block_mw": 5.0},
        {"pcs_units": 4, "pcs_unit_kw": 1725, "ac_block_mw": 6.9},
    ]
    best = None
    best_score = None

    for cand in candidates:
        p_ac = cand["ac_block_mw"]
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
            # Exclude any configuration with exactly 3 DC per block
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
                    "pcs_units": cand["pcs_units"],
                    "pcs_unit_kw": cand["pcs_unit_kw"],
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

def suggest_dc_adjustments_for_ac_block(
    poi_mw: float,
    container_cnt: int,
    cabinet_cnt: int,
    *,
    search_extra: int = 40,
    max_delta: int = 4,
) -> list[str]:
    """Return human-readable suggestions for DC adjustments when no AC block fits."""
    suggestions: list[str] = []
    seen: set[tuple[int, int]] = set()

    def _try_match(cont: int, cab: int):
        res_container = find_ac_block_container_only(
            poi_mw=poi_mw, container_cnt=cont, search_extra=search_extra
        )
        if res_container:
            return "container_only", res_container
        res_mixed = find_ac_block_mixed(
            poi_mw=poi_mw, container_cnt=cont, cabinet_cnt=cab, search_extra=search_extra
        )
        if res_mixed:
            return "mixed", res_mixed
        return None, None

    for dc_delta in range(-max_delta, max_delta + 1):
        for cab_delta in range(-max_delta, max_delta + 1):
            new_cont = max(container_cnt + dc_delta, 0)
            new_cab = max(cabinet_cnt + cab_delta, 0)
            if new_cont == container_cnt and new_cab == cabinet_cnt:
                continue
            if new_cont + new_cab == 0:
                continue
            if (new_cont, new_cab) in seen:
                continue
            seen.add((new_cont, new_cab))
            mode, res = _try_match(new_cont, new_cab)
            if res:
                mode_label = "容器优先" if mode == "container_only" else "容器+柜体混合"
                suggestions.append(
                    f"调整为集装箱 {new_cont} / 柜体 {new_cab}（{mode_label}，AC Block 方案：{res['ac_block_qty']} × {res['ac_block_rated_mw']:.2f} MW）"
                )
            if len(suggestions) >= 3:
                break
        if len(suggestions) >= 3:
            break

    if not suggestions:
        suggestions.append("增加或减少 1–2 个集装箱/柜体以避免每个 AC Block 对应 3 个 DC Block。")
    return suggestions


# -----------------------------------------------------
# Main UI
# -----------------------------------------------------

st.title("Stage 4 – AC Block (V0.4)")
st.caption("Chain: RMU/SW → Transformer (MV/LV) → PCS → DC Busbar → DC Block")

stage13 = st.session_state.get("stage13_output")
if not stage13:
    st.error("Stage 1–3 output not found. Please complete sizing in Stage 1–3 first.")
    st.stop()

# Tabs for interaction
tab1, tab2, tab3 = st.tabs(
    ["Step 1 · AC Block Sizing", "Step 2 · Block SLD + Layout (placeholder)", "Step 3 · Site + Simulation (placeholder)"]
)

with tab1:
    # Read values from stage13_output
    poi_mw = stage13.get("poi_power_req_mw", 0.0)
    container_cnt = stage13.get("container_count", 0)
    cabinet_cnt = stage13.get("cabinet_count", 0)
    dc_total = stage13.get("dc_total_blocks", container_cnt + cabinet_cnt)
    poi_voltage = stage13.get("poi_nominal_voltage_kv", "")
    highest_equip_voltage = stage13.get("highest_equipment_voltage_kv", "")

    # Top Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("POI Power Requirement (MW)", f"{poi_mw:.2f}")
    c2.metric("DC Blocks Total", f"{dc_total}")
    c3.metric("POI Nominal Voltage (kV)", f"{poi_voltage}")
    

    st.write(f"Current DC configuration: container = {container_cnt}, cabinet = {cabinet_cnt}")
    st.divider()

    search_extra = st.number_input(
        "Search Extra AC Block Qty (V0.4)",
        min_value=0, value=40, step=5
    )

    stage4_alert_box = st.empty()

    if st.button("Run Step 1 · AC Block Sizing"):
        st.session_state.pop("stage4_adjustment_hint", None)
        stage4_alert_box.empty()

        # Try container-only
        best_container = find_ac_block_container_only(
            poi_mw=float(poi_mw),
            container_cnt=int(container_cnt),
            search_extra=int(search_extra),
        )
        stage4_top_level = None
        stage4_suggestions = []

        if best_container:
            st.success("Container-only DC Blocks matched AC Block configuration.")
            st.session_state["stage4_step1_result"] = best_container
        else:
            # Try mixed
            best_mixed = find_ac_block_mixed(
                poi_mw=float(poi_mw),
                container_cnt=int(container_cnt),
                cabinet_cnt=int(cabinet_cnt),
                search_extra=int(search_extra),
            )
            if best_mixed:
                stage4_top_level = "warning"
                st.session_state["stage4_step1_result"] = best_mixed
                stage4_suggestions = suggest_dc_adjustments_for_ac_block(
                    poi_mw=float(poi_mw),
                    container_cnt=int(container_cnt),
                    cabinet_cnt=int(cabinet_cnt),
                    search_extra=int(search_extra),
                )
            else:
                stage4_top_level = "error"
                stage4_suggestions = suggest_dc_adjustments_for_ac_block(
                    poi_mw=float(poi_mw),
                    container_cnt=int(container_cnt),
                    cabinet_cnt=int(cabinet_cnt),
                    search_extra=int(search_extra),
                )
                st.session_state.pop("stage4_step1_result", None)
                st.session_state["stage4_adjustment_hint"] = {
                    "reason": "当前 DC 配置无法找到合规的 AC Block。",
                    "suggestions": stage4_suggestions,
                }

        if stage4_top_level == "warning":
            stage4_alert_box.warning(
                "容器优先方案不满足设计规则，已尝试混合方案。可调整 DC 配置后重跑 Stage 4。"
            )
            if stage4_suggestions:
                for s in stage4_suggestions:
                    stage4_alert_box.markdown(f"- 建议：{s}")
        elif stage4_top_level == "error":
            stage4_alert_box.error(
                "未找到满足规则的 AC Block 配置，请调整 Stage 1–3 中的容器/柜体数量后重试。"
            )
            if stage4_suggestions:
                for s in stage4_suggestions:
                    stage4_alert_box.markdown(f"- 建议：{s}")
        else:
            stage4_alert_box.empty()

    res = st.session_state.get("stage4_step1_result")
    if res:
        st.markdown("## Step 1 · AC Block Sizing Summary (V0.4)")

        st.write(f"**Strategy**: {res.get('strategy', '').replace('_', ' ').title()}")

        cA, cB, cC, cD, cE = st.columns(5)
        with cA:
            st.metric("AC Blocks Quantity", f"{res['ac_block_qty']}")
        with cB:
            st.metric("AC Block Rating (MW)", f"{res['ac_block_rated_mw']:.2f}")
        with cC:
            st.metric("PCS per Block", f"{res['pcs_units']} × {res['pcs_unit_kw']} kW")
        with cD:
            st.metric("Total AC Capacity (MW)", f"{res['total_ac_mw']:.2f}")
        with cE:
            st.metric("Oversize vs POI (MW)", f"{res['oversize_mw']:.2f}")

        # DC Blocks per AC Block details
        if res.get("strategy") == "container_only":
            st.write(f"**DC Blocks per AC Block**: {res.get('dc_blocks_per_block', 0)}")
        else:
            st.write("**Mixed DC Distribution per AC Block**")
            st.write(f"• Containers / Block: {res.get('container_per_block', 0)}")
            st.write(f"• Cabinets / Block: {res.get('cabinet_per_block', 0)}")
            if res.get("container_rem", 0) or res.get("cabinet_rem", 0):
                st.write(
                    f"  ⚠ Remainder not evenly divisible: container_rem={res.get('container_rem', 0)}, "
                    f"cabinet_rem={res.get('cabinet_rem', 0)}"
                )
            st.write(
                f"  • DC Blocks per Block (base/max): "
                f"{res.get('dc_blocks_per_block_base', 0)} / {res.get('dc_blocks_per_block_max', 0)}"
            )

with tab2:
    st.info("Step 2 placeholder: Block-level Single Line Diagram and Local Layout (to be implemented).")

with tab3:
    st.info("Step 3 placeholder: Site Layout and Simulation (to be implemented).")
