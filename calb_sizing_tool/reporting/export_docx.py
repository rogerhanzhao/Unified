import io
import datetime
import pandas as pd
import matplotlib
matplotlib.use('Agg') # Non-interactive backend
import matplotlib.pyplot as plt
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from calb_sizing_tool.config import PROJECT_ROOT
from calb_sizing_tool.models import ProjectSizingResult

# --- Constants ---
CALB_BLUE = RGBColor(0x2E, 0x74, 0xB5)
FONT_HEAD = 'Arial'
FONT_BODY = 'Times New Roman'

# --- Chart Builder ---
class ChartBuilder:
    @staticmethod
    def create_dc_chart(df: pd.DataFrame, target_mwh: float):
        if df is None or df.empty: return None
        
        fig, ax = plt.subplots(figsize=(6.5, 3.2))
        col_yr = 'Year' if 'Year' in df.columns else 'Year_Index'
        col_egy = 'POI_Usable_Energy_MWh'
        
        data = df[df[col_yr] >= 0].copy()
        
        ax.bar(data[col_yr], data[col_egy], color='#5cc3e4', width=0.6, label='Usable Energy')
        ax.axhline(y=target_mwh, color='red', linestyle='--', label='Target')
        
        ax.set_ylim(bottom=0, top=max(data[col_egy].max(), target_mwh)*1.15)
        ax.set_ylabel('Energy (MWh)', fontsize=9)
        ax.set_title('DC Energy Profile', fontsize=10, weight='bold')
        ax.legend(fontsize=8)
        ax.grid(axis='y', linestyle=':', alpha=0.5)
        
        buf = io.BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format='png', dpi=150)
        plt.close(fig)
        buf.seek(0)
        return buf

    @staticmethod
    def create_ac_chart(ac_blocks: list):
        if not ac_blocks: return None
        fig, ax = plt.subplots(figsize=(6, 3))
        
        count = len(ac_blocks)
        sample = ac_blocks[0]
        total_p = count * (sample.pcs_power_kw * sample.num_pcs / 1000.0)
        
        ax.bar(['AC Blocks'], [count], color='#90EE90', width=0.4)
        ax.text(0, count, f"{count}", ha='center', va='bottom')
        
        ax2 = ax.twinx()
        ax2.bar(['Total MW'], [total_p], color='#87CEEB', width=0.4)
        ax2.text(1, total_p, f"{total_p:.2f}", ha='center', va='bottom')
        
        ax.set_title("AC System Summary")
        ax.set_ylim(bottom=0, top=count*1.3)
        ax2.set_ylim(bottom=0, top=total_p*1.3)
        
        buf = io.BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format='png', dpi=150)
        plt.close(fig)
        buf.seek(0)
        return buf

# --- Document Helpers ---
def _setup_doc(doc):
    style = doc.styles['Normal']
    style.font.name = FONT_BODY
    style.font.size = Pt(10)
    
    h1 = doc.styles['Heading 1']
    h1.font.name = FONT_HEAD
    h1.font.size = Pt(16)
    h1.font.color.rgb = CALB_BLUE
    h1.font.bold = True
    
    h2 = doc.styles['Heading 2']
    h2.font.name = FONT_HEAD
    h2.font.size = Pt(12)
    h2.font.color.rgb = RGBColor(60, 60, 60)
    h2.font.bold = True

def _setup_header(doc, title_suffix="Report"):
    """Adds standard header with Logo and Title Suffix."""
    section = doc.sections[0]
    header = section.header
    header.is_linked_to_previous = False
    
    t = header.add_table(1, 2, Inches(7))
    t.autofit = False
    t.columns[0].width = Inches(2)
    t.columns[1].width = Inches(5)
    
    # Logo
    logo = PROJECT_ROOT / "calb_logo.png"
    c0 = t.cell(0,0)
    if logo.exists():
        c0.paragraphs[0].add_run().add_picture(str(logo), width=Inches(1.2))
    else:
        c0.text = "CALB ESS"
        
    c1 = t.cell(0,1)
    p = c1.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = p.add_run(f"CALB Group Co., Ltd.\n{title_suffix}\nConfidential")
    r.font.size = Pt(8)
    r.font.color.rgb = RGBColor(128,128,128)

