"""用 yfinance 获取港股 03690 60 分钟 K 线数据"""

import yfinance as yf
from datetime import datetime
import csv
from pathlib import Path

symbol = "3690.HK"
start = datetime(2026, 3, 3)
end = datetime(2026, 4, 12, 23, 59, 59)

print(f"尝试用 yfinance 获取 {symbol} 60 分钟 K 线")
print(f"时间范围: {start.date()} ~ {end.date()}")

try:
    data = yf.download(
        symbol,
        start=start,
        end=end,
        interval="60m",
        progress=False,
        timeout=30
    )
    
    print(f"\n✓ 成功！获取 {len(data)} 根 60 分钟 K 线")
    print(f"\n首条记录:")
    print(f"  时间: {data.index[0]}")
    print(f"  {data.iloc[0].to_dict()}")
    print(f"\n末条记录:")
    print(f"  时间: {data.index[-1]}")
    print(f"  {data.iloc[-1].to_dict()}")
    
    # 保存到 CSV
    output_path = "data/03690_美团/60m/3690_60m_yfinance.csv"
    
    rows = []
    for ts, row in data.iterrows():
        rows.append({
            "ts": ts.strftime("%Y-%m-%d %H:%M"),
            "open": f"{row['Open']:.2f}",
            "high": f"{row['High']:.2f}",
            "low": f"{row['Low']:.2f}",
            "close": f"{row['Close']:.2f}",
            "volume": int(row['Volume']),
        })
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ts", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"\n已保存到: {output_path}")
    
except Exception as e:
    print(f"\n✗ 失败: {type(e).__name__}")
    print(f"  {str(e)}")
    print(f"\n原因分析:")
    print(f"  - 可能被限流（Too Many Requests）")
    print(f"  - 或网络超时")
    print(f"\n解决方案:")
    print(f"  1. 稍后重试")
    print(f"  2. 申请 tushare token (https://tushare.pro)")
    print(f"  3. 使用代理或 VPN")
