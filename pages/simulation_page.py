"""Simulation page."""

from __future__ import annotations

from typing import List

import streamlit as st

import simulation
from validation import ValidationIssue


def _render_errors(errors: List[ValidationIssue]) -> None:
    if not errors:
        return
    st.error("; ".join(f"{err.field}: {err.message}" for err in errors))


def render() -> None:
    st.header("Simulation")
    st.caption("Run simplified performance checks and surface debug information.")

    annual_cycles = st.number_input("Annual Cycles", min_value=0.0, value=300.0, step=10.0)
    rte = st.number_input("Round-trip Efficiency (%)", min_value=0.0, max_value=100.0, value=85.0, step=1.0)
    soi = st.number_input("Initial Stored Energy (MWh)", min_value=0.0, value=20.0, step=1.0)

    if st.button("Run Simulation"):
        try:
            payload = simulation.run_simulation(
                simulation.SimulationRequest(annual_cycles=annual_cycles, eff_rte=rte, soi_mwh=soi)
            )
        except ValueError as exc:
            errors = exc.args[0] if exc.args else []
            _render_errors(errors)
            return
        except Exception as exc:  # pragma: no cover
            st.exception(exc)
            return

        st.success("Simulation completed.")
        st.json(payload)
