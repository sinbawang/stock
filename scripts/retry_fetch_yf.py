"""用 yfinance 抓美团 60m，按 1/2/4/8/16 分钟间隔重试。"""
import os, sys, time, csv
from datetime import datetime
from pathlib import Path

for v in ("HTTP_PROXY","HTTPS_PROXY","http_proxy","https_proxy","ALL_PROXY","all_proxy"):
    os.environ.pop(v, None)
os.environ["NO_PROXY"] = "*"

import yfinance as yf

waits = [0, 60, 120, 240, 480, 960]  # 0,1,2,4,8,16 min
df = None
for i, w in enumerate(waits):
    if w:
        print(f"[{datetime.now():%H:%M:%S}] sleep {w}s", flush=True)
        time.sleep(w)
    try:
        print(f"[{datetime.now():%H:%M:%S}] try #{i+1}", flush=True)
        # 重新 import 以清空 yfinance 内部限速状态
        import importlib, yfinance
        importlib.reload(yfinance)
        df = yfinance.download("3690.HK", interval="60m", period="730d",
                               auto_adjust=False, progress=False, threads=False)
        if df is not None and not df.empty:
            print(f"OK {len(df)} rows", flush=True)
            break
        print("empty", flush=True)
        df = None
    except Exception as e:
        print(f"fail: {type(e).__name__}: {e}", flush=True)

if df is None or df.empty:
    print("ALL FAILED", flush=True)
    sys.exit(1)

# yfinance multi-index column when single ticker → flatten
if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
    df.columns = df.columns.get_level_values(0)

out_path = Path(r"c:\sinba\stock\data\03690\60m\03690_60m.csv")
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["ts","open","high","low","close","volume"])
    for ts, row in df.iterrows():
        w.writerow([
            ts.strftime("%Y-%m-%d %H:%M"),
            float(row["Open"]), float(row["High"]),
            float(row["Low"]),  float(row["Close"]),
            int(row["Volume"]) if row["Volume"] == row["Volume"] else 0,
        ])
print(f"saved {len(df)} rows -> {out_path}", flush=True)
print("first:", df.index[0], "last:", df.index[-1], flush=True)
