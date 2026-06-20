# 港股分钟线数据源策略

这份文档只回答一件事：港股分钟级 K 线默认该用哪个数据源，以及什么时候才允许回退到其它源。

如果阅读过程中需要回到总导航，见 [fundamental-doc-map.md](fundamental-doc-map.md)。

## 结论

- 默认主数据源：雪球
- 默认行为：只用雪球，不自动轮询其它源
- 显式回退源：AKShare / 东方财富
- 适用范围：港股 `1m / 5m / 15m / 30m / 60m`

原因很简单：

- 雪球对港股分钟线在这个仓库里的实际稳定性更好
- 自动把多个源都试一遍，会放大不确定性，也会拖慢运行
- 很多失败不是“源本身坏了”，而是 cookie、代理、限流这些局部环境问题

所以当前约定不是“每次多源探测”，而是：

- 先把雪球这条链路跑稳
- 只有调用方显式允许时，才回退到 `akshare`

## 当前公共入口

公共代码在 [src/chanlun/data/hk_minute_fetcher.py](../src/chanlun/data/hk_minute_fetcher.py)。

推荐调用入口：

```python
from chanlun.data.hk_minute_fetcher import fetch_hk_minute_with_policy

rows, used_source = fetch_hk_minute_with_policy(
    "03690",
    period="60",
    start="2026-01-01 09:30",
  adjust="",
    primary_source="xueqiu",
    fallback_sources=None,
)
```

如果你明确允许回退：

```python
rows, used_source = fetch_hk_minute_with_policy(
    "03690",
    period="60",
    start="2026-01-01 09:30",
  adjust="",
    primary_source="xueqiu",
    fallback_sources=("akshare",),
)
```

这里的约束是：

- `fetch_hk_minute(...)` 是单数据源、确定性调用
- `fetch_hk_minute_with_policy(...)` 才负责主源和可选回退策略
- 港股分钟线当前默认不复权；只有显式传 `qfq` 或 `hfq` 时才做复权

## 雪球链路要求

雪球分钟线需要有效登录态。

优先顺序：

1. 读取环境变量 `XUEQIU_COOKIE`
2. 若未设置，则尝试从本机浏览器自动读取雪球 cookie

推荐的最小环境变量：

```powershell
$env:XUEQIU_COOKIE = 'xq_a_token=REPLACE_ME; xqat=REPLACE_ME; u=REPLACE_ME'
```

辅助脚本：

- [scripts/export_xueqiu_cookie.py](../scripts/export_xueqiu_cookie.py)
- [scripts/xueqiu_env_example.ps1](../scripts/xueqiu_env_example.ps1)

另外要注意两点：

- API 查询里符号必须用裸数字，如 `03690`
- 页面 Referer 仍然可以用 `https://xueqiu.com/S/HK03690`

## 代理要求

本机如果开了 HTTPS 代理拦截，东财和雪球都可能出现异常。

港股分钟线 fetcher 已经内置以下处理：

- 清理 `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY`
- 设置 `NO_PROXY=*`

所以不要在外层脚本重复实现一套不同版本的代理清理逻辑；优先走公共 fetcher。

## 什么时候才回退到 AKShare

只在下面两类场景允许：

- 你明确接受雪球 cookie 当前不可用，但仍要尽快拿一版分钟线
- 你在做数据源对比、异常排查、历史回补

不建议把 AKShare 作为每次运行的自动第二选择，原因是：

- 会拉长抓取时间
- 会让日志和失败语义变得混乱
- 当主问题其实是 cookie 失效时，会掩盖真正要修的点

## 当前脚本约定

[scripts/run_hk_60m_chanlun_to_wechat.py](../scripts/run_hk_60m_chanlun_to_wechat.py) 已接入统一策略入口。

默认只用雪球：

```powershell
c:/sinba/stock/venv/Scripts/python.exe scripts/run_hk_60m_chanlun_to_wechat.py \
  --symbol 03690 \
  --name 美团 \
  --source xueqiu \
  --render-only
```

显式允许回退：

```powershell
c:/sinba/stock/venv/Scripts/python.exe scripts/run_hk_60m_chanlun_to_wechat.py \
  --symbol 03690 \
  --name 美团 \
  --source xueqiu \
  --fallback-source akshare \
  --render-only
```

## 实践建议

- 日常跑港股分钟线时，把雪球当唯一主源
- 先修 cookie 和代理，再考虑回退源
- 回退源是显式策略，不是默认行为
- 新脚本不要直接拼雪球 URL，也不要重新实现 cookie / proxy 逻辑，直接复用公共 fetcher