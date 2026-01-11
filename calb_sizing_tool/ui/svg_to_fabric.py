import xml.etree.ElementTree as ET
import re

def parse_style(style_str):
    """Parse inline style string into a dict."""
    style = {}
    if not style_str:
        return style
    for item in style_str.split(';'):
        if ':' in item:
            key, value = item.split(':', 1)
            style[key.strip()] = value.strip()
    return style

def get_stroke_width(elem, style):
    val = elem.get('stroke-width') or style.get('stroke-width')
    if val:
        return float(re.sub(r'[^\d\.]', '', val))
    return 1.0

def get_stroke(elem, style):
    return elem.get('stroke') or style.get('stroke') or 'black'

def get_fill(elem, style):
    val = elem.get('fill') or style.get('fill')
    if val == 'none':
        return 'transparent'
    return val or 'transparent'

def parse_dasharray(value):
    if not value:
        return None
    parts = re.findall(r'[-+]?\d*\.?\d+', value)
    if not parts:
        return None
    return [float(p) for p in parts]

def get_stroke_dasharray(elem, style):
    val = elem.get('stroke-dasharray') or style.get('stroke-dasharray')
    return parse_dasharray(val)

def parse_points(points_str):
    if not points_str:
        return []
    nums = re.findall(r'[-+]?\d*\.?\d+', points_str)
    points = []
    for i in range(0, len(nums) - 1, 2):
        points.append({"x": float(nums[i]), "y": float(nums[i + 1])})
    return points

def _parse_length(value):
    if value is None:
        return None
    try:
        return float(re.sub(r"[^\d\.]", "", str(value)))
    except Exception:
        return None


def _parse_viewbox(viewbox):
    if not viewbox:
        return None
    parts = re.findall(r"[-+]?\d*\.?\d+", str(viewbox))
    if len(parts) >= 4:
        try:
            return float(parts[2]), float(parts[3])
        except Exception:
            return None
    return None


