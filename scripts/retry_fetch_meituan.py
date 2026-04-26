"""按 1/2/4/8/16 分钟间隔重试抓取美团 60m K 线，成功立即停止。"""
import sys, time, traceback
from datetime import datetime
sys.path.insert(0, r"c:\sinba\stock\src")
from chanlun.data.hk_minute_fetcher import fetch_hk_minute, save_to_csv

waits = [60, 120, 240, 480, 960]  # seconds: 1,2,4,8,16 min
rows = None
for i, w in enumerate([0] + waits):
    if w:
        print(f"[{datetime.now():%H:%M:%S}] 等 {w}s 后第 {i+1} 次尝试", flush=True)
        time.sleep(w)
    try:
        print(f"[{datetime.now():%H:%M:%S}] 第 {i+1} 次抓取...", flush=True)
        rows = fetch_hk_minute("03690", period="60", start="2025-01-01", adjust="qfq")
        if rows:
            print(f"[{datetime.now():%H:%M:%S}] 成功 {len(rows)} 根", flush=True)
            break
        else:
            print("返回空", flush=True)
    except Exception as e:
        print(f"失败: {e}", flush=True)

if rows:
    save_to_csv(rows, r"data/03690/60m/03690_60m.csv")
    print("首:", rows[0])
    print("末:", rows[-1])
else:
    print("全部尝试失败", flush=True)
    sys.exit(1)
