import streamlit as st
from PIL import Image
import streamlit.elements.image as st_image
from streamlit.elements.lib.image_utils import image_to_url
st_image.image_to_url = image_to_url
from streamlit_drawable_canvas import st_canvas
import json
import os
from pathlib import Path

def show():
    st.title("🎨 Diagram Studio (Beta)")
    st.markdown("Interactive editor for Single Line Diagrams and Site Layouts.")

    # 1. Select Diagram Type
    diagram_type = st.radio("Select Diagram Type", ["Single Line Diagram", "Site Layout"], horizontal=True)

    # 2. Load Background Image
    # Determine path based on type
    # Assuming outputs are in 'outputs/' relative to project root
    # We need to find the absolute path or relative to where app.py is run
    
    # Try to find the latest generated image
    # Based on previous context, images might be sld_latest.png or layout_latest.png
    # If only SVG exists, we might need to convert or just use a placeholder if we can't render SVG in canvas background easily (canvas usually takes raster)
    
    base_path = Path("outputs")
    if diagram_type == "Single Line Diagram":
        img_path = base_path / "sld_latest.png"
        json_path = base_path / "sld_template.json"
    else:
        img_path = base_path / "layout_latest.png"
        json_path = base_path / "layout_template.json"

    bg_image = None
    if img_path.exists():
        try:
            bg_image = Image.open(img_path)
            st.success(f"Loaded background: {img_path}")
        except Exception as e:
            st.error(f"Error loading image: {e}")
    else:
        st.warning(f"No generated image found at {img_path}. Please generate one in the respective page first.")
        # Create a blank white image if none exists
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

