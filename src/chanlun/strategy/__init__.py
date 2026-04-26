"""
策略信号模块。

定义基于缠论结构的交易信号规则。
"""

from typing import List
from ..models import Bi, Zhongshu, FractalType


class SignalType:
    """信号类型常数"""
    BUY_FIRST = "buy_1"       # 一类买点
    BUY_SECOND = "buy_2"      # 二类买点
    BUY_THIRD = "buy_3"       # 三类买点
    SELL_FIRST = "sell_1"     # 一类卖点
    SELL_SECOND = "sell_2"    # 二类卖点
    SELL_THIRD = "sell_3"     # 三类卖点


def find_basic_buy_signal(bis: List[Bi], zhongshus: List[Zhongshu]) -> List[dict]:
    """
    寻找基础买信号。
    
    第一阶段暂不具体定义，只提供接口。
    后续可补充：
    - 一类买点
    - 二类买点
    - 三类买点
    - 背驰买点
    
    Returns:
        信号列表，每个信号包含时间、价格、类型、依据结构等
    """
    signals = []
    # TODO: 实现具体的信号识别逻辑
    return signals


def find_basic_sell_signal(bis: List[Bi], zhongshus: List[Zhongshu]) -> List[dict]:
    """
    寻找基础卖信号。
    
    Returns:
        信号列表
    """
    signals = []
    # TODO: 实现具体的信号识别逻辑
    return signals
