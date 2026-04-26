"""直接打 eastmoney API 看 03690 60m 全量根数（akshare 内部其实就是这个调用）。"""
import os, time
for v in ("HTTP_PROXY","HTTPS_PROXY","http_proxy","https_proxy","ALL_PROXY","all_proxy"):
    os.environ.pop(v, None)
os.environ["NO_PROXY"] = "*"

import requests

url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
params = {
    "fields1": "f1,f2,f3,f4,f5,f6",
    "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
    "ut": "bd1d9ddb04089700cf9c27f6f7426281",
    "klt": "60",
    "fqt": 1,
    "secid": "116.03690",
    "beg": "0",
    "end": "20500000",
    "lmt": "100000",
}
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0",
    "Referer": "https://quote.eastmoney.com/",
}
for attempt in range(6):
    try:
        r = requests.get(url, params=params, headers=headers, timeout=30)
        data = r.json()
        klines = (data.get("data") or {}).get("klines") or []
        print(f"attempt {attempt}: rows={len(klines)}")
        if klines:
            print("first:", klines[0])
            print("last:", klines[-1])
        break
    except Exception as e:
        print(f"attempt {attempt} {type(e).__name__}: {str(e)[:120]}")
        time.sleep(3 + attempt * 2)
