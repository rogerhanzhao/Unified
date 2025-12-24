import datetime
import io
from typing import Optional

import pandas as pd
from docx import Document
from docx.shared import Inches

from calb_sizing_tool.reporting.export_docx import (
    _add_appendix,
    _add_cover_page,
    _add_table,
    _doc_to_bytes,
    _setup_header,
    _setup_margins,
)
from calb_sizing_tool.reporting.report_context import ReportContext

try:
    import matplotlib.pyplot as plt

    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False


def _fmt(value, decimals=2, suffix=""):
    if value is None:
        return ""
    try:
        return f"{float(value):.{decimals}f}{suffix}"
    except Exception:
        return str(value)


def _format_percent(value, decimals=1):
    if value is None:
        return ""
    try:
        return f"{float(value) * 100:.{decimals}f}%"
    except Exception:
        return str(value)


def _default_formatter(value):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value)


def _add_dataframe_table(doc: Document, df: Optional[pd.DataFrame], columns, headers_map, formatters):
    if df is None or df.empty:
        doc.add_paragraph("No data available.")
        return

    rows = []
    for _, row in df.iterrows():
        rows.append([formatters.get(col, _default_formatter)(row.get(col)) for col in columns])

    headers = [headers_map.get(col, col) for col in columns]
    _add_table(doc, rows, headers)


def _plot_poi_usable_png(df: pd.DataFrame, poi_target: float, title: str) -> Optional[io.BytesIO]:
    if not MATPLOTLIB_AVAILABLE:
        return None
    try:
        data = df.sort_values("Year_Index").copy()
        x = data["Year_Index"].astype(int).tolist()
        y = data["POI_Usable_Energy_MWh"].astype(float).tolist()

        fig = plt.figure(figsize=(7.0, 3.2))
        ax = fig.add_subplot(111)
        ax.bar(x, y, color="#5cc3e4")
        ax.axhline(poi_target, linewidth=2, color="#ff0000")
        ax.set_title(title)
        ax.set_xlabel("Year (from COD)")
        ax.set_ylabel("POI Usable Energy (MWh)")
        ax.set_xticks(x)
        ax.grid(True, axis="y", linestyle="--", alpha=0.35)

        buf = io.BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format="png", dpi=150)
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception:
        return None


