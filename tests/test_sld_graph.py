from pathlib import Path

import pytest

from sld_graph import (
    add_edges,
    add_nodes,
    build_default_sld,
    init_graph,
    render_graph,
)


def test_build_default_sld_renders_to_disk(tmp_path: Path):
    graph = build_default_sld(format="dot")
    output_file = render_graph(graph, tmp_path / "default_sld")
    output_path = Path(output_file)

    assert output_path.exists()
    text = output_path.read_text(encoding="utf-8")
    assert "POI / Grid" in text
    assert '"bus" -> "dc_block"' in text


def test_custom_nodes_and_edges(tmp_path: Path):
    graph = init_graph("custom", format="dot")
    add_nodes(graph, [("a", "Node A"), {"id": "b", "label": "Node B", "attrs": {"shape": "box"}}])
    add_edges(graph, [("a", "b")])

    rendered = render_graph(graph, tmp_path / "custom_graph")
    rendered_path = Path(rendered)
    assert rendered_path.exists()

    content = rendered_path.read_text(encoding="utf-8")
    assert "Node A" in content
    assert "Node B" in content
    assert '"a" -> "b"' in content
