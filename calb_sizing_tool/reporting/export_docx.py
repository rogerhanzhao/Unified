import copy
import datetime
import io
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

from calb_sizing_tool.config import DC_DATA_PATH

# --- Document Helpers ---

def _find_logo_for_report():
    try:
        data_dir = Path(DC_DATA_PATH).parent
        for item in data_dir.iterdir():
            lower = item.name.lower()
            if lower.endswith((".png", ".jpg", ".jpeg")) and ("logo" in lower or "calb" in lower):
                return str(item)
    except Exception:
        return None
    return None


def _setup_margins(doc: Document):
    section = doc.sections[0]
    section.left_margin = Inches(0.8)
    section.right_margin = Inches(0.8)
    section.top_margin = Inches(0.8)
    section.bottom_margin = Inches(0.8)


def _setup_header(doc: Document, title: str):
    """Adds standard header with logo and report title."""
    section = doc.sections[0]
    header = section.header
    header.is_linked_to_previous = False
    header_table = header.add_table(rows=1, cols=2, width=Inches(6.9))
    hdr_cells = header_table.rows[0].cells

    logo_path = _find_logo_for_report()
    if logo_path:
        p_logo = hdr_cells[0].paragraphs[0]
        run_logo = p_logo.add_run()
        run_logo.add_picture(logo_path, width=Inches(1.2))

    p_info = hdr_cells[1].paragraphs[0]
    p_info.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run_info = p_info.add_run(
        "CALB Group Co., Ltd.\n"
        "Utility-Scale Energy Storage Systems\n"
        f"{title}"
    )
    run_info.font.size = Pt(9)
    run_info.font.bold = True


def _format_float(value, decimals):
    if value is None:
        return ""
    try:
        return f"{float(value):.{decimals}f}"
    except Exception:
        return str(value)


def _add_table(doc: Document, rows, headers):
    if not rows:
        doc.add_paragraph("No data available.")
        return

    tbl = doc.add_table(rows=1, cols=len(headers))
    tbl.style = "Table Grid"

    hdr = tbl.rows[0].cells
    for j, col in enumerate(headers):
        hdr[j].text = str(col)
    for cell in hdr:
        for para in cell.paragraphs:
            for run in para.runs:
                run.bold = True

    for row in rows:
        rc = tbl.add_row().cells
        for j, val in enumerate(row):
            rc[j].text = "" if val is None else str(val)


def make_report_filename(proj_name, suffix="Report"):
    safe = "".join(c if c.isalnum() else "_" for c in proj_name)
    return f"{safe}_{suffix}.docx"


# --- Dictionary Extraction ---

def _match_pack_from_block_name(packs: pd.DataFrame, block_name: str, block_code: str):
    if packs is None or packs.empty:
        return None

    candidates = packs.copy()
    if "Is_Active" in candidates.columns:
        active = candidates[candidates["Is_Active"] == 1]
        if not active.empty:
            candidates = active

    search = f"{block_name} {block_code}".lower()
    for _, row in candidates.iterrows():
        model = str(row.get("Pack_Model", "")).lower()
        if model and model in search:
            return row
        tail = model.split("calb_")[-1] if "calb_" in model else model
        if tail and tail in search:
            return row

    return candidates.iloc[0] if not candidates.empty else None


def _voltage_range_from_row(row: pd.Series):
    if row is None:
        return None

    min_col = None
    max_col = None
    for col in row.index:
        label = str(col).lower()
        if "voltage" in label and "min" in label:
            min_col = col
        if "voltage" in label and "max" in label:
            max_col = col

    if min_col and max_col:
        try:
            v_min = float(row[min_col])
            v_max = float(row[max_col])
            if v_min > 0 and v_max > 0:
                return f"{v_min:.0f}-{v_max:.0f} V DC"
        except Exception:
            return None

    return None


