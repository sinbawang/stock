"""用 tushare hk_mins 接口批量分段获取港股 03690 60 分钟 K 线并可视化"""

import os
import time
import csv
from datetime import datetime, timedelta
from pathlib import Path

import tushare as ts
import mplfinance as mpf
import pandas as pd

TOKEN = os.environ.get("TUSHARE_TOKEN", "")
pro = ts.pro_api(TOKEN)

SYMBOL = "03690.HK"
START = datetime(2026, 3, 3)
END   = datetime(2026, 4, 12, 17, 0, 0)
OUTPUT_CSV = "data/03690_美团/60m/3690_60m_tushare.csv"
OUTPUT_PNG = "data/03690_美团/60m/3690_60m_tushare.png"

MAX_RETRIES = 5
RETRY_WAIT  = 65  # 超过 1 分钟，确保每分钟配额复位


def fetch_range_with_retry(start_dt: str, end_dt: str) -> pd.DataFrame:
    """单次宽范围请求，带自动重试"""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            df = pro.hk_mins(
                ts_code=SYMBOL,
                freq="60min",
                start_date=start_dt,
                end_date=end_dt,
            )
            return df
        except Exception as e:
            msg = str(e)
            if "每分钟" in msg or "每小时" in msg or "次" in msg:
                wait = RETRY_WAIT * attempt
                print(f"  ↻ 限流，{wait}s 后重试 (第{attempt}次)...")
                time.sleep(wait)
            else:
                print(f"  ✗ 其他错误: {msg[:80]}")
                return pd.DataFrame()
    return pd.DataFrame()


# ─── 1. 单次宽范围请求 ────────────────────────────────────

start_dt = START.strftime("%Y-%m-%d %H:%M:%S")
end_dt   = END.strftime("%Y-%m-%d %H:%M:%S")
print(f"正在获取 {SYMBOL} 60 分钟 K 线 ({start_dt} ~ {end_dt})...")
print("(单次请求完整区间，如遇限流自动等待重试)\n")

result = fetch_range_with_retry(start_dt, end_dt)

if result.empty:
    print("\n❌ 未获取到任何数据")
    print("原因：tushare hk_mins 免费账号有严格限流，已超出每小时配额")
    print("解决：等待约 1 小时后重试，或在 tushare.pro 充值提升权限")
    exit(1)

print(f"\n✓ 获取 {len(result)} 根 60 分钟 K 线")

# ─── 2. 去重、排序、规范列名 ──────────────────────────────

result = result.drop_duplicates(subset=["trade_time"])
result = result.sort_values("trade_time").reset_index(drop=True)
result = result.rename(columns={"trade_time": "ts"})
result = result[["ts", "open", "high", "low", "close", "vol"]].rename(columns={"vol": "volume"})

print(f"  首条: {result.iloc[0]['ts']}  收={result.iloc[0]['close']}")
print(f"  末条: {result.iloc[-1]['ts']}  收={result.iloc[-1]['close']}")

# ─── 3. 保存 CSV ──────────────────────────────────────────

Path("data").mkdir(exist_ok=True)
result.to_csv(OUTPUT_CSV, index=False)
print(f"\n✓ 已保存到 {OUTPUT_CSV}")

# ─── 4. 可视化 ──────────────────────────────────────────

print(f"\n正在生成 K 线图...")

df_plot = result.copy()
df_plot["ts"] = pd.to_datetime(df_plot["ts"])
df_plot = df_plot.set_index("ts")
df_plot = df_plot.rename(columns={
    "open": "Open", "high": "High",
    "low": "Low", "close": "Close", "volume": "Volume",
})
df_plot = df_plot[["Open", "High", "Low", "Close", "Volume"]].astype(float)

style = mpf.make_mpf_style(
    marketcolors=mpf.make_marketcolors(
        up="#e74c3c", down="#2ecc71",
        edge="inherit", wick="inherit", volume="inherit",
    ),
    gridstyle="--",
    facecolor="#f9fbfd",
    figcolor="#f9fbfd",
)

title = f"Meituan 03690 — 60 min Kline  ({START.date()} ~ {END.date()})"
mpf.plot(
    df_plot,
    type="candle",
    style=style,
    title=title,
    volume=True,
    mav=(5, 10, 20),
    tight_layout=True,
    savefig=dict(fname=OUTPUT_PNG, dpi=160, bbox_inches="tight"),
)

print(f"✓ K 线图已生成: {OUTPUT_PNG}")
