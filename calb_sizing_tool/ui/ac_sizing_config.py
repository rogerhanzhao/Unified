"""
AC Sizing配置和推荐引擎
基于DC Block数量生成三种标准搭配方案 (1:1, 1:2, 1:4)
"""
import math
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class PCSRecommendation:
    """PCS推荐配置"""
    pcs_count: int  # 每个AC Block中的PCS数量
    pcs_kw: int     # 每个PCS的功率(kW)
    total_kw: int   # 总功率(kW)
    
    @property
    def readable(self) -> str:
        return f"{self.pcs_count} × {self.pcs_kw}kW = {self.total_kw}kW"


@dataclass
class ACBlockRatioOption:
    """AC Block搭配方案"""
    ratio: str                      # "1:1", "1:2", "1:4"
    ac_block_count: int             # AC Block数量
    dc_blocks_per_ac: List[int]     # 每个AC Block连接的DC Block数
    pcs_recommendations: List[PCSRecommendation]  # PCS推荐列表
    description: str = ""
    is_recommended: bool = False
    
    @property
    def readable_description(self) -> str:
        avg_dc = sum(self.dc_blocks_per_ac) / len(self.dc_blocks_per_ac) if self.dc_blocks_per_ac else 0
        return f"{self.ratio} - {self.ac_block_count} AC Blocks, ~{avg_dc:.1f} DC Blocks each"


def generate_ac_sizing_options(
    dc_blocks_total: int,
    target_mw: float,
    target_mwh: float,
    dc_block_mwh: float = 5.0
) -> List[ACBlockRatioOption]:
    """
    根据DC Block数量生成三种标准搭配方案
    
    Args:
        dc_blocks_total: DC Block总数 (20ft container)
        target_mw: POI功率需求 (MW)
        target_mwh: POI能量需求 (MWh)
        dc_block_mwh: 每个DC Block的容量 (MWh), 默认5.0
    
    Returns:
        三种搭配方案的列表
    """
    options = []
    
    # ========== Option A: 1:1 搭配 ==========
    ac_blocks_a = dc_blocks_total
    dc_per_ac_a = [1] * ac_blocks_a if ac_blocks_a > 0 else []
    
    # 推荐PCS配置: 小功率
    pcs_recommendations_a = [
        PCSRecommendation(pcs_count=1, pcs_kw=1250, total_kw=1250),
        PCSRecommendation(pcs_count=2, pcs_kw=690, total_kw=1380),  # 非标准但参考
    ]
    
    option_a = ACBlockRatioOption(
        ratio="1:1",
        ac_block_count=ac_blocks_a,
        dc_blocks_per_ac=dc_per_ac_a,
        pcs_recommendations=pcs_recommendations_a,
        description="高灵活性，每个DC Block配一个AC Block。适合小型或分布式部署。",
        is_recommended=dc_blocks_total <= 4
    )
    options.append(option_a)
    
    # ========== Option B: 1:2 搭配 ==========
    ac_blocks_b = math.ceil(dc_blocks_total / 2)
    dc_per_ac_b = evenly_distribute(dc_blocks_total, ac_blocks_b)
    
    # 推荐PCS配置: 中功率
    # 每个AC Block应该有2-3个PCS
    pcs_recommendations_b = [
        PCSRecommendation(pcs_count=2, pcs_kw=1250, total_kw=2500),
        PCSRecommendation(pcs_count=3, pcs_kw=900, total_kw=2700),   # 近似
    ]
    
    option_b = ACBlockRatioOption(
        ratio="1:2",
        ac_block_count=ac_blocks_b,
        dc_blocks_per_ac=dc_per_ac_b,
        pcs_recommendations=pcs_recommendations_b,
        description="成本优化，2个DC Block配1个AC Block。通常推荐方案，平衡可靠性和成本。",
        is_recommended=True  # 默认推荐
    )
    options.append(option_b)
    
    # ========== Option C: 1:4 搭配 ==========
    ac_blocks_c = math.ceil(dc_blocks_total / 4)
    dc_per_ac_c = evenly_distribute(dc_blocks_total, ac_blocks_c)
    
    # 推荐PCS配置: 大功率，需要更多PCS或更高功率
    pcs_recommendations_c = [
        PCSRecommendation(pcs_count=3, pcs_kw=1500, total_kw=4500),
        PCSRecommendation(pcs_count=4, pcs_kw=1250, total_kw=5000),
        PCSRecommendation(pcs_count=4, pcs_kw=1500, total_kw=6000),  # 有超配
    ]
    
    option_c = ACBlockRatioOption(
        ratio="1:4",
        ac_block_count=ac_blocks_c,
        dc_blocks_per_ac=dc_per_ac_c,
        pcs_recommendations=pcs_recommendations_c,
        description="高度集成，4个DC Block配1个AC Block。适合大型项目，占地最小。",
        is_recommended=dc_blocks_total >= 8
    )
    options.append(option_c)
    
    return options