def extract_dc_equipment_spec(block_code=None, block_name=None, data_path=None):
    data_path = Path(data_path) if data_path else Path(DC_DATA_PATH)
    if not data_path.exists():
        raise FileNotFoundError(f"DC dictionary not found at {data_path}")

    xls = pd.ExcelFile(data_path)
    blocks = pd.read_excel(xls, "dc_block_template_314_data")
    racks = pd.read_excel(xls, "rack_type_314_data")
    packs = pd.read_excel(xls, "pack_type_314_data")
    cells = pd.read_excel(xls, "battery_cell_type_314_data")

    if "Is_Active" in blocks.columns:
        blocks = blocks[blocks["Is_Active"] == 1]

    match = pd.DataFrame()
    if block_code and "Dc_Block_Code" in blocks.columns:
        match = blocks[blocks["Dc_Block_Code"] == block_code]
    if match.empty and block_name and "Dc_Block_Name" in blocks.columns:
        match = blocks[blocks["Dc_Block_Name"] == block_name]
    if match.empty:
        default = blocks[blocks.get("Is_Default_Option", 0) == 1]
        if not default.empty:
            container = default[default["Block_Form"].astype(str).str.lower() == "container"]
            match = container if not container.empty else default
    if match.empty:
        match = blocks.head(1)
    if match.empty:
        return {
            "container_model": "",
            "cell_type": "",
            "configuration": "",
            "unit_capacity_mwh": None,
            "nominal_voltage_v": None,
            "voltage_range_v": None,
        }

    block_row = match.iloc[0]
    rack_row = None
    pack_row = None

    rack_type_id = block_row.get("Rack_Type_Id")
    if pd.notna(rack_type_id) and "Rack_Type_Id" in racks.columns:
        rack = racks[racks["Rack_Type_Id"] == rack_type_id]
        if not rack.empty:
            rack_row = rack.iloc[0]
            pack_type_id = rack_row.get("Pack_Type_Id")
            if pd.notna(pack_type_id) and "Pack_Type_Id" in packs.columns:
                pack = packs[packs["Pack_Type_Id"] == pack_type_id]
                if not pack.empty:
                    pack_row = pack.iloc[0]

    if pack_row is None:
        pack_row = _match_pack_from_block_name(
            packs,
            str(block_row.get("Dc_Block_Name", "")),
            str(block_row.get("Dc_Block_Code", "")),
        )

    cell_row = None
    if pack_row is not None and "Cell_Type_Id" in packs.columns:
        cell_type_id = pack_row.get("Cell_Type_Id")
        if pd.notna(cell_type_id) and "Cell_Type_Id" in cells.columns:
            cell = cells[cells["Cell_Type_Id"] == cell_type_id]
            if not cell.empty:
                cell_row = cell.iloc[0]

    container_model = str(block_row.get("Dc_Block_Name") or block_row.get("Dc_Block_Code") or "")
    cell_type = str(cell_row.get("Cell_Model")) if cell_row is not None else ""

    configuration = ""
    racks_per_block = block_row.get("Racks_Per_Block")
    packs_per_block = block_row.get("Packs_Per_Block")
    if pd.notna(racks_per_block):
        configuration = f"{int(racks_per_block)} Racks"
    elif pd.notna(packs_per_block):
        configuration = f"{int(packs_per_block)} Packs"

    unit_capacity_mwh = None
    if pd.notna(block_row.get("Block_Nameplate_Capacity_Mwh")):
        unit_capacity_mwh = float(block_row.get("Block_Nameplate_Capacity_Mwh"))

    nominal_voltage_v = None
    pack_nominal = None
    if pack_row is not None and pd.notna(pack_row.get("Pack_Nominal_Voltage_V")):
        pack_nominal = float(pack_row.get("Pack_Nominal_Voltage_V"))

    if pack_nominal is not None:
        packs_per_rack = rack_row.get("Packs_Per_Rack") if rack_row is not None else None
        if pd.notna(packs_per_rack):
            nominal_voltage_v = pack_nominal * float(packs_per_rack)
        elif pd.notna(packs_per_block):
            nominal_voltage_v = pack_nominal * float(packs_per_block)
        else:
            nominal_voltage_v = pack_nominal

    voltage_range = _voltage_range_from_row(block_row)
    if voltage_range is None and pack_row is not None:
        voltage_range = _voltage_range_from_row(pack_row)

    return {
        "container_model": container_model,
        "cell_type": cell_type,
        "configuration": configuration,
        "unit_capacity_mwh": unit_capacity_mwh,
        "nominal_voltage_v": nominal_voltage_v,
        "voltage_range_v": voltage_range,
        "block_code": str(block_row.get("Dc_Block_Code", "")),
    }


