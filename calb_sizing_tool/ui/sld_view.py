import streamlit as st
from calb_sizing_tool.models import ProjectSizingResult, ACBlockData, DCBlockData
from calb_sizing_tool.sld.topology import ElectricalTopology
from calb_sizing_tool.sld.generator import render_sld

def show_sld_interface():
    st.header("⚡ Single Line Diagram Generator")

    # 1. 获取数据 (尝试从 Session State 获取，否则使用默认值用于演示)
    # 真实场景中，这里的 data 应来自于 AC/DC Sizing 页面计算后的 st.session_state
    
    st.sidebar.subheader("SLD 参数 (模拟)")
    sim_power = st.sidebar.number_input("系统功率 (MW)", value=5.0)
    
    # 构造模拟数据用于演示
    data = ProjectSizingResult(
        total_power_mw=sim_power,
        total_capacity_mwh=sim_power * 4,
        ac_blocks=[
            ACBlockData(block_id="B1", power_mw=2.5, num_pcs=2, pcs_power_kw=1250),
            ACBlockData(block_id="B2", power_mw=2.5, num_pcs=2, pcs_power_kw=1250)
        ],
        dc_blocks=[
            DCBlockData(racks_per_cluster=10, battery_voltage_v=1200, total_energy_mwh=10),
            DCBlockData(racks_per_cluster=10, battery_voltage_v=1200, total_energy_mwh=10)
        ]
    )
    
    if st.button("生成系统拓扑图"):
        try:
            topo = ElectricalTopology(data)
            g = topo.get_graph()
            
            # 显示统计
            c1, c2 = st.columns(2)
            c1.metric("节点数量", g.number_of_nodes())
            c2.metric("连接线数量", g.number_of_edges())
            
            # 渲染图形
            dot = render_sld(g)
            st.graphviz_chart(dot, use_container_width=True)
            
        except Exception as e:
            st.error(f"生成失败: {e}")
            st.info("请确保已安装 Graphviz 软件并配置了环境变量。")