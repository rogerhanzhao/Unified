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

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional


def _parse_translate(transform: str):
    match = re.search(r"translate\(([-\d.]+)[ ,]([-\d.]+)\)", transform or "")
    if not match:
        return None
    try:
        return float(match.group(1)), float(match.group(2))
    except Exception:
        return None


def _find_generator_positions(root, pcs_ids):
    positions = {}
    for elem in root.iter():
        if elem.tag.endswith("g"):
            texts = [child for child in list(elem) if child.tag.endswith("text")]
            if not texts:
                continue
            label = "".join(text.text or "" for text in texts).strip()
            if label in pcs_ids:
                transform = elem.attrib.get("transform", "")
                pos = _parse_translate(transform)
                if pos:
                    positions[label] = pos
    return positions


def _update_svg_height(root, required_height):
    try:
        current_height = float(root.attrib.get("height", "0"))
    except Exception:
        current_height = 0.0

    if required_height <= current_height:
        return

    root.attrib["height"] = f"{required_height:.1f}"

    view_box = root.attrib.get("viewBox")
    if view_box:
        parts = view_box.split()
        if len(parts) == 4:
            parts[3] = f"{required_height:.1f}"
            root.attrib["viewBox"] = " ".join(parts)


def append_dc_block_function_blocks(
    svg_in: Path,
    svg_out: Path,
    snapshot: dict,
    metadata: Optional[dict] = None,
) -> None:
    svg_in = Path(svg_in)
    svg_out = Path(svg_out)
    tree = ET.parse(svg_in)
    root = tree.getroot()
    namespace = ""
    if root.tag.startswith("{"):
        namespace = root.tag.split("}")[0].strip("{")
    tag_g = f"{{{namespace}}}g" if namespace else "g"
    tag_rect = f"{{{namespace}}}rect" if namespace else "rect"
    tag_text = f"{{{namespace}}}text" if namespace else "text"

    feeders = snapshot.get("feeders", [])
    dc_by_feeder = {item.get("feeder_id"): item for item in snapshot.get("dc_blocks_by_feeder", [])}
    pcs_ids = [feeder.get("pcs_id") for feeder in feeders if feeder.get("pcs_id")]
    positions = _find_generator_positions(root, set(pcs_ids))

    width = 92
    height = 26
    y_offset = 24

    required_height = 0.0

    for idx, feeder in enumerate(feeders, start=1):
        pcs_id = feeder.get("pcs_id") or f"PCS-{idx:02d}"
        feeder_id = feeder.get("feeder_id") or f"FDR_{idx:02d}"
        dc_entry = dc_by_feeder.get(feeder_id, {})
        dc_blocks = dc_entry.get("dc_blocks", 0)
        dc_energy = dc_entry.get("dc_energy_mwh")

        base_pos = positions.get(pcs_id)
        if base_pos:
            x, y = base_pos
        else:
            x = 20.0 + (idx - 1) * (width + 10)
            y = required_height + 10.0

        rect_x = x - width / 2
        rect_y = y + y_offset

        label = f"DC Block x{int(dc_blocks)}"
        if dc_energy is not None:
            label += f" / {dc_energy:.2f} MWh"

        group = ET.Element(tag_g, attrib={"class": "dc-block"})
        rect = ET.SubElement(
            group,
            tag_rect,
            attrib={
                "x": f"{rect_x:.1f}",
                "y": f"{rect_y:.1f}",
                "width": f"{width}",
                "height": f"{height}",
                "fill": "#f7f7f7",
                "stroke": "#3a3a3a",
                "stroke-width": "1",
                "rx": "3",
                "ry": "3",
            },
        )
        _ = rect
        text = ET.SubElement(
            group,
            tag_text,
            attrib={
                "x": f"{rect_x + 4:.1f}",
                "y": f"{rect_y + 16:.1f}",
                "font-size": "10",
                "font-family": "Helvetica, Arial, sans-serif",
                "fill": "#1e1e1e",
            },
        )
        text.text = label
        root.append(group)

        required_height = max(required_height, rect_y + height + 10.0)

    _update_svg_height(root, required_height)

    svg_out.parent.mkdir(parents=True, exist_ok=True)
    tree.write(svg_out, encoding="utf-8", xml_declaration=True)
