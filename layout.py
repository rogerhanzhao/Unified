"""Simple layout helpers for positioning DC/AC blocks and optional plotting.

The helpers here are intentionally lightweight and avoid any Streamlit coupling
so they can be exercised in unit tests and headless environments.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Tuple

LayoutPosition = Dict[str, float]
LayoutPositions = Dict[str, List[LayoutPosition]]


def compute_layout_positions(
    dc_blocks: int, ac_blocks: int, container_dims: Tuple[float, float]
) -> LayoutPositions:
    """Return coordinates for DC and AC blocks in a simple grid layout.

    The algorithm arranges DC blocks in a near-square grid (ceil of square
    root columns) and places AC blocks in a single row beneath the DC grid.

    Args:
        dc_blocks: Number of DC block containers.
        ac_blocks: Number of AC blocks.
        container_dims: Tuple of (width, height) used for spacing in the plot.

    Returns:
        A dict with "dc" and "ac" keys mapping to lists of {"id", "x", "y"}.

    Raises:
        ValueError: If counts are negative or dimensions are non-positive.
    """

    if dc_blocks < 0 or ac_blocks < 0:
        raise ValueError("Block counts must be non-negative")

    try:
        width, height = (float(container_dims[0]), float(container_dims[1]))
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError("container_dims must be a tuple of two numbers") from exc

    if width <= 0 or height <= 0:
        raise ValueError("container_dims must be positive")

    gap = 1.0  # simple constant gap to keep coordinates predictable
    step_x = width + gap
    step_y = height + gap

    cols = max(1, int(math.ceil(math.sqrt(dc_blocks)))) if dc_blocks else 1
    positions: LayoutPositions = {"dc": [], "ac": []}

    for idx in range(dc_blocks):
        row = idx // cols
        col = idx % cols
        positions["dc"].append(
            {"id": idx + 1, "x": col * step_x, "y": row * step_y}
        )

    dc_rows = math.ceil(dc_blocks / cols) if dc_blocks else 0
    ac_y_start = dc_rows * step_y + (gap if dc_rows else 0.0)

    for idx in range(ac_blocks):
        positions["ac"].append({"id": idx + 1, "x": idx * step_x, "y": ac_y_start})

    return positions


def plot_layout(
    positions: LayoutPositions,
    container_dims: Tuple[float, float],
    *,
    save_path: Path | str | None = None,
    show: bool = False,
):
    """Render a lightweight layout plot.

    Args:
        positions: Output from :func:`compute_layout_positions`.
        container_dims: Tuple of (width, height) for drawing rectangles.
        save_path: Optional file path. When provided the figure is saved and the
            parent directory is created automatically.
        show: If True, call ``plt.show()`` for interactive environments.

    Returns:
        The matplotlib figure instance for further customization if desired.
    """

    try:
        import matplotlib

        # Force a headless-friendly backend so tests and servers without a display
        # do not fail when importing pyplot.
        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt  # noqa: E402  # isort: skip
        from matplotlib.patches import Rectangle  # noqa: E402  # isort: skip
    except ModuleNotFoundError:
        # Matplotlib is optional; if unavailable but a save_path is provided,
        # write a placeholder PNG-like file so callers still receive output.
        if save_path:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_bytes(b"Matplotlib unavailable; placeholder image.")
        return None

    width, height = float(container_dims[0]), float(container_dims[1])
    fig, ax = plt.subplots(figsize=(8, 6))

    def _draw_blocks(blocks: List[LayoutPosition], color: str, label_prefix: str):
        for block in blocks:
            ax.add_patch(
                Rectangle(
                    (block["x"], block["y"]),
                    width,
                    height,
                    facecolor=color,
                    edgecolor="black",
                    alpha=0.6,
                    linewidth=1.2,
                )
            )
            ax.text(
                block["x"] + width / 2,
                block["y"] + height / 2,
                f"{label_prefix}{block['id']}",
                ha="center",
                va="center",
                fontsize=9,
                color="black",
            )

    _draw_blocks(positions.get("dc", []), "#5cc3e4", "DC")
    _draw_blocks(positions.get("ac", []), "#23496b", "AC")

    all_x = [b["x"] for b in positions.get("dc", []) + positions.get("ac", [])]
    all_y = [b["y"] for b in positions.get("dc", []) + positions.get("ac", [])]
    if all_x and all_y:
        max_x = max(all_x) + width
        max_y = max(all_y) + height
    else:
        max_x = max(width, height)
        max_y = max(width, height)

    margin = max(width, height) * 0.2
    ax.set_xlim(-margin, max_x + margin)
    ax.set_ylim(-margin, max_y + margin)
    ax.set_aspect("equal")
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_title("DC/AC Block Layout")
    ax.grid(True, linestyle="--", alpha=0.3)

    if save_path:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, bbox_inches="tight")

    if show:
        plt.show()

    plt.close(fig)
    return fig
