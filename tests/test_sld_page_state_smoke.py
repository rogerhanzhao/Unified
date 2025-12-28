from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


def _app() -> AppTest:
    return AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=10)


def _go_to(app: AppTest, page: str) -> AppTest:
    app.sidebar.radio[0].set_value(page)
    return app.run()


def test_sld_first_visit_no_crash():
    app = _app().run()
    _go_to(app, "Single Line Diagram")
    assert len(app.exception) == 0


def test_sld_page_keeps_ac_lv_value_across_pages():
    app = _app()
    app.session_state["ac_inputs"] = {"lv_voltage_v": 690.0, "pcs_lv_v": 690.0, "grid_kv": 33.0}
    app.run()

    _go_to(app, "Single Line Diagram")
    lv_widget = app.number_input(key="diagram_inputs.lv_v")
    assert lv_widget.value == pytest.approx(690.0)

    _go_to(app, "Site Layout")
    _go_to(app, "Single Line Diagram")
    lv_widget = app.number_input(key="diagram_inputs.lv_v")
    assert lv_widget.value == pytest.approx(690.0)
    assert app.session_state["ac_inputs"]["lv_voltage_v"] == pytest.approx(690.0)
