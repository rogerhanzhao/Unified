import streamlit as st

from calb_sizing_tool.ui.single_line_diagram_view import show

st.set_page_config(page_title="Single Line Diagram", layout="wide")
show()
