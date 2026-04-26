"""探测新浪/腾讯/网易等来源对汇川技术 60m K 线的支持情况。"""

from __future__ import annotations

import json
import re
import ssl
from urllib.parse import urlencode
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener


def make_opener():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return build_opener(ProxyHandler({}), HTTPSHandler(context=ctx))


def fetch(opener, url: str, headers: dict | None = None) -> str:
    h = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0",
        "Accept": "*/*",
    }
    if headers:
        h.update(headers)
    req = Request(url, headers=h)
    with opener.open(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def test_tencent_ifzq(opener):
    url = (
        "https://ifzq.gtimg.cn/appstock/app/kline/mkline?"
        + urlencode({"param": "sz300124,m60,,500"})
    )
    raw = fetch(opener, url, {"Referer": "https://gu.qq.com/"})
    data = json.loads(raw)
    arr = data.get("data", {}).get("sz300124", {}).get("m60", [])
    if not arr:
        return False, "腾讯 ifzq 返回空"
    return True, f"腾讯 ifzq 成功: {len(arr)} 根, 首条={arr[0]}"


def test_sina_cn_market(opener):
    url = (
        "https://quotes.sina.cn/cn/api/jsonp_v2.php/"
        "CN_MarketDataService.getKLineData"
        "?symbol=sz300124&scale=60&ma=no&datalen=500"
    )
    raw = fetch(opener, url, {"Referer": "https://finance.sina.com.cn/"})
    m = re.search(r"\((\[.*\]|\{.*\})\)", raw, re.DOTALL)
    if not m:
        return False, f"新浪返回异常: {raw[:120]}"
    payload = m.group(1)
    if payload.startswith("{"):
        return False, f"新浪接口报错: {payload[:120]}"
    arr = json.loads(payload)
    if not arr:
        return False, "新浪返回空"
    return True, f"新浪成功: {len(arr)} 根, 首条={arr[0]}"


def test_netease(opener):
    url = "http://quotes.money.163.com/service/chddata.html?code=1300124&start=20260303&end=20260412&fields=TCLOSE;HIGH;LOW;TOPEN;VOTURNOVER"
    raw = fetch(opener, url)
    if "日期" in raw and "收盘价" in raw:
        lines = [x for x in raw.splitlines() if x.strip()]
        return True, f"网易导出接口可用(通常日线): {len(lines)-1} 行"
    return False, f"网易返回异常: {raw[:120]}"


def main():
    opener = make_opener()

    tests = [
        ("腾讯 ifzq m60", test_tencent_ifzq),
        ("新浪 KLineData m60", test_sina_cn_market),
        ("网易 chddata", test_netease),
    ]

    for name, fn in tests:
        try:
            ok, msg = fn(opener)
            status = "OK" if ok else "FAIL"
            print(f"[{status}] {name}: {msg}")
        except Exception as e:
            print(f"[FAIL] {name}: {type(e).__name__}: {str(e)[:160]}")


if __name__ == "__main__":
    main()
