import os
import glob
from pathlib import Path

# 获取项目根目录 (即 calb_sizing_tool 文件夹的上一级)
PROJECT_ROOT = Path(__file__).parent.parent.absolute()

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"

# --- 智能文件查找逻辑 ---
def find_excel_file(pattern_glob: str, default_name: str) -> Path:
    """
    在 data 目录下搜索符合 pattern 的 Excel 文件。
    如果找不到，回退到 default_name 并会在后续读取时报错。
    """
    # 1. 尝试精确查找
    exact_path = DATA_DIR / default_name
    if exact_path.exists():
        return exact_path

    # 2. 尝试模糊查找 (例如忽略版本号差异)
    search_path = str(DATA_DIR / pattern_glob)
    candidates = glob.glob(search_path)
    
    if candidates:
        # 按文件名排序，取最后一个（通常是最新版本）
        found_path = Path(sorted(candidates)[-1])
        print(f"[Config] Auto-resolved data file: {found_path.name}")
        return found_path
    
    # 3. 找不到，返回默认路径（后续代码会报 FileNotFoundError）
    return exact_path

# --- 定义文件路径 ---

# AC 数据字典匹配模式: AC_Block_Data_Dictionary*.xlsx
AC_DATA_PATH = find_excel_file(
    "AC_Block_Data_Dictionary*.xlsx", 
    "AC_Block_Data_Dictionary_v1_1.xlsx"
)

# DC 数据字典匹配模式: ess_sizing_data_dictionary*dc*.xlsx
# 这样可以匹配 _automation, _autofit 等不同后缀
DC_DATA_PATH = find_excel_file(
    "ess_sizing_data_dictionary*dc*.xlsx",
    "ess_sizing_data_dictionary_v13_dc_automation.xlsx"
)

# --- 调试检查 ---
if not AC_DATA_PATH.exists():
    print(f"⚠️ 警告: 无法在 {DATA_DIR} 下找到 AC 数据文件。")

if not DC_DATA_PATH.exists():
    print(f"⚠️ 警告: 无法在 {DATA_DIR} 下找到 DC 数据文件。")