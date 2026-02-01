from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from calb_sizing_tool.config import DC_DATA_PATH


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _cell_energy_wh(df_cell: pd.DataFrame) -> Dict[int, float]:
    energy_map: Dict[int, float] = {}
    for _, row in df_cell.iterrows():
        cell_type_id = row.get("Cell_Type_Id")
        if cell_type_id is None or pd.isna(cell_type_id):
            continue
        wh = row.get("Cell_Energy_Wh")
        if wh is None or pd.isna(wh):
            wh = _safe_float(row.get("Cell_Capacity_Ah"), 0.0) * _safe_float(row.get("Cell_Nominal_Voltage_V"), 0.0)
        energy = _safe_float(wh, 0.0)
        if energy > 0:
            energy_map[int(cell_type_id)] = energy
    return energy_map


def _pack_energy_kwh(df_pack: pd.DataFrame, cell_energy_map: Dict[int, float]) -> Dict[int, float]:
    pack_map: Dict[int, float] = {}
    for _, row in df_pack.iterrows():
        pack_id = row.get("Pack_Type_Id")
        cell_type_id = row.get("Cell_Type_Id")
        if pack_id is None or cell_type_id is None:
            continue
        if pd.isna(pack_id) or pd.isna(cell_type_id):
            continue
        cell_wh = cell_energy_map.get(int(cell_type_id))
        if not cell_wh:
            continue
        series = _safe_float(row.get("Cells_In_Series"), 0.0)
        parallel = _safe_float(row.get("Cells_In_Parallel"), 0.0)
        if series <= 0 or parallel <= 0:
            continue
        pack_kwh = (cell_wh * series * parallel) / 1000.0
        if pack_kwh > 0:
            pack_map[int(pack_id)] = pack_kwh
    return pack_map


def _rack_energy_mwh(df_rack: pd.DataFrame, pack_map: Dict[int, float]) -> Dict[int, float]:
    rack_map: Dict[int, float] = {}
    for _, row in df_rack.iterrows():
        rack_id = row.get("Rack_Type_Id")
        pack_id = row.get("Pack_Type_Id")
        if rack_id is None or pack_id is None:
            continue
        if pd.isna(rack_id) or pd.isna(pack_id):
            continue
        pack_kwh = pack_map.get(int(pack_id))
        if not pack_kwh:
            continue
        packs_per_rack = _safe_float(row.get("Packs_Per_Rack"), 0.0)
        if packs_per_rack <= 0:
            continue
        rack_mwh = (pack_kwh * packs_per_rack) / 1000.0
        if rack_mwh > 0:
            rack_map[int(rack_id)] = rack_mwh
    return rack_map


def apply_block_nameplate_recalc(
    df_blocks: pd.DataFrame,
    df_rack: pd.DataFrame,
    df_pack: pd.DataFrame,
    df_cell: pd.DataFrame,
) -> pd.DataFrame:
    if df_blocks is None or df_blocks.empty:
        return df_blocks

    cell_map = _cell_energy_wh(df_cell)
    pack_map = _pack_energy_kwh(df_pack, cell_map)
    rack_map = _rack_energy_mwh(df_rack, pack_map)
    if not rack_map:
        return df_blocks

    df = df_blocks.copy()
    updated = []
    for _, row in df.iterrows():
        rack_type_id = row.get("Rack_Type_Id")
        racks_per_block = _safe_float(row.get("Racks_Per_Block"), 0.0)
        if rack_type_id is None or pd.isna(rack_type_id) or racks_per_block <= 0:
            updated.append(None)
            continue
        rack_mwh = rack_map.get(int(rack_type_id))
        if not rack_mwh:
            updated.append(None)
            continue
        block_mwh = round(rack_mwh * racks_per_block, 3)
        updated.append(block_mwh if block_mwh > 0 else None)

    if "Block_Nameplate_Capacity_Mwh" in df.columns:
        df["Block_Nameplate_Capacity_Mwh"] = [
            upd if upd is not None else orig
            for upd, orig in zip(updated, df["Block_Nameplate_Capacity_Mwh"].tolist())
        ]
    return df


@lru_cache(maxsize=2)
def _load_nameplate_tables(path: str):
    xls = pd.ExcelFile(path)
    df_cell = pd.read_excel(xls, "battery_cell_type_314_data")
    df_pack = pd.read_excel(xls, "pack_type_314_data")
    df_rack = pd.read_excel(xls, "rack_type_314_data")
    df_blocks = pd.read_excel(xls, "dc_block_template_314_data")
    return df_cell, df_pack, df_rack, df_blocks


def get_standard_container_mwh(path: Optional[Path] = None) -> float:
    data_path = Path(path) if path else Path(DC_DATA_PATH)
    try:
        df_cell, df_pack, df_rack, df_blocks = _load_nameplate_tables(str(data_path))
        df_blocks = apply_block_nameplate_recalc(df_blocks, df_rack, df_pack, df_cell)
        df = df_blocks.copy()
        df = df[(df.get("Block_Form") == "container") & (df.get("Is_Active") == 1)]
        if df.empty:
            return 5.000
        pref = df[df.get("Is_Default_Option") == 1]
        if not pref.empty:
            df = pref
        df = df.sort_values("Block_Nameplate_Capacity_Mwh", ascending=False)
        val = _safe_float(df.iloc[0].get("Block_Nameplate_Capacity_Mwh"), 0.0)
        if val <= 0:
            return 5.000
        return round(val, 3)
    except Exception:
        return 5.000
