import streamlit as st
from sizing.sld import build_default_sld, render_graph

st.header("Single Line Diagram")

dot = build_default_sld()
path = render_graph(dot, "ess_sld_test")
st.image(path, use_column_width=True)