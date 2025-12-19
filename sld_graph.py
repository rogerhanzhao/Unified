from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Sequence

try:  # Optional dependency
    from graphviz import Digraph  # type: ignore
except Exception:  # pragma: no cover - best-effort import
    Digraph = None  # type: ignore


def _is_graphviz_graph(graph: object) -> bool:
    return Digraph is not None and isinstance(graph, Digraph)  # type: ignore[arg-type]


def _graph_format(graph: object, default: str = "png") -> str:
    if _is_graphviz_graph(graph):
        fmt = getattr(graph, "format", None)
        return fmt or default
    if isinstance(graph, Mapping):
        return graph.get("format", default)  # type: ignore[arg-type]
    return default


def init_graph(name: str = "sld", *, format: str = "png", engine: str = "dot"):
    """
    Initialize a graphviz.Digraph when available, otherwise a lightweight dict fallback.
    """
    if Digraph:
        return Digraph(name=name, format=format, engine=engine)  # type: ignore[call-arg]
    return {
        "name": name,
        "format": format,
        "engine": engine,
        "nodes": [],
        "edges": [],
    }


def add_nodes(graph: object, nodes: Iterable[Mapping | Sequence]):
    """
    Add nodes to a graph. Each node can be:
        - Mapping with keys: id, label (optional), attrs (optional)
        - Sequence like (id, label?, attrs?)
    """
    for node in nodes:
        if isinstance(node, Mapping):
            node_id = str(node["id"])
            label = str(node.get("label", node_id))
            attrs = dict(node.get("attrs", {}))
        else:
            seq = list(node)
            node_id = str(seq[0])
            label = str(seq[1]) if len(seq) > 1 else node_id
            attrs = dict(seq[2]) if len(seq) > 2 else {}

        if _is_graphviz_graph(graph):
            graph.node(node_id, label=label, **attrs)  # type: ignore[arg-type]
        elif isinstance(graph, MutableMapping):
            graph.setdefault("nodes", []).append({  # type: ignore[index]
                "id": node_id,
                "label": label,
                "attrs": attrs,
            })
        else:
            raise TypeError("Unsupported graph type for add_nodes")


def add_edges(graph: object, edges: Iterable[Mapping | Sequence]):
    """
    Add directed edges. Each edge can be:
        - Mapping with keys: tail, head, attrs (optional)
        - Sequence like (tail, head, attrs?)
    """
    for edge in edges:
        if isinstance(edge, Mapping):
            tail = str(edge["tail"])
            head = str(edge["head"])
            attrs = dict(edge.get("attrs", {}))
        else:
            seq = list(edge)
            tail = str(seq[0])
            head = str(seq[1])
            attrs = dict(seq[2]) if len(seq) > 2 else {}

        if _is_graphviz_graph(graph):
            graph.edge(tail, head, **attrs)  # type: ignore[arg-type]
        elif isinstance(graph, MutableMapping):
            graph.setdefault("edges", []).append({  # type: ignore[index]
                "tail": tail,
                "head": head,
                "attrs": attrs,
            })
        else:
            raise TypeError("Unsupported graph type for add_edges")


def _build_dot_source(graph: Mapping) -> str:
    lines = [f'digraph {graph.get("name", "G")} {{']
    for node in graph.get("nodes", []):
        node_id = node["id"]
        label = node.get("label", node_id)
        attrs = node.get("attrs", {})
        attr_parts = [f'label="{label}"']
        attr_parts.extend([f'{k}="{v}"' for k, v in attrs.items()])
        attr_str = ", ".join(attr_parts)
        lines.append(f'    "{node_id}" [{attr_str}];')

    for edge in graph.get("edges", []):
        tail = edge["tail"]
        head = edge["head"]
        attrs = edge.get("attrs", {})
        attr_str = ""
        if attrs:
            attr_str = " [" + ", ".join(f'{k}="{v}"' for k, v in attrs.items()) + "]"
        lines.append(f'    "{tail}" -> "{head}"{attr_str};')

    lines.append("}")
    return "\n".join(lines)


def render_graph(graph: object, output_path: str | Path, *, view: bool = False, cleanup: bool = True) -> str:
    """
    Render the graph to the requested path. Ensures directory exists and raises
    a RuntimeError with context when rendering fails.
    """
    out_path = Path(output_path)
    fmt = _graph_format(graph)
    if not out_path.suffix:
        out_path = out_path.with_suffix(f".{fmt}")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if _is_graphviz_graph(graph):
        try:
            rendered = graph.render(  # type: ignore[arg-type]
                filename=out_path.stem,
                directory=str(out_path.parent),
                view=view,
                cleanup=cleanup,
                format=fmt,
            )
        except Exception as exc:  # pragma: no cover - depends on environment
            raise RuntimeError(f"Graphviz rendering failed: {exc}") from exc
        return rendered

    if isinstance(graph, Mapping):
        dot_source = _build_dot_source(graph)
        try:
            out_path.write_text(dot_source, encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"Failed to write graph to {out_path}: {exc}") from exc
        return str(out_path)

    raise TypeError("Unsupported graph type for render_graph")


def build_default_sld(*, format: str = "png"):
    """
    Build a basic Single Line Diagram (SLD) for the AC block pathway.
    """
    graph = init_graph("ac_block_sld", format=format)
    nodes = [
        {"id": "poi", "label": "POI / Grid", "attrs": {"shape": "doublecircle"}},
        {"id": "rmu", "label": "RMU / Switchgear", "attrs": {"shape": "box"}},
        {"id": "xfmr", "label": "Transformer (MV/LV)", "attrs": {"shape": "box3d"}},
        {"id": "pcs", "label": "PCS", "attrs": {"shape": "diamond"}},
        {"id": "bus", "label": "DC Busbar", "attrs": {"shape": "parallelogram"}},
        {"id": "dc_block", "label": "DC Block", "attrs": {"shape": "folder"}},
    ]
    edges = [
        ("poi", "rmu"),
        ("rmu", "xfmr"),
        ("xfmr", "pcs"),
        ("pcs", "bus"),
        ("bus", "dc_block"),
    ]

    add_nodes(graph, nodes)
    add_edges(graph, edges)
    return graph
