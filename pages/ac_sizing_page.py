"""AC sizing Streamlit page."""

from __future__ import annotations

from typing import List

import streamlit as st

import ac_logic
from data_io import DEFAULT_AC_DATA_PATH, DataIOError
from validation import ValidationIssue


def _render_errors(errors: List[ValidationIssue]) -> None:
    if not errors:
        return
    st.error("; ".join(f\"{err.field}: {err.message}\" for err in errors))


def render() -> None:
    st.header("AC Sizing")
    st.caption("Connect DC sizing outputs to AC block sizing with clear validation and debug data.")

    data_path = st.text_input("AC Data Path", value=str(DEFAULT_AC_DATA_PATH))
    poi_power = st.number_input("POI Power (MW)", min_value=0.0, value=10.0, step=1.0)
    dc_blocks = st.number_input("DC Block Quantity", min_value=0.0, value=12.0, step=1.0)

    if st.button("Run AC Sizing"):
        try:
            payload = ac_logic.run_ac_sizing(
                ac_logic.ACRequest(
                    data_path=data_path,
                    poi_power_mw=poi_power,
                    dc_block_qty=dc_blocks,
                )
            )
        except ValueError as exc:
            errors = exc.args[0] if exc.args else []
            _render_errors(errors)
            return
        except DataIOError as exc:
            st.error(f"Data error: {exc}")
            return
        except Exception as exc:  # pragma: no cover
            st.exception(exc)
            return

        st.success("AC sizing completed.")
        st.json(payload)

        st.subheader("Debug information")
        st.json(payload.get("data_debug", {}))