def _add_table(doc, data, headers=None, widths=None):
    rows = len(data) + (1 if headers else 0)
    cols = len(data[0]) if data else (len(headers) if headers else 0)
    
    tbl = doc.add_table(rows, cols)
    tbl.style = 'Table Grid'
    tbl.autofit = False
    
    if widths:
        for r in tbl.rows:
            for i, w in enumerate(widths):
                if i < len(r.cells): r.cells[i].width = Inches(w)
    
    ridx = 0
    if headers:
        for i, h in enumerate(headers):
            cell = tbl.cell(0, i)
            tcPr = cell._tc.get_or_add_tcPr()
            shd = OxmlElement('w:shd')
            shd.set(qn('w:fill'), 'E7E6E6')
            tcPr.append(shd)
            
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(str(h))
            r.bold = True
            r.font.name = FONT_HEAD
        ridx = 1
        
    for row in data:
        for i, val in enumerate(row):
            cell = tbl.cell(ridx, i)
            p = cell.paragraphs[0]
            p.text = str(val)
            if i == 0: p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            else: p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        ridx += 1
    return tbl

def make_report_filename(proj_name, suffix="Report"):
    safe = "".join(c if c.isalnum() else "_" for c in proj_name)
    return f"{safe}_{suffix}.docx"

# --- Section Builders (Modular) ---

def _write_cover(doc, data, title):
    doc.add_paragraph("\n"*5)
    t = doc.add_heading(title, 0)
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = doc.add_paragraph(f"\nProject: {data.project_name}\nDate: {datetime.datetime.now().strftime('%Y-%m-%d')}")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_page_break()

def _write_exec_summary(doc, data):
    doc.add_heading("1. Executive Summary", 1)
    mv = data.ac_blocks[0].mv_voltage_kv if data.ac_blocks else "-"
    
    bullets = [
        f"POI Power: {data.system_power_mw:.2f} MW",
        f"POI Energy: {data.system_capacity_mwh:.2f} MWh",
        f"DC System: {data.total_dc_blocks} Containers",
        f"AC System: {len(data.ac_blocks)} Blocks @ {mv} kV"
    ]
    for b in bullets:
        doc.add_paragraph(b, style='List Bullet')
    doc.add_paragraph("\n")

def _write_inputs(doc, inputs):
    doc.add_heading("Input Assumptions", 1)
    rows = []
    for k,v in inputs.items():
        val = f"{v:.4f}" if isinstance(v, float) else str(v)
        rows.append((k, val))
    _add_table(doc, rows, ["Parameter", "Value"], [3.5, 3.0])
    doc.add_paragraph("\n")

def _write_dc_body(doc, data, context):
    doc.add_heading("DC Sizing Results", 1)
    
    # 1. Specs
    doc.add_heading("DC Equipment Specification", 2)
    
    raw = context.get('dc_spec_raw', {})
    dc = None
    if data.ac_blocks and data.ac_blocks[0].dc_blocks_connected:
        dc = data.ac_blocks[0].dc_blocks_connected[0]
    
    if dc:
        # Prioritize Excel raw values for accuracy
        model = raw.get('Dc_Block_Name', dc.container_model)
        cell = raw.get('Cell_Type', 'LFP 314Ah')
        cfg = raw.get('Configuration', f"{dc.racks_per_container} Racks")
        
        # Fix: Unit Capacity 3 decimals
        u_cap = float(raw.get('Block_Nameplate_Capacity_Mwh', dc.capacity_mwh))
        
        # Fix: Voltage Range string
        v_nom = float(raw.get('System_Voltage_V', dc.voltage_v))
        v_range = raw.get('Voltage_Range_V', "1000~1500 V") # Fallback string
        
        specs = [
            ("Container Model", model),
            ("Cell Type", cell),
            ("Configuration", cfg),
            ("Unit Capacity (BOL)", f"{u_cap:.3f} MWh"),
            ("Nominal Voltage", f"{v_nom:.0f} V DC"),
            ("Operating Voltage Range", str(v_range)),
            ("Total Quantity", f"{data.total_dc_blocks}"),
            ("Total DC Energy", f"{(data.total_dc_blocks * u_cap):.3f} MWh")
        ]
        _add_table(doc, specs, ["Item", "Specification"], [3.0, 3.5])
    else:
        doc.add_paragraph("No DC data.")

    # 2. Chart
    doc.add_paragraph("\n")
    doc.add_heading("Lifetime Capacity", 2)
    deg_df = context.get('degradation_table')
    
    if deg_df is not None and not deg_df.empty:
        img = ChartBuilder.create_dc_chart(deg_df, data.system_capacity_mwh)
        if img: doc.add_picture(img, width=Inches(6))
    else:
        doc.add_paragraph("No simulation data available.")

