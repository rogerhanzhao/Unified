"""Data loading helpers for the Streamlit sizing tool.

These helpers intentionally work with absolute paths so the UI can accept
user-provided locations while still supporting the default Excel assets that
ship with the repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd


class DataIOError(RuntimeError):
    """Raised when data loading fails."""


@dataclass
class DataLoadResult:
    path: Path
    shape: tuple[int, int]
    columns: list[str]
    preview: Optional[pd.DataFrame]


_REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_DC_DATA_PATH = (_REPO_ROOT / "ess_sizing_data_dictionary_v13_dc_autofit.xlsx").resolve()
DEFAULT_AC_DATA_PATH = (_REPO_ROOT / "AC_Block_Data_Dictionary_v1_1.xlsx").resolve()


def resolve_data_path(path_str: Optional[str], fallback: Path) -> Path:
    """Resolve and validate a data path.

    Always returns an absolute path and ensures the file exists.
    """

    candidate = Path(path_str).expanduser() if path_str else fallback
    if not candidate.is_absolute():
        candidate = candidate.resolve()

    if not candidate.exists():
        raise DataIOError(f"Data file not found: {candidate}")

    return candidate


def load_dictionary(path: Path, *, sheet: str | int | None = 0) -> DataLoadResult:
    """Load a sizing data dictionary Excel file.

    Returns a lightweight summary rather than the full DataFrame to keep
    session state small while still surfacing useful debug information.
    """

    try:
        df = pd.read_excel(path, sheet_name=sheet)
    except Exception as exc:  # pragma: no cover - surfaced to the UI
        raise DataIOError(f"Unable to read Excel file '{path}': {exc}")

    preview_rows = min(len(df), 5)
    preview_df = df.head(preview_rows) if preview_rows else None

    return DataLoadResult(
        path=path,
        shape=(len(df), len(df.columns)),
        columns=[str(c) for c in df.columns],
        preview=preview_df,
    )


def debug_payload(result: DataLoadResult) -> Dict[str, Any]:
    """Return a JSON-friendly payload summarizing a load result."""

    return {
        "path": str(result.path),
        "shape": result.shape,
        "columns": result.columns,
        "preview_rows": result.preview.to_dict(orient="list") if result.preview is not None else None,
    }
