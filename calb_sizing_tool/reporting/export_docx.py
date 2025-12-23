import io
import datetime
import pandas as pd
import matplotlib.pyplot as plt
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from calb_sizing_tool.config import PROJECT_ROOT
from calb_sizing_tool.models import ProjectSizingResult

# --- Style Constants ---
CALB_BLUE = RGBColor(0x2E, 0x74, 0xB5)
HEADER_GRAY = 'E7E6E6'
FONT_HEAD = 'Arial'
FONT_BODY = 'Times New Roman'

class ChartBuilder:
    """Generates engineering-grade charts for the report."""
    
    @staticmethod
    def create_dc_chart(df: pd.DataFrame, target_mwh: float):
        if df is None or df.empty: return None
        
        fig, ax = plt.subplots(figsize=(6.5, 3.2))
        
        # Determine columns
        col_yr = 'Year' if 'Year' in df.columns else 'Year_Index'
        col_egy = 'POI_Usable_Energy_MWh'
        
        # Filter negative years and data
        data = df[df[col_yr] >= 0].copy()
        
        # Plot
        ax.bar(data[col_yr], data[col_egy], color='#5cc3e4', width=0.6, label='Usable Energy', zorder=3)
        ax.axhline(y=target_mwh, color='red', linestyle='--', linewidth=1.5, label='Requirement', zorder=4)
        
        # Strict Engineering Axis
        ax.set_ylim(bottom=0, top=max(data[col_egy].max(), target_mwh) * 1.15)
        ax.set_xlim(left=-0.6, right=len(data)-0.4)
        ax.set_ylabel('Energy (MWh)', fontname=FONT_HEAD, fontsize=9)
        ax.set_title('DC Usable Energy Profile', fontname=FONT_HEAD, fontsize=10, weight='bold')
        
        ax.grid(axis='y', linestyle=':', alpha=0.5)
        ax.legend(loc='upper right', fontsize=8)
        plt.tight_layout()
        
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150)
        plt.close(fig)
        buf.seek(0)
        return buf

    @staticmethod
    def create_ac_chart(ac_blocks: list):
        if not ac_blocks: return None
        fig, ax = plt.subplots(figsize=(6, 3))
        
        count = len(ac_blocks)
        # Calculate totals
        total_mw = sum(b.pcs_power_kw * b.num_pcs / 1000.0 for b in ac_blocks)
        
        # Simple Visualization
        ax.bar(['AC Blocks'], [count], color='#90EE90', width=0.3)
        ax.text(0, count, f"{count}", ha='center', va='bottom')
        
        ax2 = ax.twinx()
        ax2.bar(['Total Power'], [total_mw], color='#87CEEB', width=0.3)
        ax2.text(1, total_mw, f"{total_mw:.2f} MW", ha='center', va='bottom')
        
        ax.set_ylabel('Quantity')
        ax2.set_ylabel('Power (MW)')
        ax.set_title('AC System Configuration')
        ax.set_ylim(bottom=0, top=count*1.3)
        ax2.set_ylim(bottom=0, top=total_mw*1.3)
        
        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150)
        plt.close(fig)
        buf.seek(0)
        return buf

def _setup_styles(doc):
    styles = doc.styles
    
    # Normal
    p = styles['Normal']
    p.font.name = FONT_BODY
    p.font.size = Pt(10.5)
    
    # Heading 1
    h1 = styles['Heading 1']
    h1.font.name = FONT_HEAD
    h1.font.size = Pt(16)
    h1.font.color.rgb = CALB_BLUE
    h1.font.bold = True
    h1.paragraph_format.space_before = Pt(18)
    
    # Heading 2
    h2 = styles['Heading 2']
    h2.font.name = FONT_HEAD
    h2.font.size = Pt(12)
    h2.font.color.rgb = RGBColor(60, 60, 60)
    h2.font.bold = True
    h2.paragraph_format.space_before = Pt(12)