# --- AC Report Builders ---

def _write_report_title(doc: Document, title: str, project_name: str, poi_power, poi_energy):
    doc.add_heading(title, level=1)
    doc.add_paragraph(f"Project: {project_name}")
    if poi_power is not None and poi_energy is not None:
        doc.add_paragraph(f"POI Requirement: {poi_power:.2f} MW / {poi_energy:.2f} MWh")
    elif poi_power is not None:
        doc.add_paragraph(f"POI Requirement: {poi_power:.2f} MW")
    doc.add_paragraph("")


def _write_exec_summary(doc: Document, ac_output: dict, heading: str):
    doc.add_heading(heading, level=2)

    poi_power = ac_output.get("poi_power_mw")
    poi_energy = ac_output.get("poi_energy_mwh")
    total_blocks = ac_output.get("num_blocks")
    total_pcs = ac_output.get("total_pcs")
    transformer_count = ac_output.get("transformer_count")
    mv_level = ac_output.get("mv_level_kv") or ac_output.get("grid_kv")

    p = doc.add_paragraph()
    if poi_power is not None:
        p.add_run(f"POI Power: {poi_power:.2f} MW\n")
    if poi_energy is not None:
        p.add_run(f"POI Energy: {poi_energy:.2f} MWh\n")
    if total_blocks is not None:
        p.add_run(f"Total AC Blocks: {int(total_blocks)}\n")
    if total_pcs is not None:
        p.add_run(f"Total PCS Modules: {int(total_pcs)}\n")
    if transformer_count is not None:
        p.add_run(f"Transformer Count: {int(transformer_count)}\n")
    if mv_level is not None:
        p.add_run(f"MV Level: {mv_level} kV")


def _build_ac_inputs_rows(ac_output: dict):
    rows = []
    rows.append(("Grid Voltage (kV)", _format_float(ac_output.get("grid_kv"), 1)))
    rows.append(("PCS AC Output Voltage (V_LL,rms)", _format_float(ac_output.get("inverter_lv_v"), 0)))
    rows.append(("Standard AC Block Size (MW)", _format_float(ac_output.get("block_size_mw"), 2)))
    return rows


def _build_ac_results_rows(ac_output: dict):
    rows = []
    rows.append(("AC Blocks", _format_float(ac_output.get("num_blocks"), 0)))
    rows.append(("Total AC Power (MW)", _format_float(ac_output.get("total_ac_mw"), 2)))
    rows.append(("Overhead Margin (MW)", _format_float(ac_output.get("overhead_mw"), 2)))
    rows.append(("Total PCS Modules", _format_float(ac_output.get("total_pcs"), 0)))
    rows.append(("Transformer Count", _format_float(ac_output.get("transformer_count"), 0)))
    dc_per_ac = ac_output.get("dc_blocks_per_ac")
    if dc_per_ac is not None:
        rows.append(("DC Blocks per AC Block", _format_float(dc_per_ac, 0)))
    return rows


