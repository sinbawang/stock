"""继续探测 - 新浪、雪球、longbridge 等"""

import ssl, json, re, time, random
from urllib.request import Request, build_opener, ProxyHandler, HTTPSHandler

def make_opener():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return build_opener(ProxyHandler({}), HTTPSHandler(context=ctx))

opener = make_opener()

def get(url, headers=None):
    h = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
    }
    if headers:
        h.update(headers)
    try:
        req = Request(url, headers=h)
        raw = opener.open(req, timeout=12).read().decode("utf-8")
        return raw
    except Exception as e:
        return f"ERROR:{type(e).__name__}:{str(e)[:80]}"

# ── 1. 新浪 hk 分钟线（另一格式）
print("\n【1】新浪 HK 分时接口")
for sym in ["hk_03690", "hk03690", "HK0000003690"]:
    url = f"https://hq.sinajs.cn/list=hkHK{sym.replace('hk','').replace('HK','').zfill(5)}_60"
    r = get(url)
    print(f"  {sym}: {r[:120]}")

# ── 2. 新浪新版 K 线接口
print("\n【2】新浪新版 hqapi")
url = "https://hqapi.eastmoney.com/nemo/qtjs/getHisKData?secid=116.03690&klt=60&beg=20260403&end=20260412&fields1=f1,f2,f3,f5&fields2=f51,f52,f53,f54,f55,f56"
r = get(url)
print(f"  {r[:200]}")

# ── 3. Yahoo Finance (直接 API 不走 yfinance 库)
print("\n【3】Yahoo Finance 直接 API")
url = ("https://query1.finance.yahoo.com/v8/finance/chart/3690.HK"
       "?interval=60m&range=30d&includePrePost=false")
r = get(url, {"Accept": "application/json"})
print(f"  {r[:300]}")

# ── 4. 富途 (OpenD 本地网关) 检查是否运行
import socket
print("\n【4】检查 Futu OpenD 本地网关是否运行 (port 11111)")
try:
    s = socket.create_connection(("127.0.0.1", 11111), timeout=2)
    s.close()
    print("  ✓ FutuOpenD 已在本地运行！可直接用 futu-api 获取数据")
except:
    print("  ✗ FutuOpenD 未运行")
    print("  → 开户方式：moomoo.com (免费) 或 futunn.com (香港/新加坡账号)")

# ── 5. Longbridge OpenAPI (长桥证券, 免费开户)
print("\n【5】Longbridge 可用性")
try:
    import longbridge
    print(f"  ✓ longbridge SDK 已安装")
except ImportError:
    print("  ✗ 未安装 (pip install longbridge)")
    print("  → 免费开户：longbridgeapp.com (国内可用，支持港股分钟线)")
    print("  → 优点：免费每月 10000 次历史 K 线请求，支持 1m/5m/15m/30m/60m")