def evenly_distribute(total: int, buckets: int) -> List[int]:
    """
    均衡分配total个项目到buckets个桶中
    
    示例:
        evenly_distribute(6, 4) -> [2, 1, 1, 2] 或 [2, 2, 1, 1] 等
        evenly_distribute(7, 3) -> [3, 2, 2] 或 [2, 3, 2] 等
    """
    if buckets <= 0:
        return []
    
    base = total // buckets
    remainder = total % buckets
    
    result = []
    for i in range(buckets):
        if i < remainder:
            result.append(base + 1)
        else:
            result.append(base)
    
    return result


def calculate_optimal_pcs_rating(
    dc_blocks_in_ac_block: int,
    dc_block_mwh: float,
    pcs_per_ac_block: int,
    transformer_efficiency: float = 0.9,
    pcs_efficiency: float = 0.97
) -> float:
    """
    根据DC Block数量计算最优的PCS功率
    
    Args:
        dc_blocks_in_ac_block: AC Block中的DC Block数
        dc_block_mwh: 每个DC Block的容量(MWh)
        pcs_per_ac_block: AC Block中的PCS数量
        transformer_efficiency: 变压器效率
        pcs_efficiency: PCS效率
    
    Returns:
        推荐的PCS功率(kW), 基于DC能量和系统参数
    """
    # DC总容量
    dc_total_mwh = dc_blocks_in_ac_block * dc_block_mwh
    
    # 假设一个合理的discharge时间(4小时)
    discharge_hours = 4.0
    
    # 所需功率 = 容量 / 时间 / 效率
    required_power_mw = dc_total_mwh / discharge_hours / (pcs_efficiency * transformer_efficiency)
    required_power_kw = required_power_mw * 1000
    
    # 向上圆整到最近的标准规格
    standard_ratings = [1000, 1250, 1500, 1725, 2000, 2500, 3000, 3500, 4000, 4500, 5000]
    optimal_kw = min(r for r in standard_ratings if r >= required_power_kw)
    
    return optimal_kw


def suggest_pcs_count_and_rating(
    dc_blocks_per_ac: int,
    target_power_mw: float,
    ac_block_count: int,
    safety_factor: float = 1.1
) -> Tuple[int, int]:
    """
    基于DC Block数和目标功率，推荐PCS数量和功率规格
    
    Args:
        dc_blocks_per_ac: AC Block中的DC Block数
        target_power_mw: 目标功率需求(MW)
        ac_block_count: AC Block总数
        safety_factor: 安全系数(默认1.1，即110%)
    
    Returns:
        (pcs_count, pcs_kw): 推荐的PCS数量和单个PCS功率(kW)
    """
    # 每个AC Block需要的功率
    power_per_ac_mw = target_power_mw / ac_block_count * safety_factor
    power_per_ac_kw = power_per_ac_mw * 1000
    
    # 尝试标准规格，找到最佳组合
    standard_ratings = [1000, 1250, 1500, 1725, 2000, 2500]
    best_pcs_count = 2
    best_pcs_kw = 1250
    best_fit_error = float('inf')
    
    for pcs_kw in standard_ratings:
        for pcs_count in [1, 2, 3, 4, 5, 6]:
            total_kw = pcs_count * pcs_kw
            error = abs(total_kw - power_per_ac_kw)
            
            if error < best_fit_error and total_kw >= power_per_ac_kw:
                best_fit_error = error
                best_pcs_count = pcs_count
                best_pcs_kw = pcs_kw
    
    return best_pcs_count, best_pcs_kw