def convert_svg_to_fabric(svg_path):
    """
    Convert a simple SVG file to Fabric.js JSON format for streamlit-drawable-canvas.
    Supports <rect>, <line>, <text>.
    """
    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
    except Exception as e:
        print(f"Error parsing SVG: {e}")
        return None

    width_attr = root.get("width")
    height_attr = root.get("height")
    width = _parse_length(width_attr)
    height = _parse_length(height_attr)
    if width is None or height is None:
        vb = _parse_viewbox(root.get("viewBox"))
        if vb:
            width, height = vb

    # Remove namespace prefixes
    for elem in root.iter():
        if '}' in elem.tag:
            elem.tag = elem.tag.split('}', 1)[1]

    objects = []
    
    # Global styles from <style> tag (very basic parsing)
    global_styles = {}
    for style_elem in root.findall('.//style'):
        if style_elem.text:
            # This is a hacky parser for CSS classes in SVG
            # .class { key: val; }
            matches = re.findall(r'\.([\w-]+)\s*\{([^}]+)\}', style_elem.text)
            for class_name, content in matches:
                global_styles[class_name] = parse_style(content)

    def get_elem_style(elem):
        """Merge global class styles and inline styles."""
        merged = {}
        class_name = elem.get('class')
        if class_name and class_name in global_styles:
            merged.update(global_styles[class_name])
        
        inline_style = elem.get('style')
        if inline_style:
            merged.update(parse_style(inline_style))
        return merged

    for elem in root.iter():
        style = get_elem_style(elem)
        dasharray = get_stroke_dasharray(elem, style)
        
        if elem.tag == 'rect':
            try:
                x = float(elem.get('x', 0))
                y = float(elem.get('y', 0))
                w = float(elem.get('width', 0))
                h = float(elem.get('height', 0))
                
                obj = {
                    "type": "rect",
                    "left": x,
                    "top": y,
                    "width": w,
                    "height": h,
                    "fill": get_fill(elem, style),
                    "stroke": get_stroke(elem, style),
                    "strokeWidth": get_stroke_width(elem, style),
                    "strokeDashArray": dasharray,
                    "selectable": True,
                    "hasControls": True
                }
                objects.append(obj)
            except ValueError:
                continue

        elif elem.tag == 'line':
            try:
                x1 = float(elem.get('x1', 0))
                y1 = float(elem.get('y1', 0))
                x2 = float(elem.get('x2', 0))
                y2 = float(elem.get('y2', 0))
                left = min(x1, x2)
                top = min(y1, y2)
                
                obj = {
                    "type": "line",
                    "left": left,
                    "top": top,
                    "width": abs(x2 - x1),
                    "height": abs(y2 - y1),
                    "x1": x1 - left,
                    "y1": y1 - top,
                    "x2": x2 - left,
                    "y2": y2 - top,
                    "stroke": get_stroke(elem, style),
                    "strokeWidth": get_stroke_width(elem, style),
                    "strokeDashArray": dasharray,
                    "selectable": True,
                    "hasControls": True
                }
                objects.append(obj)
            except ValueError:
                continue

        elif elem.tag == 'circle':
            try:
                cx = float(elem.get('cx', 0))
                cy = float(elem.get('cy', 0))
                r = float(elem.get('r', 0))
                
                obj = {
                    "type": "circle",
                    "left": cx - r,
                    "top": cy - r,
                    "radius": r,
                    "fill": get_fill(elem, style),
                    "stroke": get_stroke(elem, style),
                    "strokeWidth": get_stroke_width(elem, style),
                    "strokeDashArray": dasharray,
                    "selectable": True,
                    "hasControls": True
                }
                objects.append(obj)
            except ValueError:
                continue
        elif elem.tag == 'polyline':
            try:
                points = parse_points(elem.get('points', ''))
                if not points:
                    continue
                min_x = min(p["x"] for p in points)
                min_y = min(p["y"] for p in points)
                rel_points = [{"x": p["x"] - min_x, "y": p["y"] - min_y} for p in points]
                obj = {
                    "type": "polyline",
                    "left": min_x,
                    "top": min_y,
                    "points": rel_points,
                    "fill": get_fill(elem, style),
                    "stroke": get_stroke(elem, style),
                    "strokeWidth": get_stroke_width(elem, style),
                    "strokeDashArray": dasharray,
                    "selectable": True,
                    "hasControls": True
                }
                objects.append(obj)
            except ValueError:
                continue
        elif elem.tag == 'polygon':
            try:
                points = parse_points(elem.get('points', ''))
                if not points:
                    continue
                min_x = min(p["x"] for p in points)
                min_y = min(p["y"] for p in points)
                rel_points = [{"x": p["x"] - min_x, "y": p["y"] - min_y} for p in points]
                obj = {
                    "type": "polygon",
                    "left": min_x,
                    "top": min_y,
                    "points": rel_points,
                    "fill": get_fill(elem, style),
                    "stroke": get_stroke(elem, style),
                    "strokeWidth": get_stroke_width(elem, style),
                    "strokeDashArray": dasharray,
                    "selectable": True,
                    "hasControls": True
                }
                objects.append(obj)
            except ValueError:
                continue

        elif elem.tag == 'text':
            try:
                x = float(elem.get('x', 0))
                y = float(elem.get('y', 0))
                
                # Handle tspans for multi-line text
                tspans = list(elem.findall('tspan'))
                if tspans:
                    text_content = ""
                    for i, tspan in enumerate(tspans):
                        tspan_text = tspan.text or ""
                        if i > 0:
                            text_content += "\n"
                        text_content += tspan_text
                else:
                    text_content = elem.text or ""
                
                if not text_content.strip() and not tspans:
                    continue

                # Handle text-anchor
                anchor = elem.get('text-anchor', 'start')
                originX = 'left'
                if anchor == 'middle':
                    originX = 'center'
                elif anchor == 'end':
                    originX = 'right'

                # Handle transform="rotate(deg, cx, cy)"
                angle = 0
                transform = elem.get('transform')
                if transform and 'rotate' in transform:
                    match = re.search(r'rotate\(([\d\.-]+)', transform)
                    if match:
                        angle = float(match.group(1))

                font_size = style.get('font-size', '12px').replace('px', '')
                try:
                    font_size = float(font_size)
                except:
                    font_size = 12

                # Adjust for baseline difference between SVG and Fabric
                # SVG y is baseline, Fabric top is top-left.
                # Heuristic: subtract approx 0.8 * fontSize
                top_adj = y - (font_size * 0.8)

                obj = {
                    "type": "i-text",
                    "left": x,
                    "top": top_adj,
                    "originX": originX,
                    "text": text_content,
                    "fontSize": font_size,
                    "fill": get_fill(elem, style) or 'black',
                    "angle": angle,
                    "selectable": True,
                    "hasControls": True,
                    "fontFamily": style.get('font-family', 'Arial')
                }
                objects.append(obj)
            except ValueError:
                continue

    payload = {"version": "4.4.0", "objects": objects, "background": ""}
    if width:
        payload["width"] = width
    if height:
        payload["height"] = height
    return payload
