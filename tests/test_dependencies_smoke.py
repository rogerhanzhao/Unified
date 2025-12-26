from calb_sizing_tool.common.dependencies import check_dependencies


def test_check_dependencies_keys():
    deps = check_dependencies()
    assert isinstance(deps, dict)
    assert "svgwrite" in deps
    assert "cairosvg" in deps
    assert "pypowsybl" in deps
