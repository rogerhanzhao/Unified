import streamlit as st
import runpy
import sys
import os

st.title("CALB ESS Sizing Tool")

PAGES = {
    "DC Block Sizing": "pages/DC_Block_Sizing.py",
    "AC Block Sizing": "pages/AC_Block_Sizing.py",
}

choice = st.sidebar.selectbox("Select page", list(PAGES.keys()))

page_file = PAGES[choice]

if not os.path.isfile(page_file):
    st.error(f"Page file not found: {page_file}")
else:
    try:
        runpy.run_path(page_file, run_name="__main__")
    except Exception as e:
        st.error(f"Error in page {choice}:\n{e}")
        raise