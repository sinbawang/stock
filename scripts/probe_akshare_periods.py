"""探测 akshare.stock_hk_hist 支持的 period 参数"""

import akshare as ak

symbol = "03690"
start_date = "2026-04-10"
end_date = "2026-04-12"

periods = [
    "daily", "day", "d",
    "1h", "60m", "hour",
    "30m", "15m", "5m", "1m",
    "week", "w", "month", "m"
]

print(f"测试 akshare.stock_hk_hist('{symbol}') 支持的 period 参数：\n")

for period in periods:
    try:
        df = ak.stock_hk_hist(symbol=symbol, start_date=start_date, end_date=end_date, period=period)
        if len(df) > 0:
            print(f"✓ period='{period:8}' -> {len(df)} 根 K 线，列={df.columns.tolist()}")
        else:
            print(f"○ period='{period:8}' -> 0 根 K 线")
    except KeyError as e:
        print(f"✗ period='{period:8}' -> KeyError: {str(e)[:50]}")
    except Exception as e:
        print(f"✗ period='{period:8}' -> {type(e).__name__}: {str(e)[:40]}")

print("\n结论：akshare stock_hk_hist 支持的级别列表如上")
