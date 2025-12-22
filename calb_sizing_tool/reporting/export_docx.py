import os
from io import BytesIO
import pandas as pd
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from calb_sizing_tool.config import PROJECT_ROOT
from calb_sizing_tool.models import ProjectSizingResult

def _setup_page_header(doc):
    """设置符合 CALB 标准的页眉 (Logo + 保密声明)"""
    section = doc.sections[0]
    header = section.header
    header.is_linked_to_previous = False
    
    # 创建 1行2列 的表格用于布局
    table = header.add_table(rows=1, cols=2, width=Inches(6.5))
    table.autofit = False
    table.columns[0].width = Inches(2.0) # Logo 区域
    table.columns[1].width = Inches(4.5) # 文字区域
    
    # 插入 Logo
    logo_path = PROJECT_ROOT / "calb_logo.png"
    cell_logo = table.cell(0, 0)
    if logo_path.exists():
        paragraph = cell_logo.paragraphs[0]
        paragraph.add_run().add_picture(str(logo_path), width=Inches(1.2))
    else:
        cell_logo.text = "[CALB Logo]"

    # 插入右对齐文本
    cell_text = table.cell(0, 1)
    paragraph = cell_text.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run("CALB Group Co., Ltd.\nUtility-Scale ESS Technical Proposal\nConfidential")
    run.font.name = "Arial"
    run.font.size = Pt(9)
    run.font.bold = True

def _add_table_style(table):
    """应用统一的表格样式"""
    table.style = 'Table Grid'
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(10)
                    run.font.name = 'Arial'

