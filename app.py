import streamlit as st
from pathlib import Path
from PIL import Image

# --- 核心修改：将 page_title 改为全大写 ---
st.set_page_config(
    page_title="CALB ESS SIZING PLATFORM", 
    layout="wide", 
    page_icon="🔋"
)

# 引入 Config 以确保路径初始化
import calb_sizing_tool.config as config

# --- 侧边栏 ---
with st.sidebar:
    # 尝试加载 Logo
    logo_path = Path("calb_logo.png")
    if logo_path.exists():
        st.image(str(logo_path), width=200)
    else:
        # 如果没有图片，显示文字 Logo
        st.markdown("## CALB ESS")
        
    st.title("Navigation")
    st.markdown("---")
    
    # 导航菜单
    nav = st.radio(
        "Go to", 
        ["Dashboard", "DC Sizing", "AC Sizing", "Single Line Diagram"]
    )
    
    st.markdown("---")
    st.caption("v2.1 Refactored")

# --- 页面路由逻辑 ---
if nav == "Dashboard":
    st.title("🔋 CALB ESS SIZING PLATFORM")
    st.markdown("### Welcome to the Utility-Scale Energy Storage Sizing Tool")
    
    st.info("Please follow the standard workflow:")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### 1. DC Sizing")
        st.write("Define capacity, select battery technology, and calculate degradation.")
    with col2:
        st.markdown("#### 2. AC Sizing")
        st.write("Configure grid voltage, transformers, and PCS blocks based on DC results.")
    with col3:
        st.markdown("#### 3. SLD Generation")
        st.write("Automatically generate the Single Line Diagram for the system.")

elif nav == "DC Sizing":
    from calb_sizing_tool.ui.dc_view import show
    show()

elif nav == "AC Sizing":
    from calb_sizing_tool.ui.ac_view import show
    show()

elif nav == "Single Line Diagram":
    from calb_sizing_tool.ui.sld_view import show
    show()