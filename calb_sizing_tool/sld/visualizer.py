import graphviz
from calb_sizing_tool.models import ProjectSizingResult

def generate_sld(result: ProjectSizingResult, format='svg') -> graphviz.Digraph:
    dot = graphviz.Digraph(comment='ESS SLD', format=format)
    
    # Engineering Style
    dot.attr(rankdir='TB', splines='ortho', nodesep='0.6', ranksep='0.8')
    dot.attr('node', fontname='Helvetica', fontsize='10')

    # 1. Grid & POI
    with dot.subgraph(name='cluster_grid') as c:
        c.attr(style='invis')
        c.node('POI', label=f'POI\n{result.system_power_mw} MW', shape='doublecircle', style='filled', fillcolor='gold')

    # 2. MV Bus
    mv_kv = result.ac_blocks[0].mv_voltage_kv if result.ac_blocks else 33
    dot.node('MV_BUS', label=f"MV Busbar ({mv_kv} kV)", shape='underline', width='6', height='0.1')
    dot.edge('POI', 'MV_BUS', penwidth='3.0')

    # 3. AC Blocks (Limit visualization to 3 for clarity)
    blocks_to_show = result.ac_blocks[:3]
    for i, ac in enumerate(blocks_to_show):
        with dot.subgraph(name=f'cluster_b{i}') as b:
            b.attr(label=f'AC Block {i+1}', style='dashed', color='gray')
            
            # Transformer
            trafo = f'Trafo_{i}'
            lbl = f'Transformer\n{ac.transformer_kva} kVA\n{ac.mv_voltage_kv}/{ac.lv_voltage_v/1000:.3f}kV'
            b.node(trafo, label=lbl, shape='trapezium', style='filled', fillcolor='#87CEEB', fixedsize='false')
            dot.edge('MV_BUS', trafo)

            # PCS & Battery
            for p in range(ac.num_pcs):
                pcs = f'PCS_{i}_{p}'
                b.node(pcs, label=f'PCS\n{ac.pcs_power_kw} kW', shape='box', style='filled', fillcolor='#98FB98')
                b.edge(trafo, pcs, dir='none')
                
                # Battery Connection (Mock 1-to-1 for diagram)
                if ac.dc_blocks_connected:
                    dc = ac.dc_blocks_connected[0]
                    bat = f'BAT_{i}_{p}'
                    b.node(bat, label=f'Battery\n{dc.container_model}', shape='cylinder', style='filled', fillcolor='#FFA07A')
                    b.edge(pcs, bat, color='red', label='DC')

    if len(result.ac_blocks) > 3:
        dot.node('MORE', label=f'... {len(result.ac_blocks)-3} more blocks ...', shape='plaintext')
        dot.edge('MV_BUS', 'MORE', style='dotted')

    return dot