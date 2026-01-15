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

import inspect
from pathlib import Path
from typing import Any, Optional


def render_sld_svg(
    network,
    container_id: str,
    out_svg: Path,
    out_metadata: Optional[Path] = None,
    parameters: Optional[dict] = None,
    sld_profile: Optional[Any] = None,
) -> None:
    out_svg = Path(out_svg)
    out_svg.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = None
    if out_metadata is not None:
        metadata_path = Path(out_metadata)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

    network.write_single_line_diagram_svg(
        container_id,
        out_svg,
        metadata_file=metadata_path,
        parameters=parameters,
        sld_profile=sld_profile,
    )


def render_pow_sybl_svg(
    network,
    container_id: str,
    out_svg: Path,
    out_metadata: Optional[Path] = None,
    parameters: Optional[dict] = None,
    sld_profile: Optional[Any] = None,
) -> None:
    render_sld_svg(
        network,
        container_id,
        out_svg,
        out_metadata=out_metadata,
        parameters=parameters,
        sld_profile=sld_profile,
    )


def _build_sld_parameters(overrides: Optional[dict] = None):
    try:
        import pypowsybl as pp
    except Exception:
        return None

    desired = {
        "use_name": True,
        "center_name": True,
        "diagonal_label": False,
        "nodes_infos": False,
        "tooltip_enabled": False,
        "topological_coloring": False,
        "display_current_feeder_info": False,
        "active_power_unit": "",
        "reactive_power_unit": "",
        "current_unit": "",
    }
    if overrides:
        for key, value in overrides.items():
            if value is not None:
                desired[key] = value

    try:
        sig = inspect.signature(pp.network.SldParameters)
    except Exception:
        return None

    kwargs = {key: value for key, value in desired.items() if key in sig.parameters}
    try:
        return pp.network.SldParameters(**kwargs)
    except Exception:
        return None


def render_raw_svg(
    network,
    container_id: str,
    out_svg: Path,
    out_metadata: Optional[Path] = None,
    parameters: Optional[dict] = None,
    sld_profile: Optional[Any] = None,
) -> None:
    params = None
    if parameters is None:
        params = _build_sld_parameters()
    else:
        params = parameters

    render_sld_svg(
        network,
        container_id,
        out_svg,
        out_metadata=out_metadata,
        parameters=params,
        sld_profile=sld_profile,
    )
