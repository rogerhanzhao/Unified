# -----------------------------------------------------------------------------
# Personal Open-Source Notice
#
# Copyright (c) 2026 Alex.Zhao. All rights reserved.
#
# This repository is released under the MIT License (see LICENSE file).
# Intended use: learning, evaluation, and engineering reference for Utility-scale
# BESS/ESS sizing and Reporting workflows.
#
# DISCLAIMER: This software is provided "AS IS", without warranty of any kind,
# express or implied. In no event shall the author(s) be liable for any claim,
# damages, or other liability arising from, out of, or in connection with the
# software or the use or other dealings in the software.
#
# NOTE: This is a personal project. It is not an official product or statement
# of any company or organization.
# -----------------------------------------------------------------------------

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Tuple


def _parse_number(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    cleaned = str(value).replace("px", "").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned.split()[0])
    except Exception:
        return None


def _get_viewbox(root) -> Tuple[float, float, float, float]:
    view_box = root.attrib.get("viewBox")
    if view_box:
        parts = view_box.replace(",", " ").split()
        if len(parts) == 4:
            try:
                return tuple(float(part) for part in parts)
            except Exception:
                pass

    width = _parse_number(root.attrib.get("width")) or 0.0
    height = _parse_number(root.attrib.get("height")) or 0.0
    return 0.0, 0.0, width, height


def apply_raw_style(
    svg_in: Path,
    svg_out: Path,
    to_switchgear: Optional[str] = None,
    to_other_rmu: Optional[str] = None,
) -> None:
    svg_in = Path(svg_in)
    svg_out = Path(svg_out)

    tree = ET.parse(svg_in)
    root = tree.getroot()

    namespace = ""
    if root.tag.startswith("{"):
        namespace = root.tag.split("}")[0].strip("{")
    tag_style = f"{{{namespace}}}style" if namespace else "style"
    tag_g = f"{{{namespace}}}g" if namespace else "g"
    tag_text = f"{{{namespace}}}text" if namespace else "text"
    tag_rect = f"{{{namespace}}}rect" if namespace else "rect"

    min_x, min_y, width, height = _get_viewbox(root)
    if width > 0 and height > 0:
        bg = ET.Element(
            tag_rect,
            attrib={
                "x": f"{min_x:.1f}",
                "y": f"{min_y:.1f}",
                "width": f"{width:.1f}",
                "height": f"{height:.1f}",
                "fill": "#ffffff",
            },
        )
        root.insert(0, bg)

    css = """
.sld-raw text { fill: #000000 !important; font-family: Arial, 'DejaVu Sans', sans-serif !important; font-size: 11px !important; }
.sld-raw path, .sld-raw line, .sld-raw polyline, .sld-raw polygon, .sld-raw rect, .sld-raw circle, .sld-raw ellipse {
  stroke: #000000 !important;
  fill: none !important;
}
.sld-raw .sld-feeder-info { display: none !important; }
"""
    style = ET.Element(tag_style)
    style.text = css
    root.insert(0, style)
    existing_class = root.attrib.get("class", "")
    if "sld-raw" not in existing_class:
        root.attrib["class"] = f"{existing_class} sld-raw".strip()

    if to_switchgear or to_other_rmu:
        label_group = ET.Element(tag_g, attrib={"class": "sld-raw-labels"})
        if to_switchgear:
            left_text = ET.SubElement(
                label_group,
                tag_text,
                attrib={"x": f"{min_x + 10:.1f}", "y": f"{min_y + 18:.1f}"},
            )
            left_text.text = to_switchgear
        if to_other_rmu:
            right_text = ET.SubElement(
                label_group,
                tag_text,
                attrib={
                    "x": f"{min_x + width - 10:.1f}",
                    "y": f"{min_y + 18:.1f}",
                    "text-anchor": "end",
                },
            )
            right_text.text = to_other_rmu
        root.append(label_group)

    svg_out.parent.mkdir(parents=True, exist_ok=True)
    tree.write(svg_out, encoding="utf-8", xml_declaration=True)
