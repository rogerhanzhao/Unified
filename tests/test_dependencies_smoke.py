import svgwrite

from calb_sizing_tool.common.dependencies import check_dependencies


def test_check_dependencies_keys():
    assert svgwrite is not None
    deps = check_dependencies()
    assert isinstance(deps, dict)
    assert "svgwrite" in deps
    assert "cairosvg" in deps
    assert "pypowsybl" in deps
