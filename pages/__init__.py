"""Pages package for Streamlit app."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

__all__ = [
    "PROJECT_ROOT",
    "DATA_DIR",
]
