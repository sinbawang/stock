"""基于日 K 生成模拟分钟 K 线并可视化。

港股 03690 分钟线数据源缺失，本脚本演示：
1. 从日 K 数据生成模拟 60 分钟 K 线
2. 保存为可用于后续分析的数据格式
"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path


def simulate_minute_klines_from_daily(
    daily_csv: str,
    output_csv: str,
    bars_per_day: int = 8,  # 09:30-17:00 共 8 个 60 分钟
) -> None:
    """从日 K 生成模拟分钟 K 线。
    
    Args:
        daily_csv: 输入日 K CSV 路径
        output_csv: 输出分钟 K CSV 路径
        bars_per_day: 每日导出分钟数
    """
    rows = []
    with open(daily_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    minute_rows = []
    
    for daily in rows:
        ts = datetime.strptime(daily["ts"], "%Y-%m-%d")
        o = float(daily["open"])
        h = float(daily["high"])
        l = float(daily["low"])
        c = float(daily["close"])
        
        # 生成当日的 bars_per_day 根分钟 K（09:30 开始，每根 60 分钟）
        bar_prices = _generate_intraday_path(o, c, h, l, bars_per_day)
        
        for i, (bar_open, bar_high, bar_low, bar_close) in enumerate(bar_prices):
            hour = 9 + i + (i // 2)  # 近似：09:30, 10:30, ..., 16:30
            minute = 30 if i == 0 else 0
            bar_ts = ts.replace(hour=hour, minute=minute)
            
            minute_rows.append({
                "ts":     bar_ts.strftime("%Y-%m-%d %H:%M"),
                "open":   f"{bar_open:.2f}",
                "high":   f"{bar_high:.2f}",
                "low":    f"{bar_low:.2f}",
                "close":  f"{bar_close:.2f}",
                "volume": str(int(random.randint(1000000, 5000000))),
            })
    
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ts", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        writer.writerows(minute_rows)
    
    print(f"已生成 {len(minute_rows)} 根模拟 60 分钟 K 线到 {output_csv}")


def _generate_intraday_path(
    open_price: float,
    close_price: float,
    high_price: float,
    low_price: float,
    num_bars: int,
) -> list[tuple[float, float, float, float]]:
    """生成日内价格路径（num_bars 根 60 分钟 K）。
    
    简单算法：
    1. 平分开收两端价格
    2. 在 [低, 高] 范围内随机波动
    """
    bars = []
    prev_close = open_price
    
    for i in range(num_bars):
        # 线性插值目标收盘
        progress = (i + 1) / num_bars
        target_close = open_price + (close_price - open_price) * progress
        
        # 随机偏离目标
        bar_open = prev_close
        bar_close = target_close + random.uniform(-0.5, 0.5)
        
        # 确保在 [low, high] 范围内
        bar_high = max(bar_open, bar_close) + random.uniform(0, 2.0)
        bar_low = min(bar_open, bar_close) - random.uniform(0, 1.0)
        
        bar_high = min(bar_high, high_price)
        bar_low = max(bar_low, low_price)
        
        bars.append((bar_open, bar_high, bar_low, bar_close))
        prev_close = bar_close
    
    return bars


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="从日 K 生成模拟分钟 K 线")
    parser.add_argument("--daily-csv", default="data/03690_美团/day/3690_daily.csv", help="输入日 K CSV")
    parser.add_argument("--output-csv", default="data/03690_美团/60m/3690_60m_simulated.csv", help="输出分钟 K CSV")
    args = parser.parse_args()
    
    simulate_minute_klines_from_daily(args.daily_csv, args.output_csv)
