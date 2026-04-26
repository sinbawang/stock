"""获取美团港股 3690 日 K 数据并保存 CSV（东方财富 API）"""
import csv, json, ssl
from urllib.request import Request, build_opener, ProxyHandler, HTTPSHandler
from urllib.parse import urlencode
from pathlib import Path

# 显式禁用代理 + 放宽 TLS 检查（开发环境，绕过证书拦截代理）
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE
opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl_ctx))

url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
params = {
    "secid":   "116.03690",
    "fields1": "f1,f2,f3,f4,f5,f6",
    "beg":     "20260303",
    "end":     "20260412",
    "lmt":     "500",
}
full_url = url + "?" + urlencode(params)
req = Request(full_url, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0",
    "Referer":    "https://quote.eastmoney.com/",
})
print("正在从东方财富 API 获取美团(03690)日 K 数据...")
with opener.open(req, timeout=20) as resp:
    payload = json.loads(resp.read().decode("utf-8"))
klines = (payload.get("data") or {}).get("klines") or []
print(f"获取 {len(klines)} 根 K 线")

rows = []
for k in klines:
    p = k.split(",")
    if len(p) < 7:
    rows.append({
        "ts":         p[0],
        "open":       p[1],
        "volume":     int(float(p[5])),
        "change_pct": p[8] if len(p) > 8 else "",
    })
outfile = "data/03690_美团/day/3690_daily.csv"
Path(outfile).parent.mkdir(parents=True, exist_ok=True)
with open(outfile, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["ts","open","high","low","close","volume","change_pct"])
    writer.writeheader()
    writer.writerows(rows)
print(f"已保存到 {outfile}\n")
print(f"{'日期':<13}{'开':>8}{'高':>8}{'低':>8}{'收':>8}{'量(股)':>14}{'涨跌%':>8}")
print("-" * 64)
for row in rows:
    print(f"{row['ts']:<13}{row['open']:>8}{row['high']:>8}{row['low']:>8}{row['close']:>8}{row['volume']:>14}{row['change_pct']:>8}")
"""获取美团港股 3690 日 K 数据并保存 CSV（腾讯财经 API）"""
import csv, json, ssl, re, random
from urllib.request import Request, build_opener, ProxyHandler, HTTPSHandler
from urllib.parse import urlencode
from pathlib import Path

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE
opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl_ctx))

# 腾讯财经港股历史 K 线 API
# param: hk<code>,day,<start>,<end>,<limit>,<adjust>
r_val = f"{random.random():.4f}"
url = (
    "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    f"?_var=kline_dayfqhk03690"
    f"&param=hk03690,day,2026-03-03,2026-04-12,500,qfq"
    f"&r={r_val}"
)
req = Request(url, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0",
    "Referer":    "https://gu.qq.com/",
})

print("正在从腾讯财经 API 获取美团(03690)港股日 K 数据...")
with opener.open(req, timeout=20) as resp:
    raw = resp.read().decode("utf-8")

# 返回格式: kline_dayfqhk03690 = {...json...}
# 去掉变量名赋值部分
m = re.search(r"=\s*(\{.*\})", raw, re.DOTALL)
if not m:
    raise ValueError(f"未能解析响应: {raw[:200]}")

payload = json.loads(m.group(1))

# 路径: data -> hk03690 -> day 或 qfqday
code_data = payload.get("data", {}).get("hk03690", {})
klines = code_data.get("qfqday") or code_data.get("day") or []

print(f"获取 {len(klines)} 根 K 线")

rows = []
for k in klines:
    # 格式: [日期, 开, 收, 高, 低, 量, ...]
    if len(k) < 5:
        continue
    rows.append({
        "ts":     k[0],
        "open":   k[1],
        "close":  k[2],
        "high":   k[3],
        "low":    k[4],
        "volume": k[5] if len(k) > 5 else 0,
    })

# 按日期升序
rows.sort(key=lambda r: r["ts"])

outfile = "data/03690_美团/day/3690_daily.csv"
Path(outfile).parent.mkdir(parents=True, exist_ok=True)
with open(outfile, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["ts","open","high","low","close","volume"])
    writer.writeheader()
    writer.writerows(rows)

print(f"已保存到 {outfile}\n")
print(f"{'日期':<13}{'开':>8}{'高':>8}{'低':>8}{'收':>8}{'量(股)':>14}")
print("-" * 60)
for row in rows:
    print(f"{row['ts']:<13}{row['open']:>8}{row['high']:>8}{row['low']:>8}{row['close']:>8}{row['volume']:>14}")
