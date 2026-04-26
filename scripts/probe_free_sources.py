"""探测免费数据源对港股 03690 60 分钟 K 线的支持"""

import ssl, json, re, random
from urllib.request import Request, build_opener, ProxyHandler, HTTPSHandler

def make_opener():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return build_opener(ProxyHandler({}), HTTPSHandler(context=ctx))

opener = make_opener()

def get(url, headers=None):
    h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"}
    if headers:
        h.update(headers)
    req = Request(url, headers=h)
    return opener.open(req, timeout=15).read().decode("utf-8")

print("=" * 60)

# ── 1. 新浪财经 ──────────────────────────────────────────
print("\n【1】新浪财经 getKLineData (scale=60)")
try:
    url = ("https://quotes.sina.cn/cn/api/jsonp_v2.php/"
           "CN_MarketDataService.getKLineData"
           "?symbol=hk03690&scale=60&ma=no&datalen=200")
    raw = get(url)
    # jsonp 包裹: CN_MarketDataService.getKLineData(...)
    m = re.search(r'\((\[.*\])\)', raw, re.DOTALL)
    if m:
        data = json.loads(m.group(1))
        print(f"  ✓ 成功！{len(data)} 根 K 线")
        if data:
            print(f"  首条: {data[0]}")
            print(f"  末条: {data[-1]}")
    else:
        print(f"  ○ 无法解析，原始前200字符：{raw[:200]}")
except Exception as e:
    print(f"  ✗ {type(e).__name__}: {str(e)[:80]}")

# ── 2. 新浪财经另一接口 ──────────────────────────────────
print("\n【2】新浪财经 finance/CN_MarketData")
try:
    url = ("https://finance.sina.com.cn/realstock/company/hk03690/hisdata/"
           "klc_60.js?d=2026-04-10")
    raw = get(url, {"Referer": "https://finance.sina.com.cn/"})
    print(f"  原始前300字符：{raw[:300]}")
except Exception as e:
    print(f"  ✗ {type(e).__name__}: {str(e)[:80]}")

# ── 3. 网易财经 ──────────────────────────────────────────
print("\n【3】网易财经 quotes.money.163.com")
try:
    url = ("http://quotes.money.163.com/cjmx/2026/20260410/0HK03690.xls")
    raw = get(url)
    print(f"  原始前200字符：{raw[:200]}")
except Exception as e:
    print(f"  ✗ {type(e).__name__}: {str(e)[:80]}")

# ── 4. 雪球 ────────────────────────────────────────────
print("\n【4】雪球 xueqiu.com (需 cookie)")
try:
    url = ("https://stock.xueqiu.com/v5/stock/chart/kline.json"
           "?symbol=03690&begin=1740931200000&period=60m&type=before&count=200")
    raw = get(url, {"Referer": "https://xueqiu.com/"})
    data = json.loads(raw)
    items = data.get("data", {}).get("item", [])
    print(f"  {len(items)} 根 K 线  (无 token 可能返回空)")
    print(f"  原始前150字符：{raw[:150]}")
except Exception as e:
    print(f"  ✗ {type(e).__name__}: {str(e)[:80]}")

# ── 5. futu-api 是否已安装 ────────────────────────────────
print("\n【5】Futu OpenAPI SDK")
try:
    import futu
    print(f"  ✓ futu-api 已安装: {futu.__version__}")
    print("  需要本地运行 FutuOpenD 网关 + 富途账号")
except ImportError:
    print("  ✗ 未安装 (pip install futu-api)")
    print("  免费方案：注册富途/moomoo账号（免费开户）+ 下载 FutuOpenD 桌面程序")
    print("  优点：支持港股完整历史分钟线，无费用")
