"""检查数据源包及其港股 60 分钟 K 线支持"""

print("=" * 60)
print("检查已安装的数据源包")
print("=" * 60)

packages = ["akshare", "tushare", "pandas_datareader", "yfinance"]
for pkg in packages:
    try:
        mod = __import__(pkg)
        ver = getattr(mod, "__version__", "已装")
        print(f"✓ {pkg:20} {ver}")
    except ImportError:
        print(f"✗ {pkg:20} 未安装")

print("\n" + "=" * 60)
print("数据源对比（港股 60 分钟 K 线支持）")
print("=" * 60)

sources = {
    "akshare": {
        "支持港股": "✓ (多个接口)",
        "分钟线": "✗ 仅支持日线及以上",
        "需要token": "✗",
        "申请方式": "-",
        "备注": "高频更新，接口最多"
    },
    "tushare": {
        "支持港股": "✓ (需付费)",
        "分钟线": "?未知",
        "需要token": "✓ (免费注册)",
        "申请方式": "https://tushare.pro (邮箱注册)",
        "备注": "国内最大数据库，付费港股"
    },
    "yfinance": {
        "支持港股": "✓ (3690.HK)",
        "分钟线": "✓ 支持 1m/60m",
        "需要token": "✗",
        "申请方式": "-",
        "备注": "免费但容易被限流"
    },
    "同花顺 iFinD": {
        "支持港股": "✓",
        "分钟线": "✓ 支持",
        "需要token": "✓ (付费会员)",
        "申请方式": "同花顺官网充值会员",
        "备注": "需付费，~5000元/年"
    },
    "平安证券": {
        "支持港股": "✓",
        "分钟线": "✓ 支持",
        "需要token": "✓ (需开户)",
        "申请方式": "平安证券开户 + 获取 API key",
        "备注": "需证券账户，API 文档不完整"
    },
    "东方财富": {
        "支持港股": "✓",
        "分钟线": "? 网页有，API不明确",
        "需要token": "✗",
        "申请方式": "-",
        "备注": "国内股票数据，港股不清楚"
    }
}

for src, info in sources.items():
    print(f"\n【{src}】")
    for k, v in info.items():
        print(f"  {k:15} {v}")

print("\n" + "=" * 60)
print("推荐方案")
print("=" * 60)
print("""
方案 1（免费，推荐）：
  - 用 yfinance 获取港股 03690 分钟线（可能无法突破限流）
  - 命令: pip install yfinance
  - 无需 token

方案 2（可能可行）：
  - 安装 tushare + 申请免费 token
  - 命令: pip install tushare
  - 申请: https://tushare.pro (注册邮箱，免费额度有限)

方案 3（长期）：
  - 开通平安证券或同花顺，获得 API key
  - 同花顺会员费较贵（~5000元/年）
  - 平安需要有证券账户

推荐先尝试方案 1/2，我立即测试结果。
""")
