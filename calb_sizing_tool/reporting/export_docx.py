from docx import Document
from docx.shared import Inches, Pt, RGBColor
from io import BytesIO
from calb_sizing_tool.models import ProjectSizingResult

def create_combined_report(data: ProjectSizingResult, report_type="combined") -> BytesIO:
    """
    Generates DOCX report.
    report_type: 'dc', 'ac', or 'combined'
    """
    doc = Document()
    
    # Title Style
    try:
        style = doc.styles['Title']
        style.font.name = 'Arial'
        style.font.size = Pt(20)
        style.font.color.rgb = RGBColor(0x2E, 0x74, 0xB5)
    except:
        pass
    
    title_text = f"ESS Sizing Report: {data.project_name}"
    if report_type == "dc": title_text = "DC Sizing Technical Report"
    if report_type == "ac": title_text = "AC Sizing Technical Report"
    
    doc.add_heading(title_text, 0)
    
    # 1. Executive Summary
    doc.add_heading('1. System Overview', level=1)
    p = doc.add_paragraph()
    p.add_run(f"Total Power Capacity: ").bold = True
    p.add_run(f"{data.system_power_mw:.2f} MW\n")
    p.add_run(f"Total Energy Capacity: ").bold = True
    p.add_run(f"{data.system_capacity_mwh:.2f} MWh")

    # 2. DC Section
    if report_type in ["dc", "combined"]:
        doc.add_heading('2. DC Subsystem Configuration', level=1)
        if data.ac_blocks and data.ac_blocks[0].dc_blocks_connected:
            dc = data.ac_blocks[0].dc_blocks_connected[0] # Sample
            total_dc = data.total_dc_blocks
            
            table = doc.add_table(rows=1, cols=2)
            table.style = 'Table Grid'
            rows = [
                ("Battery Container Model", dc.container_model),
                ("System Voltage", f"{dc.voltage_v} V"),
                ("Racks per Container", str(dc.racks_per_container)),
                ("Total Container Count", str(total_dc)),
                ("Total DC Capacity (BOL)", f"{total_dc * dc.capacity_mwh:.2f} MWh")
            ]
            for k, v in rows:
                r = table.add_row().cells
                r[0].text, r[1].text = k, v
        else:
            doc.add_paragraph("No DC data available.")

    # 3. AC Section
    if report_type in ["ac", "combined"]:
        h_level = '2' if report_type == "ac" else '3'
        doc.add_heading(f'{h_level}. AC Subsystem Configuration', level=1)
        
        if data.ac_blocks:
            ac = data.ac_blocks[0] # Sample
            table = doc.add_table(rows=1, cols=2)
            table.style = 'Table Grid'
            rows = [
                ("Grid Voltage (MV)", f"{ac.mv_voltage_kv} kV"),
                ("Inverter Voltage (LV)", f"{ac.lv_voltage_v} V"),
                ("Transformer Rating", f"{ac.transformer_kva} kVA"),
                ("PCS Units per Block", str(ac.num_pcs)),
                ("PCS Unit Power", f"{ac.pcs_power_kw} kW"),
                ("Total AC Blocks", str(len(data.ac_blocks)))
            ]
            for k, v in rows:
                r = table.add_row().cells
                r[0].text, r[1].text = k, v
        else:
            doc.add_paragraph("No AC data available.")

    f = BytesIO()
    doc.save(f)
    f.seek(0)
    return f