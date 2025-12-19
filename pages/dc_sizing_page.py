"""DC sizing Streamlit page."""

from __future__ import annotations

from typing import List

import streamlit as st

import dc_logic
from data_io import DEFAULT_DC_DATA_PATH, DataIOError
from validation import ValidationIssue


def _render_errors(errors: List[ValidationIssue]) -> None:
    if not errors:
        return
    st.error("; ".join(f"{err.field}: {err.message}" for err in errors))


def render() -> None:
    st.header("DC Sizing")
    st.caption("Load data dictionaries, validate inputs, and compute simplified DC sizing outputs.")

    data_path = st.text_input("DC Data Path", value=str(DEFAULT_DC_DATA_PATH))
    poi_power = st.number_input("POI Power (MW)", min_value=0.0, value=10.0, step=1.0)
    energy_mwh = st.number_input("Energy (MWh)", min_value=0.0, value=20.0, step=1.0)

    if st.button("Run DC Sizing"):
        try:
            payload = dc_logic.run_dc_sizing(
                dc_logic.DCRequest(
                    data_path=data_path,
                    poi_power_mw=poi_power,
                    energy_mwh=energy_mwh,
                )
            )
        except ValueError as exc:
            errors = exc.args[0] if exc.args else []
            _render_errors(errors)
            return
        except DataIOError as exc:
            st.error(f"Data error: {exc}")
            return
        except Exception as exc:  # pragma: no cover - UI safety
            st.exception(exc)
            return

        st.success("DC sizing completed.")
        st.json(payload)

        st.subheader("Debug information")
        st.json(payload.get("data_debug", {}))
