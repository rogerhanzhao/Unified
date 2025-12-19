"""Utility helpers for loading and validating DC/AC sizing data dictionaries.

The module provides three entry points:

``load_excel_dict(file_path)``
    Loads an Excel workbook into a ``dict`` mapping sheet name → ``pandas.DataFrame``.
    The helper validates the input path before delegating to ``pandas.read_excel``
    and normalises sheet names to stripped strings.

``validate_dc_data(dc_dict)``
    Validates a DC sizing data dictionary. The function expects a mapping with at
    least the following sheets/columns (column order is irrelevant):

    * ``ess_sizing_case`` – ``["Enable", "Group", "Display Name", "Field Name", "Role", "Default Value", "Data Type", "Description Zh"]``
    * ``dc_block_template_314_data`` – ``["Dc_Block_Template_Id", "Dc_Block_Code", "Dc_Block_Name", "Block_Form", "Container_Length_Ft", "Rack_Type_Id", "Racks_Per_Block", "Packs_Per_Block", "Block_Nameplate_Capacity_Mwh", "Block_Aux_Energy_Kwh", "Design_Max_C_Rate", "Is_Default_Option", "Is_Active"]``
    * ``soh_profile_314_data`` – ``["Profile_Id", "Cell_Type_Id", "Profile_Name", "Cycles_Per_Year", "C_Rate", "Reference_Temperature_C", "Remark"]``
    * ``soh_curve_314_template`` – ``["Curve_Point_Id", "Profile_Id", "Life_Year_Index", "Cycle_Index", "Soh_Dc_Pct"]``
    * ``rte_profile_314_data`` – ``["Profile_Id", "Cell_Type_Id", "Profile_Name", "Cycles_Per_Year", "C_Rate", "Remark"]``
    * ``rte_curve_314_template`` – ``["Curve_Point_Id", "Profile_Id", "Soh_Band_Min_Pct", "Soh_Band_Max_Pct", "Rte_Dc_Pct"]``

    The validator performs basic content checks (e.g., presence of at least one
    active container-form DC block) and returns ``(ok, errors)`` where ``ok`` is a
    ``bool`` flag and ``errors`` is a list of human-readable strings.

``validate_ac_data(ac_dict)``
    Validates an AC block data dictionary. Required sheets/columns include:

    * ``PCS_Catalog_Dict`` – ``["Field Name En", "Field Name Cn", "Data Type", "Unit", "Description", "Required", "Example"]``
    * ``Cert_Standard_Dict`` – same columns as ``PCS_Catalog_Dict``
    * ``Cert_Document_List`` – same columns as ``PCS_Catalog_Dict``
    * ``PCS_Cert_Mapping`` – same columns as ``PCS_Catalog_Dict``
    * ``AC_Block_Option_Dict`` – same columns as ``PCS_Catalog_Dict``
    * ``Market_Requirement_Dict`` – same columns as ``PCS_Catalog_Dict``

    The validator focuses on structural sanity (sheet + column presence and
    non-empty content). Cross-sheet value validation can be layered on by the
    caller if needed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Tuple

import pandas as pd


DC_REQUIRED_SHEETS: Dict[str, Iterable[str]] = {
    "ess_sizing_case": [
        "Enable",
        "Group",
        "Display Name",
        "Field Name",
        "Role",
        "Default Value",
        "Data Type",
        "Description Zh",
    ],
    "dc_block_template_314_data": [
        "Dc_Block_Template_Id",
        "Dc_Block_Code",
        "Dc_Block_Name",
        "Block_Form",
        "Container_Length_Ft",
        "Rack_Type_Id",
        "Racks_Per_Block",
        "Packs_Per_Block",
        "Block_Nameplate_Capacity_Mwh",
        "Block_Aux_Energy_Kwh",
        "Design_Max_C_Rate",
        "Is_Default_Option",
        "Is_Active",
    ],
    "soh_profile_314_data": [
        "Profile_Id",
        "Cell_Type_Id",
        "Profile_Name",
        "Cycles_Per_Year",
        "C_Rate",
        "Reference_Temperature_C",
        "Remark",
    ],
    "soh_curve_314_template": [
        "Curve_Point_Id",
        "Profile_Id",
        "Life_Year_Index",
        "Cycle_Index",
        "Soh_Dc_Pct",
    ],
    "rte_profile_314_data": [
        "Profile_Id",
        "Cell_Type_Id",
        "Profile_Name",
        "Cycles_Per_Year",
        "C_Rate",
        "Remark",
    ],
    "rte_curve_314_template": [
        "Curve_Point_Id",
        "Profile_Id",
        "Soh_Band_Min_Pct",
        "Soh_Band_Max_Pct",
        "Rte_Dc_Pct",
    ],
}

AC_REQUIRED_SHEETS: Dict[str, Iterable[str]] = {
    "PCS_Catalog_Dict": [
        "Field Name En",
        "Field Name Cn",
        "Data Type",
        "Unit",
        "Description",
        "Required",
        "Example",
    ],
    "Cert_Standard_Dict": [
        "Field Name En",
        "Field Name Cn",
        "Data Type",
        "Unit",
        "Description",
        "Required",
        "Example",
    ],
    "Cert_Document_List": [
        "Field Name En",
        "Field Name Cn",
        "Data Type",
        "Unit",
        "Description",
        "Required",
        "Example",
    ],
    "PCS_Cert_Mapping": [
        "Field Name En",
        "Field Name Cn",
        "Data Type",
        "Unit",
        "Description",
        "Required",
        "Example",
    ],
    "AC_Block_Option_Dict": [
        "Field Name En",
        "Field Name Cn",
        "Data Type",
        "Unit",
        "Description",
        "Required",
        "Example",
    ],
    "Market_Requirement_Dict": [
        "Field Name En",
        "Field Name Cn",
        "Data Type",
        "Unit",
        "Description",
        "Required",
        "Example",
    ],
}


def load_excel_dict(file_path: str | Path) -> Dict[str, pd.DataFrame]:
    """Load an Excel workbook into a dictionary of ``pandas.DataFrame`` objects.

    Args:
        file_path: Path to an ``.xls``/``.xlsx``/``.xlsm``/``.xlsb`` file.

    Returns:
        A dictionary keyed by sheet name (stripped of surrounding whitespace),
        where every value is the corresponding DataFrame.

    Raises:
        TypeError: If ``file_path`` is not a string or ``Path``-like object.
        FileNotFoundError: If the path does not exist.
        ValueError: If the extension is unsupported, the workbook is empty, or
            pandas is unable to read the file.
    """

    if not isinstance(file_path, (str, Path)):
        raise TypeError("file_path must be a string or pathlib.Path")

    path = Path(file_path).expanduser()
    if path.suffix.lower() not in {".xls", ".xlsx", ".xlsm", ".xlsb"}:
        raise ValueError(f"Unsupported Excel extension for '{path.name}'.")

    if not path.exists():
        raise FileNotFoundError(f"Excel file not found: {path}")

    try:
        frames = pd.read_excel(path, sheet_name=None)
    except Exception as exc:  # noqa: BLE001 - propagate as ValueError for caller clarity
        raise ValueError(f"Unable to read Excel file '{path}': {exc}") from exc

    if not isinstance(frames, Mapping) or not frames:
        raise ValueError(f"No worksheets found in '{path.name}'.")

    normalized: Dict[str, pd.DataFrame] = {}
    for raw_name, df in frames.items():
        if not isinstance(df, pd.DataFrame):
            raise ValueError(f"Worksheet '{raw_name}' is not a DataFrame.")
        name = str(raw_name).strip()
        normalized[name] = df

    return normalized


def _normalize_sheet_dict(
    sheet_dict: Mapping[str, pd.DataFrame] | None,
    errors: List[str],
    label: str,
) -> Dict[str, pd.DataFrame]:
    if sheet_dict is None:
        errors.append(f"{label} is None; expected a mapping of sheet name to DataFrame.")
        return {}
    if not isinstance(sheet_dict, Mapping):
        errors.append(f"{label} must be a mapping of sheet name to DataFrame.")
        return {}

    normalized: Dict[str, pd.DataFrame] = {}
    for raw_name, df in sheet_dict.items():
        name = str(raw_name).strip()
        if not isinstance(df, pd.DataFrame):
            errors.append(f"Sheet '{name}' is not a pandas DataFrame.")
            continue
        normalized[name] = df

    if not normalized and not errors:
        errors.append(f"{label} contained no DataFrames.")

    return normalized


def _validate_sheet(df: pd.DataFrame, sheet_name: str, required_columns: Iterable[str], errors: List[str]) -> None:
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        errors.append(
            f"Sheet '{sheet_name}' is missing required column(s): {', '.join(missing_cols)}."
        )
    if df.empty:
        errors.append(f"Sheet '{sheet_name}' is present but empty.")


def validate_dc_data(dc_dict: Mapping[str, pd.DataFrame] | None) -> Tuple[bool, List[str]]:
    """Validate DC sizing workbook contents.

    Validation covers:
    * Presence of required sheets defined in ``DC_REQUIRED_SHEETS``.
    * Presence of each sheet's required columns.
    * Non-empty content for required sheets.
    * At least one active container-form DC block entry in
      ``dc_block_template_314_data`` (``Is_Active == 1`` and
      ``Block_Form`` equals ``"container"``).

    Args:
        dc_dict: Mapping of sheet name → DataFrame (e.g., output of
            ``load_excel_dict`` for ``ess_sizing_data_dictionary_v13_dc_autofit.xlsx``).

    Returns:
        ``(ok, errors)`` where ``ok`` is ``True`` if validation passes and
        ``errors`` is a list of human-readable error strings.
    """

    errors: List[str] = []
    normalized = _normalize_sheet_dict(dc_dict, errors, "dc_dict")

    for sheet, cols in DC_REQUIRED_SHEETS.items():
        df = normalized.get(sheet)
        if df is None:
            errors.append(f"Missing required sheet '{sheet}'.")
            continue
        _validate_sheet(df, sheet, cols, errors)

    blocks = normalized.get("dc_block_template_314_data")
    if blocks is not None and not blocks.empty and set(DC_REQUIRED_SHEETS["dc_block_template_314_data"]).issubset(blocks.columns):
        active_blocks = blocks[blocks["Is_Active"] == 1]
        containers = active_blocks[active_blocks["Block_Form"].astype(str).str.lower() == "container"]
        if active_blocks.empty:
            errors.append("dc_block_template_314_data must contain at least one active DC block (Is_Active == 1).")
        if containers.empty:
            errors.append("dc_block_template_314_data must contain at least one active container-form DC block.")

    ok = len(errors) == 0
    return ok, errors


def validate_ac_data(ac_dict: Mapping[str, pd.DataFrame] | None) -> Tuple[bool, List[str]]:
    """Validate AC block workbook contents.

    Validation covers:
    * Presence of required sheets defined in ``AC_REQUIRED_SHEETS``.
    * Presence of each sheet's required columns.
    * Non-empty content for required sheets.

    Args:
        ac_dict: Mapping of sheet name → DataFrame (e.g., output of
            ``load_excel_dict`` for ``AC_Block_Data_Dictionary_v1_1.xlsx``).

    Returns:
        ``(ok, errors)`` where ``ok`` is ``True`` if validation passes and
        ``errors`` is a list of human-readable error strings.
    """

    errors: List[str] = []
    normalized = _normalize_sheet_dict(ac_dict, errors, "ac_dict")

    for sheet, cols in AC_REQUIRED_SHEETS.items():
        df = normalized.get(sheet)
        if df is None:
            errors.append(f"Missing required sheet '{sheet}'.")
            continue
        _validate_sheet(df, sheet, cols, errors)

    ok = len(errors) == 0
    return ok, errors
