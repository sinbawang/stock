# 买卖点飞书通知（buysell_notify）

当程序检测到缠论买卖点时，把信号推送到**飞书自定义机器人**。个人可用、免费、无需企业认证。

- 发送器：[`src/notify/feishu.py`](../../src/notify/feishu.py)
- 信号提取/去重/卡片：[`src/notify/signal_notifier.py`](../../src/notify/signal_notifier.py)
- 命令行入口：[`scripts/notify_signals.py`](../../scripts/notify_signals.py)
- 日度入口接入：[`scripts/run_a_share_daily_overview.py`](../../scripts/run_a_share_daily_overview.py)、[`scripts/run_h_share_daily_overview.py`](../../scripts/run_h_share_daily_overview.py)

---

## 1. 它做什么

- 扫描 `data/reports/<symbol>/<timeframe>/tech.json` 里的买卖点（`summary.signal_points` + `summary.forming_points`）。
- 覆盖全部点类型：一/二/三类买卖点、类一/类二买卖点。
- 同时推送**确认**与**预备/迹象**两种生命周期（预备=提前预警；可用 `--no-forming` 只推确认）。
- 自动跳过**已失效**的信号。
- **去重**：同一「标的 | 周期 | 方向 | 点类型 | 锚点时间 | 生命周期」只推一次，重复运行不会刷屏。
- 消息为飞书**交互卡片**：买绿 🟢 / 卖红 🔴，标题带数量，正文每行含「名称 代码 周期｜确认/预备·点类型 价 @ 锚点时间」。

> 说明：通知器只**读取现有 tech.json**，自己不跑缠论检测。请在生成/刷新 tech.json 之后再调用它。

---

## 2. 一次性配置（飞书机器人）

1. 在飞书里建一个群（自用也行，拉自己进去即可）。
2. 群右上角 **设置 → 群机器人 → 添加机器人 → 自定义机器人**。
3. 复制得到的 **webhook 地址**，形如：
   `https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
4. 安全设置（三选一或多选，建议至少开一个）：
   - **签名校验**：拿到一个密钥（secret），配到 `FEISHU_SIGN_SECRET`，程序会自动签名。
   - **自定义关键词**：若设了关键词，推送内容必须包含它；默认卡片标题含「提醒」，设关键词时建议用「提醒」或买卖点相关词。
   - IP 白名单：固定出口 IP 时可用。

> 区分：国内飞书是 `open.feishu.cn`；Lark 国际版是 `open.larksuite.com`，别混用。

---

## 3. 环境变量（凭据不入库）

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `FEISHU_WEBHOOK_URL` | 是 | 自定义机器人 webhook 地址 |
| `FEISHU_SIGN_SECRET` | 否 | 开启「签名校验」时的密钥 |

PowerShell（当前会话）：

```powershell
$env:FEISHU_WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/xxxx"
# $env:FEISHU_SIGN_SECRET = "xxxx"   # 仅在开启签名校验时需要
```

持久化（用户级，重开终端生效）：

```powershell
setx FEISHU_WEBHOOK_URL "https://open.feishu.cn/open-apis/bot/v2/hook/xxxx"
```

---

## 4. 命令行用法

```powershell
# 预览将推送的新信号（不发送、不改状态）
python scripts/notify_signals.py --dry-run

# 首次建立基线：把当前已有信号记为「已通知」，避免首跑一次性刷一堆历史信号
python scripts/notify_signals.py --seed-only

# 日常推送：只推新出现的买卖点（全部周期）
python scripts/notify_signals.py

# 只推指定周期（注意是 30m/5m/1m，不是 m30/m5/m1）
python scripts/notify_signals.py --timeframes 30m 5m 1m

# 只推确认买卖点，不推预备/迹象
python scripts/notify_signals.py --no-forming
```

参数说明：

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--reports-dir` | `data/reports` | 技术面报告根目录 |
| `--state-file` | `data/_meta/notify_state.json` | 去重状态文件 |
| `--timeframes` | 全部 | 仅扫描指定周期，如 `30m 5m 1m`；**不填=全部周期**（30m/5m/1m/15m/60m/day） |
| `--no-forming` | 关 | 只推确认，不推预备/迹象 |
| `--dry-run` | 关 | 只预览，不发送、不改状态 |
| `--seed-only` | 关 | 只记基线，不实际推送 |
| `--title` | 缠论买卖点提醒 | 卡片标题 |

---

## 5. 接入日度运行

`run_a_share_daily_overview.py` / `run_h_share_daily_overview.py` 都支持 `--notify`：

```powershell
python scripts/run_a_share_daily_overview.py --notify --notify-timeframes 30m 5m 1m
```

对应子参数：`--notify-state-file`、`--notify-timeframes`、`--notify-no-forming`、`--notify-dry-run`、`--notify-seed-only`。
缺少 `FEISHU_WEBHOOK_URL` 时只告警、不中断日度流程。

> 注意：日度脚本本身**不重算 intraday tech.json**，只读现有文件。若要 intraday（30m/5m/1m）实时推送，应在你的 intraday 生成流程**之后**单独调 `notify_signals.py`（周期带 `30m 5m 1m` 或不带=全部）。

---

## 6. 建议工作流

1. 配好 `FEISHU_WEBHOOK_URL`（如需签名再配 `FEISHU_SIGN_SECRET`）。
2. `--dry-run` 看一眼要推什么。
3. `--seed-only` 建基线（防首跑刷屏）。
4. 挂进定时任务：intraday 生成 tech.json 后调 `notify_signals.py --timeframes 30m 5m 1m`。

Windows 计划任务示例（每 5 分钟，盘中）：

```powershell
schtasks /Create /TN "buysell-notify" /SC MINUTE /MO 5 ^
  /TR "powershell -NoProfile -Command cd C:\sandbox\sinba\stock; python scripts\notify_signals.py --timeframes 30m 5m 1m"
```

---

## 7. 去重与状态

- 状态文件默认 `data/_meta/notify_state.json`，结构：`{"sent_keys": [...], "updated_at": "..."}`。
- 去重键含**生命周期**，因此同一个点「预备」推一次、「确认」再推一次（预备预警 + 确认提醒）。
- 想重置（重新从头推）直接删除状态文件；想避免历史信号刷屏则改用 `--seed-only` 重建基线。

---

## 8. 排错

| 现象 | 原因 / 处理 |
| --- | --- |
| `19001 incoming webhook access token invalid` | webhook 地址/ token 无效：到群机器人设置重新复制完整地址；确认机器人未被删；确认是 `open.feishu.cn` 而非 Lark |
| `19021 sign match fail` | 开了签名校验但密钥不对：核对 `FEISHU_SIGN_SECRET` |
| 关键词相关报错 | 机器人设了「自定义关键词」，推送内容需包含它；默认标题含「提醒」，或改 `--title` |
| `未配置飞书 webhook` | 没设 `FEISHU_WEBHOOK_URL`（或在别的终端设的、没传进当前进程） |
| 已推送 0 条 | 没有新信号（都被去重）、或 `--timeframes` 没覆盖、或该周期 tech.json 未更新 |
| 只推了 30m，没有 5m/1m | `--timeframes 30m` 只含 30m；要三个写 `--timeframes 30m 5m 1m` 或不带该参数 |

---

## 9. 测试

```powershell
python -m pytest tests/test_signal_notifier.py -q
```

覆盖：信号提取（跳过失效、标签映射、预备/确认）、去重（跨运行、预备与确认分别推）、`--seed-only` / `--dry-run`、卡片结构、飞书签名、发送重试。
