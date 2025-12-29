import datetime
import io
import re
from typing import Optional

import pandas as pd
from docx import Document
from docx.shared import Inches

from calb_sizing_tool.reporting.export_docx import _add_cover_page, _add_table, _doc_to_bytes, _setup_header, _setup_margins
from calb_sizing_tool.reporting.formatter import format_percent, format_value
from calb_sizing_tool.reporting.report_context import ReportContext

try:
    import matplotlib.pyplot as plt

    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False

try:
    import cairosvg

    CAIROSVG_AVAILABLE = True
except Exception:
    CAIROSVG_AVAILABLE = False


def _format_percent_with_fraction(value, input_is_fraction=None, fraction_decimals=4) -> str:
    if value is None:
        return ""
    try:
        numeric = float(value)
    except Exception:
        return str(value)

    if input_is_fraction is None:
        is_fraction = numeric <= 1.2
    else:
        is_fraction = bool(input_is_fraction)

    fraction = numeric if is_fraction else numeric / 100.0
    percent_text = format_percent(numeric, input_is_fraction=is_fraction)
    return f"{percent_text} ({fraction:.{fraction_decimals}f})"


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


def _plot_dc_capacity_bar_png(
    bol_mwh: Optional[float],
    s3_df: Optional[pd.DataFrame],
    guarantee_year: int,
    title: str,
) -> Optional[io.BytesIO]:
    if not MATPLOTLIB_AVAILABLE:
        return None
    try:
        cod = None
        yx = None
        if s3_df is not None and not s3_df.empty:
            year0 = s3_df[s3_df["Year_Index"] == 0]
            if not year0.empty:
                cod = float(year0["POI_Usable_Energy_MWh"].iloc[0])
            g_row = s3_df[s3_df["Year_Index"] == int(guarantee_year)]
            if not g_row.empty:
                yx = float(g_row["POI_Usable_Energy_MWh"].iloc[0])

        labels = ["BOL", "COD", f"Y{int(guarantee_year)}"]
        values = [
            float(bol_mwh) if bol_mwh is not None else 0.0,
            float(cod) if cod is not None else 0.0,
            float(yx) if yx is not None else 0.0,
        ]

        fig = plt.figure(figsize=(6.6, 3.0))
        ax = fig.add_subplot(111)
        ax.bar(labels, values, color="#5cc3e4")
        ax.set_title(title)
        ax.set_xlabel("Stage")
        ax.set_ylabel("Energy (MWh)")
        ax.grid(True, axis="y", linestyle="--", alpha=0.35)

        buf = io.BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format="png", dpi=150)
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception:
        return None


def _format_or_tbd(value, unit: str) -> str:
    if value is None:
        return "TBD"
    try:
        numeric = float(value)
    except Exception:
        return str(value) if value else "TBD"
    if numeric <= 0:
        return "TBD"
    return format_value(numeric, unit)


def _format_transformer_rating(value) -> str:
    if value is None:
        return "TBD"
    try:
        kva = float(value)
    except Exception:
        return "TBD"
    if kva <= 0:
        return "TBD"
    mva = kva / 1000.0
    return f"{mva:.2f} MVA ({kva:.0f} kVA)"


def _svg_bytes_to_png(svg_bytes: bytes, width_px: int = 900) -> Optional[bytes]:
    if not svg_bytes or not CAIROSVG_AVAILABLE:
        return None
    try:
        return cairosvg.svg2png(bytestring=svg_bytes, output_width=width_px)
    except Exception:
        return None