def _build_ac_equipment_rows(ac_output: dict):
    rows = []
    rows.append(("Standard AC Block Size (MW)", _format_float(ac_output.get("block_size_mw"), 3)))
    rows.append(("PCS Rating (kW)", _format_float(ac_output.get("pcs_power_kw"), 0)))
    rows.append(("PCS per AC Block", _format_float(ac_output.get("pcs_per_block"), 0)))
    rows.append(("Transformer Rating (kVA)", _format_float(ac_output.get("transformer_kva"), 0)))
    rows.append(("MV Voltage Level (kV)", _format_float(ac_output.get("grid_kv"), 1)))
    rows.append(("LV Voltage Level (V)", _format_float(ac_output.get("inverter_lv_v"), 0)))
    return rows


def _write_ac_section(doc: Document, ac_output: dict, report_context: dict):
    _write_exec_summary(doc, ac_output, "1. Executive Summary")

    doc.add_heading("2. AC Sizing Inputs", level=2)
    input_rows = _build_ac_inputs_rows(ac_output)
    extra_inputs = report_context.get("inputs", {}) if report_context else {}
    for key, value in extra_inputs.items():
        if key not in {row[0] for row in input_rows}:
            input_rows.append((key, value))
    _add_table(doc, input_rows, ["Parameter", "Value"])
    doc.add_paragraph("")

    doc.add_heading("3. AC Sizing Results Summary", level=2)
    _add_table(doc, _build_ac_results_rows(ac_output), ["Metric", "Value"])
    doc.add_paragraph("")

    doc.add_heading("4. AC Equipment Specification", level=2)
    _add_table(doc, _build_ac_equipment_rows(ac_output), ["Item", "Specification"])


def _doc_to_bytes(doc: Document) -> bytes:
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


# --- DC Merge Helpers ---

def _replace_image_rel_ids(element, src_doc: Document, dest_doc: Document):
    for node in element.iter():
        embed = node.attrib.get(qn("r:embed"))
        if not embed:
            continue
        rel = src_doc.part.rels.get(embed)
        if rel is None or rel.reltype != RT.IMAGE:
            continue
        image_part = rel.target_part
        new_rid, _ = dest_doc.part.get_or_add_image(io.BytesIO(image_part.blob))
        node.attrib[qn("r:embed")] = new_rid


def _append_doc_body(dest_doc: Document, src_doc: Document):
    for element in src_doc.element.body:
        if element.tag == qn("w:sectPr"):
            continue
        new_element = copy.deepcopy(element)
        _replace_image_rel_ids(new_element, src_doc, dest_doc)
        dest_doc.element.body.append(new_element)


def _build_dc_report_doc(dc_output: dict):
    try:
        from calb_sizing_tool.ui import dc_view
    except Exception:
        return None

    stage1 = dc_output.get("stage1", {}) if dc_output else {}
    if not stage1:
        return None

    selected = dc_output.get("selected_scenario", stage1.get("selected_scenario", "container_only"))

    try:
        _, df_blocks, df_soh_profile, df_soh_curve, df_rte_profile, df_rte_curve = dc_view.load_data(DC_DATA_PATH)
        s2, s3_df, s3_meta, iter_count, poi_g, converged = dc_view.size_with_guarantee(
            stage1,
            selected,
            df_blocks,
            df_soh_profile,
            df_soh_curve,
            df_rte_profile,
            df_rte_curve,
            k_max=dc_view.K_MAX_FIXED,
        )
    except Exception:
        return None

    results = {
        selected: (s2, s3_df, s3_meta, iter_count, poi_g, converged)
    }
    report_order = [(selected, selected.replace("_", " ").title())]

    dc_bytes = dc_view.build_report_bytes(stage1, results, report_order)
    if not dc_bytes:
        return None
    return Document(dc_bytes)


# --- Public Report Generators ---

def create_ac_report(ac_output: dict, report_context: dict) -> bytes:
    doc = Document()
    _setup_margins(doc)
    _setup_header(doc, "Confidential AC Sizing Report")

    project_name = ac_output.get("project_name") or (report_context or {}).get("project_name") or "CALB ESS Project"
    _write_report_title(
        doc,
        "CALB Utility-Scale ESS AC Sizing Report",
        project_name,
        ac_output.get("poi_power_mw"),
        ac_output.get("poi_energy_mwh"),
    )

    _write_ac_section(doc, ac_output, report_context or {})

    return _doc_to_bytes(doc)


