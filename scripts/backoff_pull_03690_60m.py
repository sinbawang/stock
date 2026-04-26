"""按 1/2/4/8/16 分钟退避重试拉 03690 60m 全量。拿到立即停止。"""
import os, time, sys
for v in ("HTTP_PROXY","HTTPS_PROXY","http_proxy","https_proxy","ALL_PROXY","all_proxy"):
    os.environ.pop(v, None)
os.environ["NO_PROXY"] = "*"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from chanlun.data.hk_minute_fetcher import fetch_hk_minute, save_to_csv  # noqa: E402

WAITS = [0, 60, 120, 240, 480, 960]  # 立即 + 1/2/4/8/16 分钟
OUT = "data/03690_美团/60m/03690_60m_full.csv"

for i, wait in enumerate(WAITS):
    if wait:
        print(f"[{time.strftime('%H:%M:%S')}] sleep {wait}s before attempt {i+1}", flush=True)
        time.sleep(wait)
    print(f"[{time.strftime('%H:%M:%S')}] attempt {i+1} ...", flush=True)
    try:
        rows = fetch_hk_minute("03690", period="60", adjust="qfq")
        print(f"[{time.strftime('%H:%M:%S')}] SUCCESS rows={len(rows)}", flush=True)
        if rows:
            print(f"  first = {rows[0]}", flush=True)
            print(f"  last  = {rows[-1]}", flush=True)
            save_to_csv(rows, OUT)
        sys.exit(0)
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] FAIL {type(e).__name__}: {str(e)[:120]}", flush=True)

print("All attempts failed.", flush=True)
sys.exit(1)