def export_report_v2_1(ctx: ReportContext) -> bytes:
    doc = Document()
    _setup_margins(doc)
    _setup_header(doc, title="Confidential Sizing Report (V2.1 Beta)")

    _add_cover_page(
        doc,
        "CALB Utility-Scale ESS Sizing Report (V2.1 Beta)",
        ctx.project_name,
        {"tool_version": "V2.1 Beta"},
    )

    doc.add_heading("Conventions & Units", level=2)
    doc.add_paragraph(
        "All efficiencies, losses, DoD, and RTE values are displayed as percentages. "
        "Fractions (0-1) appear only inside formula parentheses."
    )
    doc.add_paragraph("")

    doc.add_heading("Executive Summary", level=2)
    exec_rows = [
        ("POI Power Requirement (MW)", format_value(ctx.poi_power_requirement_mw, "MW")),
        ("POI Energy Requirement (MWh)", format_value(ctx.poi_energy_requirement_mwh, "MWh")),
        ("POI Energy Guarantee (MWh)", format_value(ctx.poi_energy_guarantee_mwh, "MWh")),
        ("Guarantee Year (from COD)", f"{ctx.poi_guarantee_year:d}"),
        ("POI Usable @ Guarantee Year (MWh)", format_value(ctx.poi_usable_energy_mwh_at_guarantee_year, "MWh")),
        ("DC Blocks Total", f"{ctx.dc_blocks_total:d}"),
        ("DC Nameplate @BOL (MWh)", format_value(ctx.dc_total_energy_mwh, "MWh")),
        ("DC Oversize Margin (MWh)", format_value(ctx.stage2.get("oversize_mwh"), "MWh")),
        ("AC Block Template", ctx.ac_block_template_id),
        ("AC Blocks Total", f"{ctx.ac_blocks_total:d}"),
        ("Total PCS Modules", f"{ctx.pcs_modules_total:d}"),
        (
            "Transformer Rating (MVA/kVA)",
            _format_transformer_rating(ctx.transformer_rating_kva),
        ),
        ("Avg DC Blocks per AC Block", f"{ctx.avg_dc_blocks_per_ac_block:.3f}" if ctx.avg_dc_blocks_per_ac_block is not None else ""),
    ]
    _add_table(doc, exec_rows, ["Metric", "Value"])

    if ctx.dc_blocks_allocation:
        doc.add_paragraph("")
        doc.add_paragraph("DC Blocks per AC Block Allocation:")
        alloc_rows = [
            (entry.get("dc_blocks_per_ac_block"), entry.get("ac_blocks_count"))
            for entry in ctx.dc_blocks_allocation
        ]
        _add_table(doc, alloc_rows, ["DC Blocks per AC Block", "Number of AC Blocks"])
    doc.add_paragraph("")

    doc.add_heading("Inputs & Assumptions", level=2)
    doc.add_heading("Site / POI", level=3)
    site_rows = [
        ("POI Power Requirement (MW)", format_value(ctx.poi_power_requirement_mw, "MW")),
        ("POI Energy Requirement (MWh)", format_value(ctx.poi_energy_requirement_mwh, "MWh")),
        ("POI Energy Guarantee (MWh)", format_value(ctx.poi_energy_guarantee_mwh, "MWh")),
        ("POI MV Voltage (kV)", format_value(ctx.grid_mv_voltage_kv_ac, "kV")),
        ("POI Frequency (Hz)", _format_or_tbd(ctx.project_inputs.get("poi_frequency_hz"), "Hz")),
        ("Grid Power Factor (PF)", format_value(ctx.grid_power_factor, "PF")),
    ]
    _add_table(doc, site_rows, ["Parameter", "Value"])

    doc.add_heading("Battery & Degradation", level=3)
    battery_rows = [
        ("DoD", format_percent(ctx.stage1.get("dod_frac"), input_is_fraction=True)),
        ("SC Loss", format_percent(ctx.stage1.get("sc_loss_frac"), input_is_fraction=True)),
        ("Cycles per Year", f"{ctx.cycles_per_year:d}"),
        ("Project Life (years)", f"{ctx.project_life_years:d}"),
    ]
    _add_table(doc, battery_rows, ["Parameter", "Value"])

    doc.add_heading("Efficiency Chain (one-way)", level=3)
    eff_rows = [
        ("Total Efficiency (one-way)", format_percent(ctx.efficiency_chain_oneway_frac, input_is_fraction=True)),
        ("DC Cables", format_percent(ctx.efficiency_components_frac.get("eff_dc_cables_frac"), input_is_fraction=True)),
        ("PCS", format_percent(ctx.efficiency_components_frac.get("eff_pcs_frac"), input_is_fraction=True)),
        ("Transformer", format_percent(ctx.efficiency_components_frac.get("eff_mvt_frac"), input_is_fraction=True)),
        ("RMU / Switchgear / AC Cables", format_percent(ctx.efficiency_components_frac.get("eff_ac_cables_sw_rmu_frac"), input_is_fraction=True)),
        ("HVT / Others", format_percent(ctx.efficiency_components_frac.get("eff_hvt_others_frac"), input_is_fraction=True)),
    ]
    _add_table(doc, eff_rows, ["Component", "Value"])
    doc.add_paragraph("")

    doc.add_heading("Stage 1: Energy Requirement", level=2)
    doc.add_paragraph(
        "DC energy capacity required (MWh) = POI energy requirement / "
        "((1 - SC loss) * DoD * sqrt(DC RTE) * eta_chain_oneway)."
    )
    doc.add_paragraph(
        f"eta_chain_oneway = {_format_percent_with_fraction(ctx.efficiency_chain_oneway_frac, input_is_fraction=True)}"
    )
    doc.add_paragraph(
        f"SC loss = {_format_percent_with_fraction(ctx.stage1.get('sc_loss_frac'), input_is_fraction=True)}; "
        f"DoD = {_format_percent_with_fraction(ctx.stage1.get('dod_frac'), input_is_fraction=True)}; "
        f"DC RTE = {_format_percent_with_fraction(ctx.stage1.get('dc_round_trip_efficiency_frac'), input_is_fraction=True)}"
    )
    s1_rows = [
        ("DC Energy Capacity Required (MWh)", format_value(ctx.stage1.get("dc_energy_capacity_required_mwh"), "MWh")),
        ("DC Power Required (MW)", format_value(ctx.stage1.get("dc_power_required_mw"), "MW")),
    ]
    _add_table(doc, s1_rows, ["Metric", "Value"])
    doc.add_paragraph("")

    doc.add_heading("Stage 2: DC Configuration", level=2)
    dc_table = ctx.stage2.get("block_config_table") if isinstance(ctx.stage2, dict) else None
    if dc_table is not None and not dc_table.empty:
        drop_cols = {"Config Adjustment (%)", "Oversize (MWh)", "Busbars Needed (K=10)", "Busbars Needed"}
        dc_columns = [c for c in dc_table.columns if c not in drop_cols]
        headers_map = {c: c for c in dc_columns}
        formatters = {}
        for col in dc_columns:
            if col in ("Unit Capacity (MWh)", "Subtotal (MWh)", "Total DC Nameplate @BOL (MWh)"):
                formatters[col] = lambda v: format_value(v, "MWh")
            else:
                formatters[col] = lambda v: "" if v is None else str(v)
        _add_dataframe_table(doc, dc_table, dc_columns, headers_map, formatters)
    else:
        doc.add_paragraph("DC block configuration table unavailable.")
    doc.add_paragraph(
        f"DC total nameplate @BOL (MWh): {format_value(ctx.dc_total_energy_mwh, 'MWh')}; "
        f"Oversize margin (MWh): {format_value(ctx.stage2.get('oversize_mwh'), 'MWh')}."
    )
    doc.add_paragraph("")

    doc.add_heading("Stage 3: Degradation & Deliverable at POI", level=2)
    s3_df = ctx.stage3_df
    if s3_df is not None and not s3_df.empty:
        doc.add_paragraph("System RTE = DC RTE * (eta_chain_oneway)^2.")
        rte_dc = s3_df["DC_RTE_Pct"].astype(float)
        rte_sys = s3_df["System_RTE_Pct"].astype(float)
        rte_dc_min, rte_dc_max = float(rte_dc.min()), float(rte_dc.max())
        rte_sys_min, rte_sys_max = float(rte_sys.min()), float(rte_sys.max())

        if abs(rte_dc_min - rte_dc_max) < 1e-6:
            doc.add_paragraph(f"DC RTE: {format_percent(rte_dc_min, input_is_fraction=False)}")
        else:
            doc.add_paragraph(
                f"DC RTE varies by year: {format_percent(rte_dc_min, input_is_fraction=False)} to "
                f"{format_percent(rte_dc_max, input_is_fraction=False)}"
            )
        if abs(rte_sys_min - rte_sys_max) < 1e-6:
            doc.add_paragraph(f"System RTE: {format_percent(rte_sys_min, input_is_fraction=False)}")
        else:
            doc.add_paragraph(
                f"System RTE varies by year: {format_percent(rte_sys_min, input_is_fraction=False)} to "
                f"{format_percent(rte_sys_max, input_is_fraction=False)}"
            )

        s3_df = s3_df.copy()
        s3_df["Meets_Guarantee"] = s3_df["POI_Usable_Energy_MWh"] >= float(ctx.poi_energy_guarantee_mwh or 0.0)
        doc.add_paragraph(
            f"Guarantee Year = {ctx.poi_guarantee_year}; pass/fail is evaluated at year {ctx.poi_guarantee_year}."
        )

        try:
            available_years = set(s3_df["Year_Index"].astype(int).tolist())
        except Exception:
            available_years = set()
        
        # Keep full data for chart (all years)
        s3_df_full = s3_df.copy()
        
        # Filter to key years for table display only
        key_years = sorted(set([0, ctx.poi_guarantee_year, 5, 10, 15, 20]))
        selected_years = [year for year in key_years if year in available_years]
        if selected_years:
            s3_df = s3_df[s3_df["Year_Index"].isin(selected_years)].copy()

        s3_columns = [
            "Year_Index",
            "SOH_Absolute_Pct",
            "DC_Usable_MWh",
            "POI_Usable_Energy_MWh",
            "Meets_Guarantee",
        ]
        headers_map = {
            "Year_Index": "Year",
            "SOH_Absolute_Pct": "SOH (%)",
            "DC_Usable_MWh": "DC Usable (MWh)",
            "POI_Usable_Energy_MWh": "POI Usable (MWh)",
            "Meets_Guarantee": "Meets POI Guarantee",
        }
        formatters = {
            "Year_Index": lambda v: f"{int(v)}",
            "SOH_Absolute_Pct": lambda v: format_percent(v, input_is_fraction=False),
            "DC_Usable_MWh": lambda v: format_value(v, "MWh"),
            "POI_Usable_Energy_MWh": lambda v: format_value(v, "MWh"),
            "Meets_Guarantee": lambda v: "Yes" if bool(v) else "No",
        }
        _add_dataframe_table(doc, s3_df, s3_columns, headers_map, formatters)

        cap_chart = _plot_dc_capacity_bar_png(
            bol_mwh=ctx.dc_total_energy_mwh,
            s3_df=s3_df,
            guarantee_year=ctx.poi_guarantee_year,
            title="DC Block Energy (BOL/COD/Yx at POI)",
        )
        if cap_chart is not None and cap_chart.getbuffer().nbytes > 0:
            doc.add_paragraph("")
            doc.add_picture(cap_chart, width=Inches(6.7))

        chart = _plot_poi_usable_png(
            s3_df_full,
            poi_target=ctx.poi_energy_guarantee_mwh,
            title="POI Usable Energy vs Year",
        )
        if chart is not None and chart.getbuffer().nbytes > 0:
            doc.add_paragraph("")
            doc.add_picture(chart, width=Inches(6.7))
        else:
            # Show diagnostic if recompute failed
            err = None
            try:
                err = ctx.stage3_meta.get("error") if isinstance(ctx.stage3_meta, dict) else None
            except Exception:
                err = None
            if err:
                doc.add_paragraph(f"Stage 3 data unavailable: {err}")
            else:
                doc.add_paragraph("Stage 3 data unavailable.")
        doc.add_paragraph("")

    doc.add_heading("Stage 4: AC Block Sizing", level=2)
    transformer_mva = None
    if ctx.grid_power_factor and ctx.grid_power_factor > 0 and ctx.ac_block_size_mw:
        transformer_mva = ctx.ac_block_size_mw / ctx.grid_power_factor
    transformer_formula = "n/a"
    if transformer_mva is not None and ctx.ac_block_size_mw and ctx.grid_power_factor:
        transformer_formula = (
            f"{format_value(ctx.ac_block_size_mw, 'MW')} / {format_value(ctx.grid_power_factor, 'PF')} = "
            f"{format_value(transformer_mva, 'MVA')}"
        )
    pcs_count_by_block = ctx.ac_output.get("pcs_count_by_block") if isinstance(ctx.ac_output, dict) else None
    pcs_by_block_text = ""
    if isinstance(pcs_count_by_block, list) and pcs_count_by_block:
        pcs_by_block_text = ", ".join(
            f"B{idx + 1}={int(value)}" for idx, value in enumerate(pcs_count_by_block)
        )
    s4_rows = [
        ("AC Block Template", ctx.ac_block_template_id),
        ("AC Block Size (MW)", format_value(ctx.ac_block_size_mw, "MW")),
        ("PCS per AC Block", f"{ctx.pcs_per_block:d}"),
        ("Feeders per AC Block", f"{ctx.feeders_per_block:d}"),
        ("PCS LV Voltage (V_LL)", format_value(ctx.pcs_lv_voltage_v_ll_rms_ac, "V")),
        ("Total PCS Modules", f"{ctx.pcs_modules_total:d}"),
        ("Transformer Rating (kVA)", format_value(ctx.transformer_rating_kva, "kVA")),
        ("Transformer Formula (MVA)", transformer_formula),
    ]
    if pcs_by_block_text:
        s4_rows.insert(3, ("PCS per AC Block (by block)", pcs_by_block_text))
    _add_table(doc, s4_rows, ["Metric", "Value"])
    doc.add_paragraph("")

    doc.add_heading("Integrated Configuration Summary", level=2)
    combined_rows = [
        ("DC Blocks Total", f"{ctx.dc_blocks_total:d}", ""),
        ("AC Blocks Total", "", f"{ctx.ac_blocks_total:d}"),
        ("Total PCS Modules", "", f"{ctx.pcs_modules_total:d}"),
        ("Transformer Rating (MVA/kVA)", "", _format_transformer_rating(ctx.transformer_rating_kva)),
        ("Grid MV Voltage (kV)", "", format_value(ctx.grid_mv_voltage_kv_ac, "kV")),
        ("Guarantee Year (from COD)", f"{ctx.poi_guarantee_year:d}", ""),
    ]
    _add_table(doc, combined_rows, ["Metric", "DC", "AC"])
    doc.add_paragraph("")

    figure_index = 1

    doc.add_heading("Single Line Diagram (1 AC Block group)", level=2)
    doc.add_paragraph("SLD output represents a single MV node chain (RMU -> TR -> 1 AC block group).")
    if ctx.sld_snapshot_hash:
        generated_at = ctx.sld_generated_at or "unknown time"
        doc.add_paragraph(
            f"SLD snapshot hash: {ctx.sld_snapshot_hash} (generated at {generated_at})."
        )
        if ctx.sld_group_index:
            doc.add_paragraph(f"SLD preview group index: {ctx.sld_group_index}.")
    sld_embedded = False
    if ctx.sld_pro_png_bytes:
        doc.add_picture(io.BytesIO(ctx.sld_pro_png_bytes), width=Inches(6.7))
        doc.add_paragraph(f"Figure {figure_index} - Single Line Diagram (auto-generated)")
        figure_index += 1
        sld_embedded = True
    elif ctx.sld_preview_svg_bytes:
        png_bytes = _svg_bytes_to_png(ctx.sld_preview_svg_bytes)
        if png_bytes:
            doc.add_picture(io.BytesIO(png_bytes), width=Inches(6.7))
            doc.add_paragraph(f"Figure {figure_index} - Single Line Diagram (auto-generated)")
            figure_index += 1
            sld_embedded = True

    if not sld_embedded:
        doc.add_paragraph("SLD not generated. Please generate in Single Line Diagram page.")
    doc.add_paragraph("")

    doc.add_heading("Block Layout (template view)", level=2)
    if ctx.layout_png_bytes:
        doc.add_picture(io.BytesIO(ctx.layout_png_bytes), width=Inches(6.7))
        doc.add_paragraph(f"Figure {figure_index} - Block Layout (auto-generated)")
        figure_index += 1
    else:
        doc.add_paragraph("Layout not generated. Please generate in Site Layout page.")
    doc.add_paragraph("")

    qc_checks = list(ctx.qc_checks)
    percent_pairs = [
        (ctx.efficiency_chain_oneway_frac, format_percent(ctx.efficiency_chain_oneway_frac, input_is_fraction=True)),
        (ctx.stage1.get("dod_frac"), format_percent(ctx.stage1.get("dod_frac"), input_is_fraction=True)),
        (ctx.stage1.get("sc_loss_frac"), format_percent(ctx.stage1.get("sc_loss_frac"), input_is_fraction=True)),
        (
            ctx.stage1.get("dc_round_trip_efficiency_frac"),
            format_percent(ctx.stage1.get("dc_round_trip_efficiency_frac"), input_is_fraction=True),
        ),
    ]
    for raw_value, text in percent_pairs:
        if raw_value is None:
            continue
        try:
            raw_value = float(raw_value)
            displayed = float(text.replace("%", ""))
        except Exception:
            continue
        if raw_value > 0.1 and displayed < 1.0:
            qc_checks.append("Percent formatting appears to show a fraction (0.xxx%) instead of a percent.")
            break

    doc.add_heading("QC / Warnings", level=2)
    if qc_checks:
        for item in qc_checks:
            doc.add_paragraph(f"- {item}")
    else:
        doc.add_paragraph("No QC warnings.")

    return _doc_to_bytes(doc)


export_report_v2 = export_report_v2_1
