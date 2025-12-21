import streamlit as st
from PIL import Image

# Setup Page
st.set_page_config(page_title="CALB ESS Sizing Tool", layout="wide")

# Sidebar Logo
try:
    logo = Image.open("calb_logo.png")
    st.sidebar.image(logo, width=200)
except:
    st.sidebar.write("CALB ESS Platform")

# Navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Dashboard", "AC Sizing", "DC Sizing", "Single Line Diagram"])

# Import Logic (Lazy imports to prevent circular issues)
if page == "Dashboard":
    st.title("ESS Sizing Platform Dashboard")
    st.write("Select a module from the sidebar to begin.")
    
elif page == "AC Sizing":
    # Refactored import: assumes you moved logic to calb_sizing_tool/ui/ac_view.py
    # or you can temporarily import the old file if you haven't moved it yet
    try:
        from calb_sizing_tool.ui import ac_view
        ac_view.show() 
    except ImportError:
        st.warning("Please move 'ac_block_sizing.py' logic to 'calb_sizing_tool/ui/ac_view.py'")
        
elif page == "DC Sizing":
    try:
        from calb_sizing_tool.ui import dc_view
        dc_view.show()
    except ImportError:
        st.warning("Please move 'dc_block_sizing.py' logic to 'calb_sizing_tool/ui/dc_view.py'")

elif page == "Single Line Diagram":
    from calb_sizing_tool.ui.sld_view import show_sld_interface
    show_sld_interface()