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

    width = _parse_number(root.attrib.get("width"))
    height = _parse_number(root.attrib.get("height"))
    if width is None:
        width = 0.0
    if height is None:
        height = 0.0
    return 0.0, 0.0, width, height


def add_margins(
    svg_in: Path, svg_out: Path, left_margin_px: float, top_margin_px: float
) -> None:
    svg_in = Path(svg_in)
    svg_out = Path(svg_out)

    tree = ET.parse(svg_in)
    root = tree.getroot()

    namespace = ""
    if root.tag.startswith("{"):
        namespace = root.tag.split("}")[0].strip("{")
    tag_g = f"{{{namespace}}}g" if namespace else "g"

    _, _, width, height = _get_viewbox(root)
    new_width = width + left_margin_px
    new_height = height + top_margin_px

    root.attrib["viewBox"] = f"0 0 {new_width:.1f} {new_height:.1f}"
    if "width" in root.attrib:
        root.attrib["width"] = f"{new_width:.1f}"
    if "height" in root.attrib:
        root.attrib["height"] = f"{new_height:.1f}"

    defs = []
    content = []
    for child in list(root):
        if child.tag.endswith("defs") or child.tag.endswith("style"):
            defs.append(child)
        else:
            content.append(child)

    for child in list(root):
        root.remove(child)

    for child in defs:
        root.append(child)

    group = ET.Element(tag_g, attrib={"transform": f"translate({left_margin_px},{top_margin_px})"})
    for child in content:
        group.append(child)
    root.append(group)

    svg_out.parent.mkdir(parents=True, exist_ok=True)
    tree.write(svg_out, encoding="utf-8", xml_declaration=True)