def create_combined_report(data: ProjectSizingResult, report_type="combined", extra_context=None) -> BytesIO:
    """
    生成完整的技术方案报告
    :param data: ProjectSizingResult 对象
    :param report_type: 'combined', 'ac', 'dc'
    :param extra_context: 字典，包含 'degradation_table' (DataFrame) 等额外数据
    """
    if extra_context is None:
        extra_context = {}

    doc = Document()
    _setup_page_header(doc)

    # --- 标题 ---
    title = doc.add_heading(f"ESS Technical Proposal: {data.project_name}", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    doc.add_paragraph("\n")
    
    # --- 1. Executive Summary ---
    doc.add_heading('1. Executive Summary', level=1)
    p = doc.add_paragraph()
    p.add_run(f"Total System Power: ").bold = True
    p.add_run(f"{data.system_power_mw:.2f} MW\n")
    p.add_run(f"Total System Capacity (BOL): ").bold = True
    p.add_run(f"{data.system_capacity_mwh:.2f} MWh\n")
    
    # 统计 AC/DC 数量
    total_ac_blocks = len(data.ac_blocks)
    total_dc_containers = data.total_dc_blocks
    
    p.add_run(f"System Configuration: ").bold = True
    p.add_run(f"{total_ac_blocks} x AC Blocks + {total_dc_containers} x Battery Containers.")

    # --- 2. DC Subsystem Configuration ---
    if report_type in ["dc", "combined"]:
        doc.add_heading('2. DC Subsystem Configuration', level=1)
        
        # 2.1 DC Equipment Parameters
        doc.add_heading('2.1 DC Equipment Specification', level=2)
        if data.ac_blocks and data.ac_blocks[0].dc_blocks_connected:
            dc_sample = data.ac_blocks[0].dc_blocks_connected[0]
            
            table = doc.add_table(rows=1, cols=2)
            _add_table_style(table)
            
            specs = [
                ("Battery Container Model", dc_sample.container_model),
                ("Cell Technology", "CALB 314Ah LiFePO4"),
                ("System Voltage", f"{dc_sample.voltage_v:.0f} V"),
                ("Racks per Container", str(dc_sample.racks_per_container)),
                ("Unit Capacity (BOL)", f"{dc_sample.capacity_mwh:.4f} MWh"),
                ("Total Quantity", f"{total_dc_containers} Units"),
                ("Total DC Capacity", f"{data.system_capacity_mwh:.2f} MWh")
            ]
            
            for k, v in specs:
                row = table.add_row().cells
                row[0].text = k
                row[1].text = v
        
        # 2.2 Capacity Degradation (Annual Data)
        doc.add_paragraph("\n")
        doc.add_heading('2.2 Estimated Capacity Degradation', level=2)
        
        deg_df = extra_context.get("degradation_table")
        if isinstance(deg_df, pd.DataFrame) and not deg_df.empty:
            # 只取关键列，防止表格过宽
            cols_to_keep = ["Year", "SOH_Display_Pct", "POI_Usable_Energy_MWh"]
            # 尝试匹配列名（处理不同版本的列名差异）
            final_cols = []
            headers = []
            
            if "Year" in deg_df.columns: 
                final_cols.append("Year")
                headers.append("Year")
            elif "Year_Index" in deg_df.columns:
                final_cols.append("Year_Index")
                headers.append("Year")
                
            if "SOH_Display_Pct" in deg_df.columns:
                final_cols.append("SOH_Display_Pct")
                headers.append("SOH (%)")
                
            if "POI_Usable_Energy_MWh" in deg_df.columns:
                final_cols.append("POI_Usable_Energy_MWh")
                headers.append("Usable Energy (MWh)")
            
            if final_cols:
                # 创建表格
                rows_count = len(deg_df) + 1
                table = doc.add_table(rows=rows_count, cols=len(final_cols))
                _add_table_style(table)
                
                # 表头
                hdr_cells = table.rows[0].cells
                for i, h in enumerate(headers):
                    hdr_cells[i].text = h
                    hdr_cells[i].paragraphs[0].runs[0].font.bold = True
                
                # 数据填充
                for i, row in enumerate(deg_df[final_cols].itertuples(index=False)):
                    cells = table.rows[i+1].cells
                    for j, val in enumerate(row):
                        if isinstance(val, float):
                            cells[j].text = f"{val:.2f}"
                        else:
                            cells[j].text = str(val)
            else:
                doc.add_paragraph("(Data columns not matching template)")
        else:
            doc.add_paragraph("Degradation data not available in this context.")

    # --- 3. AC Subsystem Configuration ---
    if report_type in ["ac", "combined"]:
        header_title = '2. AC Subsystem Configuration' if report_type == "ac" else '3. AC Subsystem Configuration'
        doc.add_heading(header_title, level=1)
        
        if data.ac_blocks:
            ac_sample = data.ac_blocks[0]
            
            doc.add_heading('3.1 AC Block Specification', level=2)
            table = doc.add_table(rows=1, cols=2)
            _add_table_style(table)
            
            ac_specs = [
                ("Grid Voltage (MV)", f"{ac_sample.mv_voltage_kv} kV"),
                ("PCS Output Voltage (LV)", f"{ac_sample.lv_voltage_v} V"),
                ("Transformer Rating", f"{ac_sample.transformer_kva:.2f} kVA"),
                ("PCS Modules per Block", str(ac_sample.num_pcs)),
                ("PCS Module Power", f"{ac_sample.pcs_power_kw:.2f} kW"),
                ("AC Block Power Rating", f"{ac_sample.pcs_power_kw * ac_sample.num_pcs / 1000:.2f} MW"),
                ("Total AC Blocks", str(total_ac_blocks))
            ]
            
            for k, v in ac_specs:
                row = table.add_row().cells
                row[0].text = k
                row[1].text = v
                
            # 3.2 Topology Description
            doc.add_paragraph("\n")
            doc.add_heading('3.2 System Topology & Combination', level=2)
            
            dc_per_ac = 0
            if ac_sample.dc_blocks_connected:
                dc_per_ac = ac_sample.dc_blocks_connected[0].count
                
            topo_text = (
                f"The system consists of {total_ac_blocks} independent AC Blocks. "
                f"Each AC Block is connected to {dc_per_ac} Battery Container(s) via the DC Busbar. "
                f"The Power Conversion System (PCS) performs bi-directional DC/AC conversion, "
                f"and the MV Transformer steps up the voltage to {ac_sample.mv_voltage_kv} kV for grid interconnection."
            )
            doc.add_paragraph(topo_text)

    # --- 4. Technical Drawings ---
    if report_type == "combined":
        doc.add_page_break() # 【已修复】这里使用了正确的 add_page_break()
        
        doc.add_heading('4. Single Line Diagram (SLD)', level=1)
        doc.add_paragraph("[SLD Placeholder - Please insert the exported SLD image here]")
        # 预留大片空白
        doc.add_paragraph("\n" * 10)
        
        doc.add_page_break() # 【已修复】换页
        
        doc.add_heading('5. General Layout', level=1)
        doc.add_paragraph("[Layout Placeholder - Please insert the site layout drawing here]")

    # 保存
    f = BytesIO()
    doc.save(f)
    f.seek(0)
    return f