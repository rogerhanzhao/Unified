# Compatibility shim for tests expecting a top-level `simulation` module
from calb_sizing_tool.sizing.simulation import simulate_dispatch, DispatchValidationError

__all__ = ["simulate_dispatch", "DispatchValidationError"]