def create_combined_report(dc_output: dict, ac_output: dict, report_context: dict) -> bytes:
    doc = Document()
    _setup_margins(doc)
    _setup_header(doc, "Confidential Combined Sizing Report")

    project_name = ac_output.get("project_name") or (report_context or {}).get("project_name") or "CALB ESS Project"

    title = doc.add_heading("CALB Utility-Scale ESS Combined Sizing Report", level=1)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = doc.add_paragraph(
        f"Project: {project_name}\nDate: {datetime.datetime.now().strftime('%Y-%m-%d')}"
    )
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_page_break()

    _write_exec_summary(doc, ac_output, "1. Executive Summary")
    doc.add_paragraph("")

    doc.add_heading("2. Inputs", level=2)
    inputs = (report_context or {}).get("inputs", {})
    input_rows = [(k, v) for k, v in inputs.items()]
    _add_table(doc, input_rows, ["Parameter", "Value"])
    doc.add_page_break()

    dc_doc = _build_dc_report_doc(dc_output or {})
    if dc_doc is not None:
        _append_doc_body(doc, dc_doc)
    else:
        doc.add_heading("DC Sizing Results", level=2)
        doc.add_paragraph("DC report section unavailable.")

    doc.add_page_break()
    _write_ac_section(doc, ac_output, report_context or {})
    doc.add_page_break()

    doc.add_heading("5. Combined Configuration", level=2)
    dc_spec = extract_dc_equipment_spec(
        block_code=dc_output.get("block_code") if dc_output else None,
        block_name=dc_output.get("block_name") if dc_output else None,
    )

    dc_total_qty = dc_output.get("dc_block_total_qty") if dc_output else None
    if dc_total_qty is None:
        dc_total_qty = dc_output.get("container_count") if dc_output else None
    dc_total_qty = int(dc_total_qty) if dc_total_qty is not None else None

    dc_unit = dc_spec.get("unit_capacity_mwh")
    dc_total_energy = None
    if dc_total_qty is not None and dc_unit is not None:
        dc_total_energy = dc_total_qty * dc_unit

    dc_voltage = dc_spec.get("voltage_range_v")
    if not dc_voltage and dc_spec.get("nominal_voltage_v") is not None:
        dc_voltage = f"{dc_spec.get('nominal_voltage_v'):.0f} V DC"

    rows = [
        ("DC Container Model", dc_spec.get("container_model", ""), ""),
        ("DC Configuration", dc_spec.get("configuration", ""), ""),
        ("DC Unit Capacity (MWh)", _format_float(dc_unit, 3), ""),
        ("DC Total Quantity", dc_total_qty if dc_total_qty is not None else "", ""),
        ("DC Total Energy (MWh)", _format_float(dc_total_energy, 3), ""),
        ("DC Voltage", dc_voltage or "", ""),
        ("AC Block Size (MW)", "", _format_float(ac_output.get("block_size_mw"), 3)),
        ("AC Blocks", "", _format_float(ac_output.get("num_blocks"), 0)),
        ("Total AC Power (MW)", "", _format_float(ac_output.get("total_ac_mw"), 2)),
        ("Total PCS Modules", "", _format_float(ac_output.get("total_pcs"), 0)),
        ("Transformer Rating (kVA)", "", _format_float(ac_output.get("transformer_kva"), 0)),
        ("MV Level (kV)", "", _format_float(ac_output.get("grid_kv"), 1)),
    ]
    _add_table(doc, rows, ["Metric", "DC", "AC"])

    doc.add_paragraph("")
    doc.add_heading("6. Single Line Diagram", level=2)
    doc.add_paragraph("SLD placeholder - to be provided.")

    return _doc_to_bytes(doc)
