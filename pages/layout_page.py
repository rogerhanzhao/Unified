"""Layout calculation page."""

from __future__ import annotations

from typing import List

import streamlit as st

import layout
from validation import ValidationIssue


def _render_errors(errors: List[ValidationIssue]) -> None:
    if not errors:
        return
    st.error("; ".join(f"{err.field}: {err.message}" for err in errors))


def render() -> None:
    st.header("Site Layout")
    st.caption("Approximate layout density using DC and AC block counts.")

    dc_blocks = st.number_input("DC Blocks", min_value=0.0, value=12.0, step=1.0)
    ac_blocks = st.number_input("AC Blocks", min_value=0.0, value=4.0, step=1.0)
    site_area = st.number_input("Site Area (acres)", min_value=0.1, value=5.0, step=0.5)

    if st.button("Compute Layout"):
        try:
            payload = layout.compute_layout(
                layout.LayoutRequest(dc_blocks=dc_blocks, ac_blocks=ac_blocks, site_area_acres=site_area)
            )
        except ValueError as exc:
            errors = exc.args[0] if exc.args else []
            _render_errors(errors)
            return
        except Exception as exc:  # pragma: no cover
            st.exception(exc)
            return

        st.success("Layout computation completed.")
        st.json(payload)