def _setup_header(doc):
    section = doc.sections[0]
    header = section.header
    header.is_linked_to_previous = False
    
    tbl = header.add_table(rows=1, cols=2, width=Inches(7))
    tbl.autofit = False
    tbl.columns[0].width = Inches(2.5)
    tbl.columns[1].width = Inches(4.5)
    
    # Logo
    logo_file = PROJECT_ROOT / "calb_logo.png"
    if logo_file.exists():
        tbl.cell(0,0).paragraphs[0].add_run().add_picture(str(logo_file), width=Inches(1.2))
    else:
        tbl.cell(0,0).text = "CALB ESS"
        
    # Text
    p = tbl.cell(0,1).paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = p.add_run("CALB Group Co., Ltd.\nESS Combined Technical Report\nConfidential")
    r.font.name = FONT_HEAD
    r.font.size = Pt(8)
    r.font.color.rgb = RGBColor(128, 128, 128)

def _add_table(doc, data, headers=None, col_widths=None):
    """Robust table generator with gray header shading."""
    rows = len(data) + (1 if headers else 0)
    cols = len(data[0]) if data else (len(headers) if headers else 0)
    
    t = doc.add_table(rows=rows, cols=cols)
    t.style = 'Table Grid'
    t.autofit = False
    
    if col_widths:
        for r in t.rows:
            for i, w in enumerate(col_widths):
                if i < len(r.cells): r.cells[i].width = Inches(w)
                
    ridx = 0
    if headers:
        for i, h in enumerate(headers):
            cell = t.cell(0, i)
            # Shading
            tcPr = cell._tc.get_or_add_tcPr()
            shd = OxmlElement('w:shd')
            shd.set(qn('w:fill'), HEADER_GRAY)
            tcPr.append(shd)
            
            p = cell.paragraphs[0]
            r = p.add_run(str(h))
            r.bold = True
            r.font.name = FONT_HEAD
            r.font.size = Pt(10)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        ridx = 1
        
    for row_data in data:
        for i, val in enumerate(row_data):
            cell = t.cell(ridx, i)
            p = cell.paragraphs[0]
            p.text = str(val)
            p.runs[0].font.name = FONT_BODY
            p.runs[0].font.size = Pt(10)
            if i == 0: p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            else: p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        ridx += 1
    return t

def generate_combined_report(data: ProjectSizingResult, report_type="combined", extra_context=None) -> io.BytesIO:
    """
    Main entry point for report generation.
    Supports 'dc', 'ac', or 'combined'.
    """
    if extra_context is None: extra_context = {}
    
    # Unpack Context
    inputs = extra_context.get('inputs', {})
    deg_table = extra_context.get('degradation_table')
    # Raw dictionary row for exact specs
    dc_spec_raw = extra_context.get('dc_spec_raw', {}) 
    
    doc = Document()
    _setup_styles(doc)
    _setup_header(doc)
    
    # ================= A. COVER PAGE =================
    doc.add_paragraph("\n"*5)
    t = doc.add_heading("ESS Combined Technical Report", 0)
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    p = doc.add_paragraph(f"\nProject Name: {data.project_name}")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    p = doc.add_paragraph(f"Generated: {ts}\nVersion: 1.2-Auto")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    doc.add_paragraph("\n"*3)
    kpi_data = [
        ("Parameter", "Value"),
        ("POI Power", f"{data.system_power_mw:.2f} MW"),
        ("POI Capacity", f"{data.system_capacity_mwh:.2f} MWh"),
        ("DC Blocks", f"{data.total_dc_blocks}"),
        ("AC Blocks", f"{len(data.ac_blocks)}")
    ]
    _add_table(doc, kpi_data[1:], kpi_data[0], col_widths=[3,3])
    doc.add_page_break()
    
    # ================= B. EXECUTIVE SUMMARY =================
    doc.add_heading("1. Executive Summary", 1)
    
    # Logic for System Voltages
    dc_v = f"{dc_spec_raw.get('System_Voltage_V', 1200):.0f}" if dc_spec_raw else "1200"
    ac_mv = f"{data.ac_blocks[0].mv_voltage_kv}" if data.ac_blocks else "33"
    
    summary_bullets = [
        f"POI Power Capacity: {data.