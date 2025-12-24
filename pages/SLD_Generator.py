import streamlit as st

from calb_sizing_tool.ui.sld_generator_view import show

st.set_page_config(page_title="SLD Generator (PowSyBl)", layout="wide")
show()
