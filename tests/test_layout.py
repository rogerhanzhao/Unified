import os

import pytest

from layout import compute_layout_positions, plot_layout


def test_compute_layout_positions_grid_and_ac_row():
    positions = compute_layout_positions(dc_blocks=5, ac_blocks=2, container_dims=(2, 1))

    expected_dc = [
        {"id": 1, "x": 0.0, "y": 0.0},
        {"id": 2, "x": 3.0, "y": 0.0},
        {"id": 3, "x": 6.0, "y": 0.0},
        {"id": 4, "x": 0.0, "y": 2.0},
        {"id": 5, "x": 3.0, "y": 2.0},
    ]
    expected_ac = [
        {"id": 1, "x": 0.0, "y": 5.0},
        {"id": 2, "x": 3.0, "y": 5.0},
    ]

    assert positions["dc"] == expected_dc
    assert positions["ac"] == expected_ac


def test_compute_layout_positions_validates_inputs():
    with pytest.raises(ValueError):
        compute_layout_positions(-1, 0, (1, 1))

    with pytest.raises(ValueError):
        compute_layout_positions(0, 0, (0, 1))


def test_plot_layout_saves_file(tmp_path):
    positions = compute_layout_positions(dc_blocks=2, ac_blocks=1, container_dims=(2, 1))
    out_file = tmp_path / "outputs" / "layout.png"

    plot_layout(positions, (2, 1), save_path=out_file)

    assert out_file.exists()
    assert out_file.suffix == ".png"
