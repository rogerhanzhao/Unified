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
