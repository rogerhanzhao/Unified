"""Single-line diagram page."""

from __future__ import annotations

from typing import List

import streamlit as st

import sld
from validation import ValidationIssue


def _render_errors(errors: List[ValidationIssue]) -> None:
    if not errors:
        return
    st.error("; ".join(f"{err.field}: {err.message}" for err in errors))


def render() -> None:
    st.header("Single-Line Diagram")
    st.caption("Create placeholder SLD content from AC sizing results with visible debug information.")

    ac_blocks = st.number_input("AC Blocks", min_value=0, value=4, step=1)
    note = st.text_area("Layout Notes", value="Ensure MV equipment clearance maintained.")

    if st.button("Generate SLD"):
        try:
            payload = sld.build_sld(sld.SLDRequest(ac_blocks=ac_blocks, layout_note=note))
        except ValueError as exc:
            errors = exc.args[0] if exc.args else []
            _render_errors(errors)
            return
        except Exception as exc:  # pragma: no cover
            st.exception(exc)
            return

        st.success("SLD generated.")
        st.json(payload)
