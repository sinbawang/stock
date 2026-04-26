"""尝试用 akshare 获取港股 03690 60 分钟 K 线"""

import akshare as ak
from datetime import datetime
import pandas as pd

print("=" * 60)
print("尝试 akshare 港股 60 分钟 K 线")
print("=" * 60)

symbol = "03690"  # 美团
start_date = "2026-03-03"
end_date = "2026-04-12"

# 尝试方案 1：hk_fq_kline（港股复权 K 线，通常支持日线）
print("\n【方案 1】hk_fq_kline (港股复权 K 线)")
try:
    df = ak.hk_fq_kline(symbol=symbol, start_date=start_date, end_date=end_date, adjust="qfq")
    print(f"✓ 成功！获取 {len(df)} 根 K 线")
    print(f"  列名：{df.columns.tolist()}")
    print(f"\n首条：\n{df.iloc[0]}")
except Exception as e:
    print(f"✗ 失败：{type(e).__name__}: {str(e)[:100]}")

# 尝试方案 2：hk_kline（港股 K 线，通常支持日线）
print("\n【方案 2】hk_kline (港股 K 线)")
try:
    df = ak.hk_kline(symbol=symbol, start_date=start_date, end_date=end_date, period="daily")
    print(f"✓ 成功！获取 {len(df)} 根 K 线")
    print(f"  列名：{df.columns.tolist()}")
    print(f"\n首条：\n{df.iloc[0]}")
except Exception as e:
    print(f"✗ 失败：{type(e).__name__}: {str(e)[:100]}")

# 尝试方案 3：hk_hist（历史行情，看是否支持分钟级）
print("\n【方案 3】hk_hist (港股历史行情)")
try:
    df = ak.hk_hist(symbol=f"HK{symbol}", start_date=start_date, end_date=end_date, period="60m")
    print(f"✓ 成功！获取 {len(df)} 根 K 线")
    print(f"  列名：{df.columns.tolist()}")
    print(f"\n首条：\n{df.iloc[0]}")
except Exception as e:
    print(f"✗ 失败：{type(e).__name__}: {str(e)[:100]}")

# 尝试方案 4：stock_hk_hist（港股历史行情别名）
print("\n【方案 4】stock_hk_hist (港股历史)")
try:
    df = ak.stock_hk_hist(symbol=symbol, start_date=start_date, end_date=end_date, period="60m")
    print(f"✓ 成功！获取 {len(df)} 根 K 线")
    print(f"  列名：{df.columns.tolist()}")
    print(f"\n首条：\n{df.iloc[0]}")
except Exception as e:
    print(f"✗ 失败：{type(e).__name__}: {str(e)[:100]}")

# 查看 akshare 可用函数
print("\n【可用函数列表】")
print("包含 'hk' 的 akshare 接口：")
ak_funcs = [x for x in dir(ak) if "hk" in x.lower()]
for func in ak_funcs[:15]:
    print(f"  - {func}")
if len(ak_funcs) > 15:
    print(f"  ... 还有 {len(ak_funcs) - 15} 个")
