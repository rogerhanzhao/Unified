# pages/4_Stage4_AC_Block.py
from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import streamlit as st
from matplotlib.patches import Rectangle

from . import DATA_DIR, PROJECT_ROOT

# Path utilities reserved for future data access
_ = (PROJECT_ROOT, DATA_DIR)

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

    if st.button("Run Step 1 · AC Block Sizing"):
        # Try container-only
        best_container = find_ac_block_container_only(
            poi_mw=float(poi_mw),
            container_cnt=int(container_cnt),
            search_extra=int(search_extra),
        )
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
                st.warning("Container-only did not satisfy rules, using mixed DC Blocks for AC Block matching.")
                st.session_state["stage4_step1_result"] = best_mixed
            else:
                st.error(
                    "Neither container-only nor mixed DC Blocks can satisfy AC Block rules. "
                    "Please revise DC configuration in Stage 1–3 (e.g., adjust container/cabinet counts)."
                )

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
    st.markdown("## Step 2 · Block SLD and Local Layout")

    step1 = st.session_state.get("stage4_step1_result", {})
    ac_blocks_qty = int(step1.get("ac_block_qty", 1) or 1)
    pcs_units = int(step1.get("pcs_units", 2) or 2)
    dc_blocks_total = int(stage13.get("dc_block_total_qty", stage13.get("dc_total_blocks", 1)) or 1)
    dc_per_ac_block = max(1, int(round(dc_blocks_total / ac_blocks_qty)))

    def plot_block_sld(ac_qty: int, pcs_per_block: int, dc_blocks: int) -> plt.Figure:
        fig, ax = plt.subplots(figsize=(10, 4))

        nodes: Dict[str, Tuple[float, float]] = {
            "RMU": (0.5, 0.5),
            "Transformer (MV/LV)": (2.0, 0.5),
            "PCS": (3.5, 0.5),
            "AC Busbar": (5.0, 0.7),
            "DC Busbar": (6.5, 0.7),
            "DC Blocks": (8.0, 0.7),
        }

        for label, (x, y) in nodes.items():
            rect = Rectangle((x - 0.35, y - 0.2), 0.7, 0.4, edgecolor="black", facecolor="#cde6ff")
            ax.add_patch(rect)
            ax.text(x, y, label, ha="center", va="center", fontsize=10)

        edges: List[Tuple[str, str]] = [
            ("RMU", "Transformer (MV/LV)"),
            ("Transformer (MV/LV)", "PCS"),
            ("PCS", "AC Busbar"),
            ("AC Busbar", "DC Busbar"),
            ("DC Busbar", "DC Blocks"),
        ]

        for src, dst in edges:
            xs, ys = nodes[src]
            xd, yd = nodes[dst]
            ax.annotate(
                "",
                xy=(xd - 0.35, yd),
                xytext=(xs + 0.35, ys),
                arrowprops=dict(arrowstyle="->", lw=2, color="#1f77b4"),
            )

        ax.set_xlim(0, 8.5)
        ax.set_ylim(0, 1.2)
        ax.axis("off")
        ax.set_title("Block-level Single Line Diagram (SLD)")
        ax.text(
            3.5,
            1.05,
            f"AC Blocks: {ac_qty} · PCS per Block: {pcs_per_block} · DC Blocks per AC Block: {dc_blocks}",
            ha="center",
            fontsize=9,
        )
        return fig

    st.pyplot(plot_block_sld(ac_blocks_qty, pcs_units, dc_per_ac_block))

    st.markdown("### Local Layout (20 ft container, NFPA 855 clearances)")
    clearance_m = st.number_input("Minimum clearance between equipment (m)", min_value=0.1, max_value=1.0, value=0.3, step=0.05)

    def plot_local_layout(clearance: float) -> Tuple[plt.Figure, List[Tuple[str, str, float]]]:
        fig, ax = plt.subplots(figsize=(8, 4))

        container_length = 6.096
        container_width = 2.438
        ax.add_patch(Rectangle((0, 0), container_length, container_width, fill=False, linestyle="--", color="#555"))
        ax.text(container_length / 2, container_width + 0.05, "20 ft Container Footprint", ha="center", va="bottom")

        positions: Dict[str, Tuple[float, float]] = {
            "RMU": (0.6, 1.2),
            "Transformer": (1.8, 1.2),
            "PCS": (3.1, 1.2),
            "AC Busbar": (4.4, 0.7),
            "DC Busbar": (5.1, 1.7),
        }

        for name, (x, y) in positions.items():
            ax.add_patch(Rectangle((x - 0.35, y - 0.25), 0.7, 0.5, facecolor="#f0f6ff", edgecolor="#1f77b4"))
            ax.text(x, y, name, ha="center", va="center", fontsize=9)

        distances: List[Tuple[str, str, float]] = []
        keys = list(positions.keys())
        for i, a in enumerate(keys):
            for b in keys[i + 1 :]:
                xa, ya = positions[a]
                xb, yb = positions[b]
                dist = math.dist((xa, ya), (xb, yb))
                distances.append((a, b, dist))
                if dist < clearance:
                    ax.plot([xa, xb], [ya, yb], color="red", linestyle=":", lw=1)
                else:
                    ax.plot([xa, xb], [ya, yb], color="green", linestyle=":", lw=0.5)

        ax.set_xlim(-0.2, container_length + 0.2)
        ax.set_ylim(-0.2, container_width + 0.6)
        ax.set_aspect("equal")
        ax.set_xlabel("Meters (longitudinal)")
        ax.set_ylabel("Meters (transverse)")
        ax.set_title("Local Layout with Clearance Checks")
        ax.grid(True, linestyle=":", linewidth=0.5)

        return fig, distances

    layout_fig, clearance_data = plot_local_layout(clearance_m)
    st.pyplot(layout_fig)

    st.markdown("#### Clearance Verification (NFPA 855 style guidance)")
    warn_rows = []
    ok_rows = []
    for a, b, dist in clearance_data:
        row = f"{a} → {b}: {dist:.2f} m"
        if dist < clearance_m:
            warn_rows.append(row + " (below target clearance)")
        else:
            ok_rows.append(row)

    if warn_rows:
        st.error("Clearance shortfalls detected:")
        for line in warn_rows:
            st.write(f"- {line}")
    else:
        st.success("All component spacings meet or exceed the selected clearance target.")

    st.write("Compliant spacing supports NFPA 855 objectives for working clearances and fire separation between PCS, transformers, and busbars.")