def export_report_v2(ctx: ReportContext) -> bytes:
    doc = Document()
    _setup_margins(doc)
    _setup_header(doc, title="Confidential Sizing Report (V2 Beta)")

    _add_cover_page(
        doc,
        "CALB Utility-Scale ESS Sizing Report (V2 Beta)",
        ctx.project_name,
        {"tool_version": "V2 Beta"},
    )

    doc.add_heading("Front Matter", level=2)
    front_rows = [
        ("Report Version", "V2 Beta"),
        ("Generated Date", datetime.datetime.now().strftime("%Y-%m-%d")),
        ("DC Dictionary Version", ctx.dictionary_version_dc),
        ("AC Dictionary Version", ctx.dictionary_version_ac),
        ("Scenario ID", ctx.scenario_id),
    ]
    _add_table(doc, front_rows, ["Item", "Value"])
    doc.add_paragraph("")

    doc.add_heading("Executive Summary", level=2)
    exec_rows = [
        ("POI Power Requirement (MW, POI AC)", _fmt(ctx.poi_power_requirement_mw, 2)),
        ("POI Energy Requirement (MWh, POI AC)", _fmt(ctx.poi_energy_requirement_mwh, 2)),
        ("POI Energy Guarantee (MWh, POI AC)", _fmt(ctx.poi_energy_guarantee_mwh, 2)),
        ("POI Usable Energy @ Guarantee Year (MWh)", _fmt(ctx.poi_usable_energy_mwh_at_guarantee_year, 2)),
        ("DC Blocks Total", _fmt(ctx.dc_blocks_total, 0)),
        ("AC Blocks Total", _fmt(ctx.ac_blocks_total, 0)),
        ("Total PCS Modules", _fmt(ctx.pcs_modules_total, 0)),
        ("Transformer Rating per Block (kVA)", _fmt(ctx.transformer_rating_kva, 0)),
        ("AC Block Template", ctx.ac_block_template_id),
        ("Avg DC Blocks per AC Block", _fmt(ctx.avg_dc_blocks_per_ac_block, 3)),
    ]
    _add_table(doc, exec_rows, ["Metric", "Value"])
    doc.add_paragraph("")

    doc.add_heading("Inputs & Assumptions", level=2)
    input_rows = [
        ("POI Power Requirement (MW, POI AC)", _fmt(ctx.poi_power_requirement_mw, 2)),
        ("POI Energy Requirement (MWh, POI AC)", _fmt(ctx.poi_energy_requirement_mwh, 2)),
        ("POI Energy Guarantee (MWh, POI AC)", _fmt(ctx.poi_energy_guarantee_mwh, 2)),
        ("POI Guarantee Year (from COD)", _fmt(ctx.poi_guarantee_year, 0)),
        ("Project Life (years)", _fmt(ctx.project_life_years, 0)),
        ("Cycles per Year", _fmt(ctx.cycles_per_year, 0)),
        ("Grid MV Voltage (kV, AC)", _fmt(ctx.grid_mv_voltage_kv_ac, 2)),
        ("PCS LV Voltage (V_LL,rms, AC)", _fmt(ctx.pcs_lv_voltage_v_ll_rms_ac, 0)),
        ("Grid Power Factor (PF)", _fmt(ctx.grid_power_factor, 3)),
        ("DC Round Trip Efficiency (fraction)", _fmt(ctx.stage1.get("dc_round_trip_efficiency_frac"), 4)),
        ("SC Loss (fraction)", _fmt(ctx.stage1.get("sc_loss_frac"), 4)),
        ("DOD (fraction)", _fmt(ctx.stage1.get("dod_frac"), 4)),
        ("Efficiency Chain (one-way, fraction)", _fmt(ctx.efficiency_chain_oneway_frac, 4)),
        ("Efficiency DC Cables (fraction)", _fmt(ctx.efficiency_components_frac.get("eff_dc_cables_frac"), 4)),
        ("Efficiency PCS (fraction)", _fmt(ctx.efficiency_components_frac.get("eff_pcs_frac"), 4)),
        ("Efficiency MVT (fraction)", _fmt(ctx.efficiency_components_frac.get("eff_mvt_frac"), 4)),
        ("Efficiency AC Cables/Switchgear/RMU (fraction)", _fmt(ctx.efficiency_components_frac.get("eff_ac_cables_sw_rmu_frac"), 4)),
        ("Efficiency HVT/Others (fraction)", _fmt(ctx.efficiency_components_frac.get("eff_hvt_others_frac"), 4)),
    ]
    _add_table(doc, input_rows, ["Parameter", "Value"])
    doc.add_paragraph("")

    doc.add_heading("Stage 1: Energy Requirement", level=2)
    doc.add_paragraph(
        "DC energy capacity required (MWh) = POI energy requirement / "
        "((1 - SC loss) * DOD * sqrt(DC RTE) * eta_chain_oneway)."
    )
    doc.add_paragraph(
        "POI-to-DC power requirement (MW) = POI power requirement / eta_chain_oneway."
    )
    s1_rows = [
        ("DC Energy Capacity Required (MWh)", _fmt(ctx.stage1.get("dc_energy_capacity_required_mwh"), 3)),
        ("DC Power Required (MW)", _fmt(ctx.stage1.get("dc_power_required_mw"), 3)),
        ("Efficiency Chain (one-way)", _format_percent(ctx.efficiency_chain_oneway_frac, 2)),
    ]
    _add_table(doc, s1_rows, ["Metric", "Value"])
    doc.add_paragraph("")

    doc.add_heading("Stage 2: DC Block Configuration", level=2)
    doc.add_paragraph(
        f"Based on sizing data dictionary {ctx.dictionary_version_dc} "
        f"and AC dictionary {ctx.dictionary_version_ac}."
    )
    dc_table = ctx.stage2.get("block_config_table") if isinstance(ctx.stage2, dict) else None
    if dc_table is not None and not dc_table.empty:
        dc_columns = [c for c in dc_table.columns if c not in ("Config Adjustment (%)", "Oversize (MWh)")]
        headers_map = {c: c for c in dc_columns}
        formatters = {}
        for col in dc_columns:
            if col in ("Unit Capacity (MWh)", "Subtotal (MWh)", "Total DC Nameplate @BOL (MWh)"):
                formatters[col] = lambda v, col=col: _fmt(v, 3)
            else:
                formatters[col] = lambda v: "" if v is None else str(v)
        _add_dataframe_table(doc, dc_table, dc_columns, headers_map, formatters)
    else:
        doc.add_paragraph("DC block configuration table unavailable.")
    doc.add_paragraph(
        f"DC total nameplate @BOL (MWh): {_fmt(ctx.dc_total_energy_mwh, 3)}; "
        f"Oversize (MWh): {_fmt(ctx.stage2.get('oversize_mwh'), 3)}."
    )
    if ctx.stage2.get("busbars_needed") is not None:
        doc.add_paragraph(f"DC busbars needed: {ctx.stage2.get('busbars_needed')}.")
    doc.add_paragraph("")

    doc.add_heading("Stage 3: Degradation & POI Deliverable", level=2)
    doc.add_paragraph(
        "Definitions: DC RTE is DC-side round-trip efficiency. "
        "System RTE = DC_RTE * (eta_chain_oneway)^2. "
        "Guarantee check uses POI energy guarantee value."
    )
    s3_df = ctx.stage3_df
    if s3_df is not None and not s3_df.empty:
        s3_columns = [
            "Year_Index",
            "SOH_Display_Pct",
            "SOH_Absolute_Pct",
            "DC_Usable_MWh",
            "POI_Usable_Energy_MWh",
            "DC_RTE_Pct",
            "System_RTE_Pct",
        ]
        headers_map = {
            "Year_Index": "Year (from COD)",
            "SOH_Display_Pct": "SOH @ COD Baseline (%)",
            "SOH_Absolute_Pct": "SOH vs FAT (%)",
            "DC_Usable_MWh": "DC Usable (MWh)",
            "POI_Usable_Energy_MWh": "POI Usable (MWh)",
            "DC_RTE_Pct": "DC RTE (%)",
            "System_RTE_Pct": "System RTE (%)",
        }
        formatters = {
            "Year_Index": lambda v: _fmt(v, 0),
            "SOH_Display_Pct": lambda v: _fmt(v, 1),
            "SOH_Absolute_Pct": lambda v: _fmt(v, 1),
            "DC_Usable_MWh": lambda v: _fmt(v, 2),
            "POI_Usable_Energy_MWh": lambda v: _fmt(v, 2),
            "DC_RTE_Pct": lambda v: _fmt(v, 1),
            "System_RTE_Pct": lambda v: _fmt(v, 1),
        }
        _add_dataframe_table(doc, s3_df, s3_columns, headers_map, formatters)

        chart = _plot_poi_usable_png(
            s3_df,
            poi_target=ctx.poi_energy_guarantee_mwh,
            title="POI Usable Energy vs Year",
        )
        if chart is not None:
            doc.add_paragraph("")
            doc.add_picture(chart, width=Inches(6.7))
        else:
            doc.add_paragraph("Chart export skipped (matplotlib not available).")
    else:
        doc.add_paragraph("Stage 3 data unavailable.")
    doc.add_paragraph("")

    doc.add_heading("Stage 4: AC Block Sizing", level=2)
    transformer_mva = None
    if ctx.grid_power_factor and ctx.grid_power_factor > 0 and ctx.ac_block_size_mw:
        transformer_mva = ctx.ac_block_size_mw / ctx.grid_power_factor
    feeders_total = ctx.ac_blocks_total * ctx.feeders_per_block if ctx.ac_blocks_total else 0
    s4_rows = [
        ("AC Block Template", ctx.ac_block_template_id),
        ("AC Block Size (MW)", _fmt(ctx.ac_block_size_mw, 3)),
        ("PCS per AC Block", _fmt(ctx.pcs_per_block, 0)),
        ("Feeders per AC Block", _fmt(ctx.feeders_per_block, 0)),
        ("Feeders Total", _fmt(feeders_total, 0)),
        ("PCS LV Voltage (V_LL,rms, AC)", _fmt(ctx.pcs_lv_voltage_v_ll_rms_ac, 0)),
        ("Grid MV Voltage (kV, AC)", _fmt(ctx.grid_mv_voltage_kv_ac, 2)),
        ("Grid Power Factor (PF)", _fmt(ctx.grid_power_factor, 3)),
        ("Transformer Rating (kVA)", _fmt(ctx.transformer_rating_kva, 0)),
        ("Transformer Formula (MVA)", f"{_fmt(ctx.ac_block_size_mw, 3)} / {_fmt(ctx.grid_power_factor, 3)} = {_fmt(transformer_mva, 3)}"),
    ]
    _add_table(doc, s4_rows, ["Metric", "Value"])

    if ctx.ac_blocks_total > 0:
        doc.add_paragraph("")
        doc.add_paragraph("DC Blocks per AC Block Allocation:")
        alloc_rows = []
        for entry in ctx.dc_blocks_allocation:
            alloc_rows.append(
                (
                    entry.get("dc_blocks_per_ac_block"),
                    entry.get("ac_blocks_count"),
                )
            )
        _add_table(doc, alloc_rows, ["DC Blocks per AC Block", "Number of AC Blocks"])
    doc.add_paragraph("")

    doc.add_heading("Integrated Configuration Summary", level=2)
    combined_rows = [
        ("DC Blocks Total", _fmt(ctx.dc_blocks_total, 0), ""),
        ("DC Unit Capacity (MWh)", _fmt(ctx.dc_block_unit_mwh, 3) if ctx.dc_block_unit_mwh else "mixed", ""),
        ("DC Total Energy (MWh)", _fmt(ctx.dc_total_energy_mwh, 3), ""),
        ("AC Block Template", "", ctx.ac_block_template_id),
        ("AC Blocks Total", "", _fmt(ctx.ac_blocks_total, 0)),
        ("Total PCS Modules", "", _fmt(ctx.pcs_modules_total, 0)),
        ("Transformer Rating (kVA)", "", _fmt(ctx.transformer_rating_kva, 0)),
        ("Grid MV Voltage (kV, AC)", "", _fmt(ctx.grid_mv_voltage_kv_ac, 2)),
    ]
    _add_table(doc, combined_rows, ["Metric", "DC", "AC"])
    doc.add_paragraph("")

    doc.add_heading("Single Line Diagram (SLD)", level=2)
    if ctx.sld_snapshot_hash:
        doc.add_paragraph(
            f"SLD snapshot hash: {ctx.sld_snapshot_hash} "
            f"(snapshot id: {ctx.sld_snapshot_id or 'n/a'})."
        )
    else:
        doc.add_paragraph("SLD placeholder - snapshot not generated.")
    doc.add_paragraph("")

    doc.add_heading("Layout", level=2)
    doc.add_paragraph("Layout placeholder - to be provided.")
    doc.add_paragraph("")

    doc.add_heading("QC Checks", level=2)
    if ctx.qc_checks:
        for item in ctx.qc_checks:
            doc.add_paragraph(f"- {item}")
    else:
        doc.add_paragraph("No QC warnings.")

    _add_appendix(
        doc,
        {
            "dictionary_version": ctx.dictionary_version_ac,
            "input_file_version": ctx.dictionary_version_dc,
        },
    )

    return _doc_to_bytes(doc)