def _write_ac_body(doc, data):
    doc.add_heading("AC Sizing Results", 1)
    if not data.ac_blocks:
        doc.add_paragraph("No AC data.")
        return
        
    ac = data.ac_blocks[0]
    total_pcs = len(data.ac_blocks) * ac.num_pcs
    
    specs = [
        ("AC Block Count", f"{len(data.ac_blocks)}"),
        ("Standard Block Size", f"{(ac.pcs_power_kw * ac.num_pcs / 1000):.3f} MW"),
        ("Total PCS Modules", f"{total_pcs}"),
        ("Transformer Rating", f"{ac.transformer_kva:.0f} kVA"),
        ("Voltage Levels", f"LV: {ac.lv_voltage_v} V / MV: {ac.mv_voltage_kv} kV")
    ]
    _add_table(doc, specs, ["Item", "Specification"], [3.0, 3.5])
    
    doc.add_paragraph("\n")
    img = ChartBuilder.create_ac_chart(data.ac_blocks)
    if img: doc.add_picture(img, width=Inches(5))

def _write_combined_summary(doc, data):
    doc.add_heading("Combined Configuration", 1)
    # Re-calc totals for safety
    dc_e = 0
    if data.ac_blocks and data.ac_blocks[0].dc_blocks_connected:
        dc_e = data.total_dc_blocks * data.ac_blocks[0].dc_blocks_connected[0].capacity_mwh
    
    ac_p = 0
    if data.ac_blocks:
        ac = data.ac_blocks[0]
        ac_p = len(data.ac_blocks) * (ac.pcs_power_kw * ac.num_pcs / 1000)
        
    rows = [
        ("Block Count", f"{data.total_dc_blocks} (DC)", f"{len(data.ac_blocks)} (AC)"),
        ("Total Capacity/Power", f"{dc_e:.3f} MWh", f"{ac_p:.3f} MW"),
        ("Voltages", "DC: 1000-1500 V", f"AC: {data.ac_blocks[0].mv_voltage_kv} kV")
    ]
    _add_table(doc, rows, ["Metric", "DC", "AC"], [2, 2.2, 2.2])

# --- Main Generators ---

def create_dc_report(data: ProjectSizingResult, context: dict) -> io.BytesIO:
    doc = Document()
    _setup_doc(doc)
    _setup_header(doc, "DC Technical Report")
    
    _write_cover(doc, data, "DC Sizing Technical Report")
    _write_exec_summary(doc, data)
    _write_inputs(doc, context.get('inputs', {}))
    _write_dc_body(doc, data, context)
    
    f = io.BytesIO()
    doc.save(f)
    f.seek(0)
    return f

def create_ac_report(data: ProjectSizingResult, context: dict) -> io.BytesIO:
    doc = Document()
    _setup_doc(doc)
    _setup_header(doc, "AC Technical Report")
    
    _write_cover(doc, data, "AC Sizing Technical Report")
    _write_exec_summary(doc, data)
    _write_inputs(doc, context.get('inputs', {}))
    _write_ac_body(doc, data)
    
    f = io.BytesIO()
    doc.save(f)
    f.seek(0)
    return f

def create_combined_report(data: ProjectSizingResult, context: dict) -> io.BytesIO:
    doc = Document()
    _setup_doc(doc)
    _setup_header(doc, "Combined Technical Report")
    
    _write_cover(doc, data, "ESS Combined Technical Proposal")
    _write_exec_summary(doc, data)
    _write_inputs(doc, context.get('inputs', {}))
    
    # Reuse identical sections
    _write_dc_body(doc, data, context)
    doc.add_page_break()
    _write_ac_body(doc, data)
    doc.add_page_break()
    _write_combined_summary(doc, data)
    
    f = io.BytesIO()
    doc.save(f)
    f.seek(0)
    return f