with tab3:
    st.markdown("## Step 3 · Power Flow + Fault Simulation")

    default_dc = float(stage13.get("dc_power_required_mw", stage13.get("poi_power_req_mw", 5.0)) or 5.0)
    dc_power = st.slider("DC Block output (MW)", min_value=1.0, max_value=max(10.0, default_dc), value=default_dc, step=0.5)
    pcs_eff = st.slider("PCS efficiency", min_value=0.90, max_value=0.99, value=0.96, step=0.005)
    transformer_eff = st.slider("Transformer efficiency", min_value=0.95, max_value=0.99, value=0.985, step=0.005)
    aux_losses = st.slider("Auxiliary losses (fraction)", min_value=0.0, max_value=0.1, value=0.02, step=0.005)
    fault_mode = st.selectbox("Fault scenario", ["normal", "short_circuit", "transformer_failure", "pcs_derate"])

    def simulate_power(dc_mw: float, eff_pcs: float, eff_tx: float, aux_loss: float, scenario: str) -> Dict[str, Any]:
        gross_ac = dc_mw * eff_pcs * eff_tx
        aux_penalty = gross_ac * aux_loss
        ac_at_poi = gross_ac - aux_penalty
        status = "System operating normally"

        if scenario == "short_circuit":
            ac_at_poi = 0.0
            status = "Short circuit detected → isolating fault and re-routing to remaining feeders"
        elif scenario == "transformer_failure":
            ac_at_poi *= 0.5
            status = "Transformer failure → shifting to backup / parallel transformer at 50% availability"
        elif scenario == "pcs_derate":
            ac_at_poi *= 0.75
            status = "PCS derated → thermal limit triggered; output limited to 75%"

        losses = dc_mw - (ac_at_poi / (eff_tx * eff_pcs) if eff_pcs and eff_tx else 0.0)
        return {
            "gross_ac": gross_ac,
            "ac_at_poi": max(ac_at_poi, 0.0),
            "status": status,
            "losses_mw": max(losses, 0.0),
        }

    sim = simulate_power(dc_power, pcs_eff, transformer_eff, aux_losses, fault_mode)

    c1, c2, c3 = st.columns(3)
    c1.metric("Gross AC after PCS + Transformer (MW)", f"{sim['gross_ac']:.2f}")
    c2.metric("Delivered to POI (MW)", f"{sim['ac_at_poi']:.2f}")
    c3.metric("Estimated Losses (MW)", f"{sim['losses_mw']:.2f}")

    st.info(sim["status"])

    st.markdown("#### Notes")
    st.write("- Power flow applies PCS + transformer efficiency chain and deducts auxiliary losses.")
    st.write("- Fault cases illustrate isolation, backup transformer engagement, and PCS derating impacts.")
