import importlib.util
from typing import Dict


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def check_dependencies() -> Dict[str, bool]:
    return {
        "svgwrite": _has_module("svgwrite"),
        "cairosvg": _has_module("cairosvg"),
        "pypowsybl": _has_module("pypowsybl"),
    }
