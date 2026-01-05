import streamlit as st
from PIL import Image
import streamlit.elements.image as st_image
from streamlit.elements.lib.image_utils import image_to_url
st_image.image_to_url = image_to_url
try:
    from streamlit_drawable_canvas import st_canvas
except ImportError:
    st_canvas = None
except Exception:
    st_canvas = None
import json
import os
from pathlib import Path

def show():
    st.title("🎨 Diagram Studio (Beta)")
    st.markdown("Interactive editor for Single Line Diagrams and Site Layouts.")

    # 1. Select Diagram Type
    diagram_type = st.radio("Select Diagram Type", ["Single Line Diagram", "Site Layout"], horizontal=True)

    # 2. Load Background Image
    import io
    base_path = Path("outputs")
    bg_image = None

    if diagram_type == "Single Line Diagram":
        json_path = base_path / "sld_template.json"
        # Try session state first
        if "sld_png_bytes" in st.session_state:
            try:
                bg_image = Image.open(io.BytesIO(st.session_state["sld_png_bytes"]))
            except Exception:
                pass
        # Fallback to file
        if bg_image is None:
            img_path = base_path / "sld_latest.png"
            if img_path.exists():
                bg_image = Image.open(img_path)
    else:
        json_path = base_path / "layout_template.json"
        # Try session state first
        if "layout_png_bytes" in st.session_state:
            try:
                bg_image = Image.open(io.BytesIO(st.session_state["layout_png_bytes"]))
            except Exception:
                pass
        # Fallback to file
        if bg_image is None:
            img_path = base_path / "layout_latest.png"
            if img_path.exists():
                bg_image = Image.open(img_path)

    if bg_image:
        st.success(f"Loaded {diagram_type} background.")
    else:
        st.warning(f"No generated image found for {diagram_type}. Please generate one in the respective page first.")
        bg_image = Image.new("RGB", (800, 600), "white")

    # 3. Canvas Editor
    st.markdown("### Editor")
    st.caption("Draw annotations, boxes, or lines to adjust the layout. Save as template for future auto-generation.")

    # Canvas parameters
    stroke_width = st.slider("Stroke width: ", 1, 25, 3)
    stroke_color = st.color_picker("Stroke color hex: ", "#FF0000")
    bg_color = "#FFFFFF"
    drawing_mode = st.sidebar.selectbox(
        "Drawing tool:", ("rect", "line", "circle", "transform", "freedraw", "point", "polygon")
    )
    
    # Load existing template state if available
    initial_drawing = None
    if json_path.exists():
        if st.checkbox("Load existing template data"):
            try:
                with open(json_path, "r") as f:
                    initial_drawing = json.load(f)
            except:
                pass

    # Create a canvas component
    canvas_result = st_canvas(
        fill_color="rgba(255, 165, 0, 0.3)",  # Fixed fill color with some opacity
        stroke_width=stroke_width,
        stroke_color=stroke_color,
        background_color=bg_color,
        background_image=bg_image,
        update_streamlit=True,
        height=600,
        width=800 if bg_image is None else bg_image.width,
        drawing_mode=drawing_mode,
        initial_drawing=initial_drawing,
        key="diagram_studio_canvas",
    )

    # 4. Save Template
    if canvas_result.json_data is not None:
        st.markdown("### Template Data (JSON)")
        with st.expander("View JSON"):
            st.json(canvas_result.json_data)
        
        if st.button("Save as Template"):
            try:
                with open(json_path, "w") as f:
                    json.dump(canvas_result.json_data, f, indent=2)
                st.success(f"Template saved to {json_path}")
            except Exception as e:
                st.error(f"Failed to save template: {e}")

