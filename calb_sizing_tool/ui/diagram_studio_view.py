import streamlit as st
import json
from pathlib import Path
from calb_sizing_tool.ui.svg_to_fabric import convert_svg_to_fabric
from calb_sizing_tool.ui.template_store import save_active, clear_active

try:
    from streamlit_drawable_canvas import st_canvas
except ImportError:
    st_canvas = None

def show():
    st.title("🎨 Diagram Studio (Live Code & Draw)")
    st.markdown("Bidirectional editor: Draw on the canvas OR edit the JSON code directly.")

    # 1. Select Diagram Type
    diagram_type = st.radio("Select Diagram Type", ["Single Line Diagram", "Site Layout"], horizontal=True)
    
    base_path = Path("outputs")
    svg_filename = "sld_latest.svg" if diagram_type == "Single Line Diagram" else "layout_latest.svg"
    svg_path = base_path / svg_filename
    json_path = base_path / ("sld_template.json" if diagram_type == "Single Line Diagram" else "layout_template.json")

    # Initialize Session State
    if "canvas_objects" not in st.session_state:
        st.session_state["canvas_objects"] = None
    if "canvas_version" not in st.session_state:
        st.session_state["canvas_version"] = 0
    if "last_diagram_type" not in st.session_state:
        st.session_state["last_diagram_type"] = None

    def load_from_svg():
        if svg_path.exists():
            fabric_data = convert_svg_to_fabric(str(svg_path))
            if fabric_data:
                st.session_state["canvas_objects"] = fabric_data
                st.session_state["canvas_version"] += 1
                st.toast(f"Loaded generated {diagram_type} into editor.")
            else:
                st.warning(f"Could not convert {svg_filename} to editable objects.")
        else:
            st.info(f"No generated {svg_filename} found. Please generate it first.")

    # Detect type change or first load
    if st.session_state["last_diagram_type"] != diagram_type:
        st.session_state["last_diagram_type"] = diagram_type
        st.session_state["canvas_objects"] = None
        load_from_svg()
    
    # Manual Reload Button
    if st.button("🔄 Reload from Generated Output"):
        load_from_svg()
        st.rerun()

    # 2. Layout: Canvas Top, JSON Bottom
    
    st.subheader("Visual Editor")
    st.info("💡 **Tips**: Select object -> Press `Delete` key or use button below. Double-click text to edit.")

    # Canvas Size Controls
    with st.expander("⚙️ Canvas Settings (Resize)"):
        c_w, c_h = st.columns(2)
        canvas_width = c_w.number_input("Width", value=1000, step=50, key="canvas_w")
        canvas_height = c_h.number_input("Height", value=800, step=50, key="canvas_h")

    # Toolbar
    col_tool, col_width, col_color = st.columns([2, 1, 1])
    with col_tool:
        drawing_mode = st.selectbox(
            "Drawing Tool:",
            ("transform", "rect", "line", "circle", "freedraw", "point", "polygon", "text"),
            key="drawing_mode_select"
        )
    with col_width:
        stroke_width = st.slider("Stroke width: ", 1, 25, 3)
    with col_color:
        stroke_color = st.color_picker("Stroke color: ", "#000000")
    
    col_act1, col_act2, col_act3 = st.columns(3)
    with col_act1:
        if st.button("➕ Add Text Label"):
            new_text = {
                "type": "i-text",
                "left": 50,
                "top": 50,
                "text": "New Label",
                "fontSize": 16,
                "fill": stroke_color,
                "selectable": True
            }
            if st.session_state["canvas_objects"] is None:
                    st.session_state["canvas_objects"] = {"objects": [], "background": ""}
            
            if "objects" in st.session_state["canvas_objects"]:
                st.session_state["canvas_objects"]["objects"].append(new_text)
                st.session_state["canvas_version"] += 1
                st.rerun()
    with col_act2:
        if st.button("🗑️ Clear All"):
            st.session_state["canvas_objects"] = {"objects": [], "background": ""}
            st.session_state["canvas_version"] += 1
            st.rerun()
    with col_act3:
        st.caption("To delete: Select & Press Backspace/Delete")

    # Canvas
    if st_canvas:
        canvas_result = st_canvas(
            fill_color="rgba(255, 165, 0, 0.3)",
            stroke_width=stroke_width,
            stroke_color=stroke_color,
            background_color="#ffffff",
            background_image=None,
            update_streamlit=True,
            height=canvas_height,
            width=canvas_width,
            drawing_mode=drawing_mode,
            initial_drawing=st.session_state["canvas_objects"],
            key=f"canvas_{diagram_type}_{st.session_state['canvas_version']}",
        )

        # Sync Logic: Canvas -> State
        if canvas_result.json_data is not None:
            # Check if changed
            current_state = st.session_state["canvas_objects"]
            new_state = canvas_result.json_data
            
            # Simple comparison
            if current_state != new_state:
                st.session_state["canvas_objects"] = new_state
                # Don't rerun immediately to avoid flickering, let user interact
    else:
        st.error("streamlit-drawable-canvas is not installed.")

    st.markdown("---")
    
    # Action Buttons (Apply / Reset)
    col_apply, col_reset = st.columns(2)
    
    with col_apply:
        if st.button("💾 Apply to System (Use this as Manual Override)", type="primary"):
            data = st.session_state.get("canvas_objects")
            if data:
                try:
                    # Filter helper objects
                    objs = data.get("objects") or []
                    filtered = [o for o in objs if not isinstance(o.get("meta"), dict) or o.get("meta", {}).get("role") != "helper"]
                    payload = dict(data)
                    payload["objects"] = filtered

                    # Save preview image if available
                    preview_png_path = None
                    if st_canvas and canvas_result.image_data is not None:
                        from PIL import Image
                        img = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                        png_filename = "sld_latest.png" if diagram_type == "Single Line Diagram" else "layout_latest.png"
                        png_path = base_path / png_filename
                        img.save(png_path)
                        preview_png_path = str(png_path)
                    # Persist via TemplateStore
                    dtype = "sld" if diagram_type == "Single Line Diagram" else "layout"
                    save_active(dtype, payload, preview_png_path=preview_png_path, meta={"source": "diagram_studio"})
                    st.success("Applied! Manual template stored.")
                    st.toast("Manual override applied successfully.")
                except Exception as e:
                    st.error(f"Save failed: {e}")

    with col_reset:
        if st.button("❌ Reset to Auto-Generation (Delete Override)"):
            try:
                dtype = "sld" if diagram_type == "Single Line Diagram" else "layout"
                clear_active(dtype)
                st.success("Manual override removed. Go to SLD/Layout page to regenerate.")
                st.rerun()
            except Exception as e:
                st.error(f"Reset failed: {e}")

    st.markdown("---")
    st.subheader("JSON Source (Advanced)")

    # Callback for JSON editor
    def on_json_change():
        try:
            json_str = st.session_state["json_editor_area"]
            new_data = json.loads(json_str)
            st.session_state["canvas_objects"] = new_data
            st.session_state["canvas_version"] += 1
            st.toast("Canvas updated from JSON!")
        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON: {e}")

    current_json_str = "{}"
    if st.session_state["canvas_objects"]:
        current_json_str = json.dumps(st.session_state["canvas_objects"], indent=2)
    
    st.text_area(
        "Edit JSON directly:",
        value=current_json_str,
        height=400,
        key="json_editor_area",
        on_change=on_json_change
    )
