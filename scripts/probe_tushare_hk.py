"""用 tushare 获取港股 03690 60 分钟 K 线并可视化"""

import os
import tushare as ts
import pandas as pd

TOKEN = os.environ.get("TUSHARE_TOKEN", "")
pro = ts.pro_api(TOKEN)

print("正在探测 tushare 可用的港股分钟线接口...\n")

symbol = "03690.HK"

# 方案 1：hk_daily（港股日线）
print("【1】hk_daily")
try:
    df = pro.hk_daily(ts_code=symbol, start_date="20260403", end_date="20260412")
    print(f"✓ 成功 {len(df)} 根  列={df.columns.tolist()[:6]}")
    print(df.head(2).to_string()); print()
except Exception as e:
    print(f"✗ {type(e).__name__}: {str(e)[:80]}\n")

# 方案 2：hk_mins（港股分钟线专用接口）
print("【2】hk_mins")
try:
    df = pro.hk_mins(ts_code=symbol, freq="60min", start_date="20260410 09:00:00", end_date="20260412 16:30:00")
    print(f"✓ 成功 {len(df)} 根  列={df.columns.tolist()[:6]}")
    print(df.head(2).to_string()); print()
except Exception as e:
    print(f"✗ {type(e).__name__}: {str(e)[:80]}\n")

# 方案 3：mins（通用分钟线，看是否支持港股）
print("【3】mins (通用)")
try:
    df = pro.mins(ts_code=symbol, freq="60min", start_date="20260410 09:00:00", end_date="20260412 16:30:00")
    print(f"✓ 成功 {len(df)} 根  列={df.columns.tolist()[:6]}")
    print(df.head(2).to_string()); print()
except Exception as e:
    print(f"✗ {type(e).__name__}: {str(e)[:80]}\n")

# 方案 4：query hk_mins（tushare 旧接口）
print("【4】query hk_mins")
try:
    df = pro.query("hk_mins", ts_code=symbol, freq="60min", start_date="20260410 09:00:00", end_date="20260412 16:30:00")
    print(f"✓ 成功 {len(df)} 根  列={df.columns.tolist()[:6]}")
    print(df.head(2).to_string()); print()
except Exception as e:
    print(f"✗ {type(e).__name__}: {str(e)[:80]}\n")

# 方案 5：stk_mins 接口
print("【5】stk_mins")
try:
    df = pro.stk_mins(ts_code=symbol, freq="60min", start_date="20260410 09:00:00", end_date="20260412 16:30:00")
    print(f"✓ 成功 {len(df)} 根  列={df.columns.tolist()[:6]}")
    print(df.head(2).to_string()); print()
except Exception as e:
    print(f"✗ {type(e).__name__}: {str(e)[:80]}\n")
