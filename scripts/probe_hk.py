import ssl, json, random
from urllib.request import Request, build_opener, ProxyHandler, HTTPSHandler
from urllib.parse import urlencode

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ctx))

# 试试不同的港股代码格式
codes = ["03690", "hk03690", "hk000003690", "116.03690"]
for code in codes:
    try:
        params = urlencode({"param": f"{code},m60,,10", "r": f"{random.random():.6f}"})
        url = f"https://ifzq.gtimg.cn/appstock/app/kline/mkline?{params}"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        raw = opener.open(req, timeout=10).read().decode("utf-8")
        data = json.loads(raw)
        print(f"\n{code:15} -> {raw[:200]}")
    except Exception as e:
        print(f"{code:15} -> {type(e).__name__}: {str(e)[:80]}")
