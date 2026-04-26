"""
Data structures for Chan theory analysis.

Defines: Bar, NormalizedBar, Fractal, Bi, Zhongshu
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class FractalType(str, Enum):
    """分型类型"""
    TOP = "top"      # 顶分型
    BOTTOM = "bottom"  # 底分型


class BiDirection(str, Enum):
    """笔的方向"""
    UP = "up"        # 向上
    DOWN = "down"    # 向下


@dataclass
class Bar:
    """单根 K 线，基础行情单位"""
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0

    def __post_init__(self):
        if self.high < self.low:
            raise ValueError(f"Invalid bar: high({self.high}) < low({self.low})")


@dataclass
class NormalizedBar:
    """
    去包含后的标准化 K 线。
    
    通过包含关系合并得到，保留原始 K 线索引以支持回溯。
    """
    idx: int                      # 标准化后的序列索引
    high: float
    low: float
    ts_start: datetime
    ts_end: datetime
    ts_high: Optional[datetime] = None
    ts_low: Optional[datetime] = None
    src_indices: List[int] = field(default_factory=list)  # 对应的原始 K 线索引列表
    direction: Optional[str] = None  # 当前处理方向 ("up" 或 "down")

    def __post_init__(self):
        if self.high < self.low:
            raise ValueError(
                f"NormalizedBar invalid: high({self.high}) < low({self.low})"
            )
        if self.ts_high is None:
            self.ts_high = self.ts_end
        if self.ts_low is None:
            self.ts_low = self.ts_end


@dataclass
class Fractal:
    """
    分型（顶或底）。
    
    基于标准化 K 线序列判断，中心 K 线为参考。
    """
    fx_id: int                   # 分型全局编号
    fx_type: FractalType         # 顶 or 底
    ts: datetime                 # 分型时间
    price: float                 # 分型中心价格（high for top, low for bottom）
    center_bar_idx: int          # 中心标准化 K 线索引
    high: float                  # 分型中的最高价
    low: float                   # 分型中的最低价

    def is_top(self) -> bool:
        return self.fx_type == FractalType.TOP

    def is_bottom(self) -> bool:
        return self.fx_type == FractalType.BOTTOM


@dataclass
class Bi:
    """
    笔（从一个分型到下一个反向分型）。
    
    成笔条件：
    - 起点和终点是类型相反的分型
    - 至少间隔 1 根标准化 K 线
    - 涵盖的分型可能在末端被替换（浮筑）直到反向分型出现
    """
    bi_id: int                   # 笔全局编号
    direction: BiDirection       # 向上 or 向下
    start_fx_id: int             # 起始分型 ID
    end_fx_id: int               # 结束分型 ID
    start_ts: datetime
    end_ts: datetime
    high: float                  # 笔的最高价
    low: float                   # 笔的最低价
    norm_bar_range: tuple        # (start_idx, end_idx) 标准化 K 线覆盖范围
    is_confirmed: bool = False   # 是否已确认（反向分型出现后）

    def is_up(self) -> bool:
        return self.direction == BiDirection.UP

    def is_down(self) -> bool:
        return self.direction == BiDirection.DOWN


@dataclass
class Zhongshu:
    """
    中枢（至少 3 笔的价格重叠）。
    
    由连续 3 笔及其延伸形成的结构。
    中枢区间 = max(各笔的 low) 到 min(各笔的 high)
    """
    zs_id: int                   # 中枢全局编号
    start_bi_id: int             # 起始笔 ID（参与中枢的第一笔）
    end_bi_id: int               # 结束笔 ID（最后一笔）
    zs_low: float                # 中枢下沿
    zs_high: float               # 中枢上沿
    peak_low: float              # 中枢涉及的所有笔的最低点
    peak_high: float             # 中枢涉及的所有笔的最高点
    start_ts: datetime
    end_ts: datetime
    bi_ids: List[int] = field(default_factory=list)  # 参与的笔 ID 列表
    is_terminated: bool = False  # 是否已终结

    @property
    def width(self) -> float:
        """中枢宽度"""
        return self.zs_high - self.zs_low
