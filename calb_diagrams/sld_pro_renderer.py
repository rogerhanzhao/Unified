import svgwrite
from svgwrite import cm, mm

def render_sld_pro_svg(snapshot: dict, output_path: str):
    """
    Renders the Single Line Diagram (SLD) using svgwrite.
    
    Args:
        snapshot (dict): The data snapshot containing all necessary parameters.
        output_path (str): The path to save the generated SVG file.
    """
    
    # Extract parameters from snapshot
    is_spec_object = hasattr(snapshot, "group_index") and hasattr(snapshot, "layout_params")
    
    if is_spec_object:
        # It's an SldGroupSpec object
        layout = snapshot.layout_params
        width = layout.get("svg_width", 1400)
        height = layout.get("svg_height", 900)
        
        project_name = getattr(snapshot, "project_name", "Project")
        
        mv_kv = snapshot.mv_voltage_kv
        transformer_mva = snapshot.transformer_mva
        lv_v = snapshot.lv_voltage_v_ll
        
        pcs_count = snapshot.pcs_count
        if pcs_count <= 0:
             pcs_count = 1
             
        dc_blocks_counts = snapshot.dc_blocks_per_feeder # List[int]
        
    else:
        # It's a dict
        inputs = snapshot.get("inputs", {})
        width = inputs.get("svg_width", 1400)
        height = inputs.get("svg_height", 900)
        project_name = snapshot.get("project_name", "Project")
        
        mv_kv = inputs.get('mv_nominal_kv_ac', 33)
        transformer_mva = inputs.get('transformer_rating_mva', 5)
        lv_v = inputs.get('pcs_lv_voltage_v_ll', 690)
        
        pcs_count = len(inputs.get("pcs_rating_kw_list", []))
        if pcs_count == 0:
            pcs_count = 1 
            
        dc_blocks_raw = inputs.get("dc_blocks_by_feeder", [])
        dc_blocks_counts = [d.get("dc_block_count", 0) for d in dc_blocks_raw]

    dwg = svgwrite.Drawing(str(output_path), size=(width, height))
    
    # Styles
    # Define some basic styles
    style_text = "font-family: Arial; font-size: 12px; fill: black;"
    style_title = "font-family: Arial; font-size: 16px; font-weight: bold; fill: black;"
    style_line = "stroke: black; stroke-width: 2; fill: none;"
    style_dashed = "stroke: black; stroke-width: 1; stroke-dasharray: 5,5; fill: none;"
    style_busbar = "stroke: black; stroke-width: 4; fill: none;"
    
    # Background
    dwg.add(dwg.rect(insert=(0, 0), size=('100%', '100%'), fill='white'))
    
    # Title
    dwg.add(dwg.text(f"Single Line Diagram - {project_name}", insert=(20, 30), style=style_title))
    
    # Main drawing area
    margin_x = 50
    margin_y = 60
    drawing_width = width - 2 * margin_x
    drawing_height = height - 2 * margin_y
    
    # Calculate positions
    # We assume one AC block group for now as per the view logic
    
    # Layout strategy:
    # Top: MV Grid / RMU
    # Middle: Transformer
    # Bottom: PCS and DC Blocks
    
    # Center X for the whole block
    center_x = width / 2
    
    # MV Busbar (Top)
    mv_y = margin_y + 50
    dwg.add(dwg.line(start=(margin_x, mv_y), end=(width - margin_x, mv_y), style=style_busbar))
    dwg.add(dwg.text(f"{mv_kv} kV Bus", insert=(margin_x, mv_y - 10), style=style_text))
    
    # RMU / Transformer connection
    # Draw a vertical line down from MV bus to Transformer
    trans_x = center_x
    trans_y = mv_y + 100
    
    dwg.add(dwg.line(start=(trans_x, mv_y), end=(trans_x, trans_y), style=style_line))
    
    # Transformer Symbol (Two overlapping circles)
    r = 15
    dwg.add(dwg.circle(center=(trans_x, trans_y + r), r=r, style=style_line))
    dwg.add(dwg.circle(center=(trans_x, trans_y + 3*r), r=r, style=style_line))
    dwg.add(dwg.text(f"Transformer\n{transformer_mva} MVA", insert=(trans_x + 25, trans_y + 2*r), style=style_text))
    
    # LV Busbar
    lv_y = trans_y + 4*r + 30
    lv_width = max(400, pcs_count * 150)
    lv_start_x = center_x - lv_width / 2
    lv_end_x = center_x + lv_width / 2
    
    dwg.add(dwg.line(start=(trans_x, trans_y + 4*r), end=(trans_x, lv_y), style=style_line))
    dwg.add(dwg.line(start=(lv_start_x, lv_y), end=(lv_end_x, lv_y), style=style_busbar))
    dwg.add(dwg.text(f"{lv_v} V Bus", insert=(lv_start_x, lv_y - 10), style=style_text))
    
    # PCS and DC Blocks
    pcs_y = lv_y + 80
    dc_bus_y = pcs_y + 80
    dc_block_y = dc_bus_y + 100
    
    # Calculate spacing for PCS
    pcs_spacing = lv_width / pcs_count if pcs_count > 0 else 150
    
    # Dashed box for "Battery Storage Bank"
    # It should enclose all DC blocks and maybe PCS DC side
    # Let's calculate the bounding box for all DC blocks
    
    min_dc_x = width
    max_dc_x = 0
    has_blocks = False
    
    for i in range(pcs_count):
        pcs_x = lv_start_x + pcs_spacing * (i + 0.5)
        
        # Connection from LV Bus to PCS
        dwg.add(dwg.line(start=(pcs_x, lv_y), end=(pcs_x, pcs_y), style=style_line))
        
        # PCS Symbol (Rectangle with diagonal and AC/DC indications)
        pcs_w = 40
        pcs_h = 40
        # Draw box
        dwg.add(dwg.rect(insert=(pcs_x - pcs_w/2, pcs_y), size=(pcs_w, pcs_h), style=style_line))
        # Draw diagonal line (bottom-left to top-right)
        dwg.add(dwg.line(start=(pcs_x - pcs_w/2, pcs_y + pcs_h), end=(pcs_x + pcs_w/2, pcs_y), style=style_line))
        
        # AC Symbol (~) in top-left triangle
        # Position roughly: x - 10, y + 15
        ac_sym_x = pcs_x - 12
        ac_sym_y = pcs_y + 14
        path_ac = f"M {ac_sym_x} {ac_sym_y} q 3 -5 6 0 t 6 0"
        dwg.add(dwg.path(d=path_ac, stroke="black", stroke_width=1.5, fill="none"))
        
        # DC Symbol (=) in bottom-right triangle
        # Position roughly: x + 2, y + 28
        dc_sym_x = pcs_x + 2
        dc_sym_y = pcs_y + 28
        dwg.add(dwg.line(start=(dc_sym_x, dc_sym_y), end=(dc_sym_x + 12, dc_sym_y), stroke="black", stroke_width=1.5))
        dwg.add(dwg.line(start=(dc_sym_x, dc_sym_y + 4), end=(dc_sym_x + 12, dc_sym_y + 4), stroke="black", stroke_width=1.5))
        
        dwg.add(dwg.text("PCS", insert=(pcs_x - pcs_w/2, pcs_y - 5), style=style_text))
        
        # DC Busbar for this PCS (Independent)
        # Draw a simple line for DC Busbar
        dc_bus_width = 60
        dwg.add(dwg.line(start=(pcs_x, pcs_y + pcs_h), end=(pcs_x, dc_bus_y), style=style_line))
        dwg.add(dwg.line(start=(pcs_x - dc_bus_width/2, dc_bus_y), end=(pcs_x + dc_bus_width/2, dc_bus_y), style=style_busbar))
        # No text for DC Bus as requested
        
        # DC Blocks for this PCS
        # Get block count for this feeder
        block_count = 0
        if i < len(dc_blocks_counts):
            block_count = dc_blocks_counts[i]
            
        if block_count > 0:
            has_blocks = True
            # Draw DC blocks below
            # Arrange them horizontally under the DC busbar
            
            block_spacing = 50
            total_block_width = block_count * 40 + (block_count - 1) * 10
            start_block_x = pcs_x - total_block_width / 2
            
            for b in range(block_count):
                blk_x = start_block_x + b * 50
                blk_y = dc_block_y
                
                # Update bounds for dashed box
                min_dc_x = min(min_dc_x, blk_x)
                max_dc_x = max(max_dc_x, blk_x + 40)
                
                # DC Block Symbol (Battery)
                # Two columns of battery cells
                dwg.add(dwg.rect(insert=(blk_x, blk_y), size=(40, 60), style=style_line))
                
                # Column 1 (left)
                c1_x = blk_x + 10
                for r in range(4):
                    y_off = blk_y + 10 + r * 12
                    dwg.add(dwg.line(start=(c1_x, y_off), end=(c1_x + 8, y_off), style=style_line)) # Long
                    dwg.add(dwg.line(start=(c1_x + 2, y_off + 4), end=(c1_x + 6, y_off + 4), style=style_line)) # Short

                # Column 2 (right)
                c2_x = blk_x + 22
                for r in range(4):
                    y_off = blk_y + 10 + r * 12
                    dwg.add(dwg.line(start=(c2_x, y_off), end=(c2_x + 8, y_off), style=style_line)) # Long
                    dwg.add(dwg.line(start=(c2_x + 2, y_off + 4), end=(c2_x + 6, y_off + 4), style=style_line)) # Short
                
                # Connection to DC Busbar
                # Draw single vertical line from top center of block to DC busbar
                dwg.add(dwg.line(start=(blk_x + 20, blk_y), end=(blk_x + 20, dc_bus_y), style=style_line))
                
    # Draw "Battery Storage Bank" dashed box
    # It should enclose all DC blocks.
    if has_blocks:
        box_margin = 20
        box_x = min_dc_x - box_margin
        box_y = dc_block_y - 30 # Start slightly above blocks (below DC busbar)
        box_w = (max_dc_x - min_dc_x) + 2 * box_margin
        box_h = 100 + box_margin # Height of blocks + margin
        
        dwg.add(dwg.rect(insert=(box_x, box_y), size=(box_w, box_h), style=style_dashed))
        dwg.add(dwg.text("Battery Storage Bank", insert=(box_x + 5, box_y - 5), style="font-size: 10px; fill: gray;"))

    dwg.save()
