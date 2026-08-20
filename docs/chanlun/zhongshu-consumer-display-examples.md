# 中枢消费展示对照示例

本页把 `zhongshu` 已经整理出的页内真实卡片，继续反推成下游最关心的三类展示位：

1. `tech.json` 应该如何保留主口径、观察态和辅助态。
2. 报告文案应该如何表达“去向候选 / 节奏监视 / 预警未确认”。
3. 小程序卡片和图表标签应该如何避免越级确认。

本页不重复中枢理论定义；理论层看 [zhongshu-core-spec.md](zhongshu-core-spec.md)，review 入口看 [zhongshu-review-entry.md](zhongshu-review-entry.md)，页内案例本体看 [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md)。

当前示例级别优先顺序：尽可能优先使用 `1m / 5m / 30m / day` 这条链；当前已经稳定覆盖 `1m / 5m / 30m / day映射`，其中 `1m` 已覆盖 watch/pending、completed_then_new_type、预警前态代理与 confirmed 四类消费示例。

## 1. 使用方式

建议按以下顺序使用本页：

1. 先找对应案例类型。
2. 再看 `tech.json` 推荐表达。
3. 再看报告/小程序允许文案。
4. 最后看禁止写法，确认没有把 pending/auxiliary 偷换成 confirmed。

### 1.1 当前级别覆盖

| 级别 | 当前状态 | 当前主锚点 |
| --- | --- | --- |
| `1m` | 已有七类消费示例 | `HK.02357 1m range ongoing`、`HK.01339 1m completed_then_new_type`、真实 `SZ.000651 1m pre_breakdown`、真实 replay `002555 1m pre_breakout`、真实 `01024 1m confirmed 3S`、真实 `600900 1m confirmed 3B`、`SH.601328 1m pre-warning proxy`、confirmed regression reference |
| `5m` | 已有稳定节奏案例 | `SH.601318 5m down_bias` |
| `30m` | 已有稳定扩张、去向、预警案例 | `SZ.000651 30m`、`SZ.002594 30m` |
| `day` | 当前主要作为上级别闭合/映射目标出现 | `30m -> day` 的去向与扩张解释 |

说明：

- 若同类场景已有 `30m` 或 `5m` 锚点，本页优先引用这些级别。
- `60m / 15m` 仍保留，但当前主要作为补充样例，而不是首选锚点。
- `1m` 现在已有稳定消费示例，但理论层和样例层仍可继续补更细的多案例对照。
- 真实 `SZ.000651 1m pre_breakdown` 已接入后，`SH.601328 1m` 不再承担主预警锚点角色，只保留为“预警前态代理/过渡说明”样本。
- 当前 `1m pre_breakout` 已有真实 replay 样本链，真实 `1m confirmed 3S` 与 `1m confirmed 3B` live 卡片也已分别由 `01024 1m`、`600900 1m` 补齐；剩余工作主要转为扩更多 confirmed 对照样本，而不是补角色空位。

### 1.2 `1m` 当前稳定消费锚点

当前 `1m` 首选锚点由六个真实产物/回放锚点加一个 regression reference 组成：

1. [data/reports/02357/1m/tech.json](data/reports/02357/1m/tech.json)：单中枢 `range ongoing`
2. [data/reports/01339/1m/tech.json](data/reports/01339/1m/tech.json)：`completed_then_new_type`
3. [data/reports/000651/1m/tech.json](data/reports/000651/1m/tech.json)：真实 `pre_breakdown`，当前仍属 pending/watch
4. [build/scan_real_1m_prebreakout_samples.json](build/scan_real_1m_prebreakout_samples.json)：真实 replay `002555 1m pre_breakout`，cutoff=`2026-08-05 11:07`，当前仍属 pending/watch
5. [data/reports/01024/1m/tech.json](data/reports/01024/1m/tech.json)：真实 live `confirmed 3S`，当前已确认消费
6. [data/reports/601328/1m/tech.json](data/reports/601328/1m/tech.json)：顶背驰迹象已出现，但仍未进入正式 `pre_breakdown` 字段链
7. `tests/test_build_miniapp_publish_bundle.py::test_build_summary_and_detail_payload_preserve_1m_confirmed_3s_reference_anchor`：`1m confirmed 3S` regression reference gate

当前已锁定事实：

- 真实 `SZ.000651 1m`：`zs_monitor_alert=pre_breakdown`，摘要明确给出“出现向下预警，但当前不构成确认三卖”，并保留 `dual_interpretation_pending + down_bias` 的降级语义。
- 真实 replay `002555 1m`：`zs_monitor_alert=pre_breakout`，摘要明确给出“出现向上预警，但当前不构成确认三买。”，并保留 `dual_interpretation_pending + 待确认消费 + up_bias` 的降级语义。
- `HK.02357 1m`：`zhongshus=1`，`current_structure_status=ongoing_same_type`，`relationship.kind=undetermined`，且无确认一二三类买卖点。
- `HK.01339 1m`：`last_completed.type=up`，`current_structure_status=completed_then_new_type`，当前新段为 `down ongoing`，但仍无确认一二三类买卖点。
- 真实 `01024 1m`：`sell_points=[sell3]`、`same_level_consumption_level=confirmed`、摘要明确给出“跌破中枢后反抽下沿失败，当前按三卖确认处理。”，当前可直接作为 confirmed `3S` live 锚点。
- `SH.601328 1m`：中枢仍在运行，`advice_text` 已明确提示“等向上离开或向下跌破后再做决策”，并补充“已有顶背驰迹象”，但没有正式 `zs_monitor_alert` 字段落盘。
- `1m confirmed 3S` regression reference：当前继续作为兜底 gate，防止 live 样本未来漂移时把 confirmed 文案退回 pending/watch。
- 进一步确认：`zs_monitor_alert` 与 confirmed `3S` 已在 `src / scripts / tests` 形成双链稳定主口径，当前缺的重点已经从“角色是否存在”收敛到“是否补更多同类样本对照”。
- 这说明当前 `1m` 已经有“watch/pending”“前段完成后新段运行中”“正式向下预警未确认”“正式向上预警未确认”“真实 confirmed 3S”“预警前态代理”六类真实消费案例，并额外有一条 confirmed regression reference。

当前适用方式：

- 可用于校验 `1m` 在 `tech.json`、报告和小程序里，如何把“单中枢盘整进行中”“前段完成后新段运行中”“正式预警未确认”“风险迹象已出现但尚未进入正式预警字段链”“confirmed reference”稳定区分开。
- `HK.02357 1m` 可直接作为 watch/pending 示例，`HK.01339 1m` 可直接作为 completed_then_new_type 示例，真实 `SZ.000651 1m` 可直接作为正式 `pre_breakdown` 示例，真实 replay `002555 1m` 可直接作为正式 `pre_breakout` 示例，真实 `01024 1m` 可直接作为 confirmed `3S` live 示例，`SH.601328 1m` 可直接作为预警前态代理示例，`1m confirmed 3S` reference gate 当前则保留为兜底回归。
- 只有在需要展示“尚未进入正式字段链”时才继续保留 `SH.601328 1m`；它不再承担 `1m` 主预警链上破方向的缺口填补角色。

正式样本接线要求：

1. `1m pre_breakdown` 与 `1m pre_breakout` 应成对补入，避免消费页只展示单边预警。
2. `tech.json`、报告、小程序三处写法必须同轮更新，不能只换页内案例名而保留旧代理描述。
3. `1m confirmed 3S` 继续同时保留真实 live 锚点与 regression reference：前者负责 review/消费审阅，后者负责自动化兜底。

## 2. 去向候选展示

对应案例：

1. [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md) 第 2.1 节 `SZ.000651 30m higher_level_range`
2. [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md) 第 2.2 节 `HK.00700 60m higher_level_reverse_trend`

当前优先口径：先看 `30m -> day`，再把 `60m` 反趋势候选当补充对照。

### 2.1 `tech.json` 推荐表达

```json
{
  "same_level_consumption_level": "pending",
  "same_level_decomposition_mode": "dual_interpretation_pending",
  "post_divergence_route": "higher_level_range",
  "route_level_from": "30m",
  "route_level_to": "day",
  "summary": {
    "conclusion": "背驰后进入更大级别盘整观察期"
  }
}
```

消费要求：

- `post_divergence_route` 只说明当前最强去向候选，不说明结构已完成。
- 新消费者优先读取 `same_level_consumption_level`；若它等于 `pending`，则结论只能按 pending/watch 消费。
- `same_level_decomposition_mode=dual_interpretation_pending` 只作为旧 payload 缺少新字段时的兼容回退。
- 若主口径与类中枢冲突，主结论仍应优先引用 `zhongshus`。

报告/小程序允许文案：

- `背驰后进入更大级别盘整观察期。`
- `去向偏反趋势，但级别未闭合。`
- `当前先按观察态处理，等待级别闭合。`

禁止写法：

- `日线反转已确认`
- `新趋势已成立`
- `更高级别反转已经完成`

## 3. 节奏监视展示

对应案例：

1. [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md) 第 3.1 节 `SH.601318 5m down_bias`
2. [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md) 第 3.2 节 `HK.01024 15m balanced`

当前优先口径：先用 `5m` 例子审“节奏只降级不确认”，`15m balanced` 先作为补充对照保留，等待后续换成 `1m / 5m / 30m` 链内更完整样本。

### 3.1 `tech.json` 推荐表达

```json
{
  "oscillation_rhythm_state": "down_bias",
  "same_level_decomposition_mode": "dual_interpretation_pending",
  "summary": {
    "conclusion": "节奏偏弱，先维持观察"
  }
}
```

消费要求：

- `oscillation_rhythm_state` 只能作辅助监视，不得单独生成 confirmed buy/sell。
- `down_bias` 表示节奏偏弱，`balanced` 表示暂时无方向优势，都不等于结构确认。
- 若同时存在 `dual_interpretation_pending`，所有高层表述都应保持观察态。

报告/小程序允许文案：

- `节奏偏弱，先维持观察。`
- `结构节奏平衡，暂未出现方向性优势。`
- `当前仅提示节奏变化，不升级买卖点确认。`

禁止写法：

- `卖点已确认`
- `趋势已转空`
- `节奏平衡，建议直接抄底`

## 4. 预警未确认展示

对应案例：

1. [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md) 第 4.2 节 `SZ.002594 30m pre_breakout`
2. [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md) 第 4.1 节 `HK.01024 60m pre_breakdown`

当前优先口径：先用 `30m` 预警回中枢案例做主示例，再用真实 `SZ.000651 1m pre_breakdown` 与真实 replay `002555 1m pre_breakout` 组成 `1m` 双向正式预警未确认锚点，`60m` 继续保留作补充方向对照；`1m confirmed 3S` 当前只作回归对照参考。

补充说明：当前仓库已经有真实落盘的 `1m pre_breakdown` 字段样本，以及真实历史回放的 `1m pre_breakout` 样本，并且 `src / scripts / tests` 侧已有稳定实现锚点；本节现已从“真实 `1m pre_breakdown` + 真实 replay `1m pre_breakout` + proxy negative + confirmed reference”的结构推进。剩余主要缺口是可直接页内审阅的真实 confirmed 卡片。

### 4.1 `tech.json` 推荐表达

```json
{
  "zs_monitor_alert": "pre_breakdown",
  "same_level_decomposition_mode": "single_confirmed",
  "summary": {
    "conclusion": "出现向下预警，但当前不构成确认三卖"
  }
}
```

消费要求：

- `zs_monitor_alert` 统一按 watch/pending 处理，不能单独升级为 confirmed 3B/3S。
- 只要首次回抽/回试回中枢，就必须保留“未确认”表述。
- 上破和下破预警的消费口径必须对称，不能只对一边严格。

报告/小程序允许文案：

- `出现向下预警，但当前不构成确认三卖。`
- `出现向上预警，但当前不构成确认三买。`
- `首次回抽回到中枢区间，继续等待确认链闭合。`

禁止写法：

- `确认三卖`
- `确认三买`
- `突破已成立，可直接按确认信号处理`

## 5. 主辅冲突展示

对应规范：

1. [zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md) 第 9 节主辅冲突优先级表
2. [theory-implementation-consumer-diff-matrix.md](theory-implementation-consumer-diff-matrix.md) 第 3.4 节字段级消费映射

推荐展示顺序：

1. 先显示中枢主结论。
2. 再显示类中枢辅助提示。
3. 若冲突，显式写出 `中枢主口径优先`。

最小示例：

```json
{
  "zhongshus": [{"id": 3, "post_divergence_route": "higher_level_range"}],
  "lei_zhongshus": [{"id": 8, "post_divergence_route": "higher_level_reverse_trend"}],
  "summary": {
    "conclusion": "背驰后进入更大级别盘整观察期",
    "note": "类中枢辅助视图更激进，但当前以中枢主口径优先"
  }
}
```

报告/小程序允许文案：

- `中枢主口径偏盘整观察，类中枢提示更激进方向，仅作辅助。`
- `主辅存在差异，当前以中枢主口径优先。`

禁止写法：

- `类中枢已确认，因此主结论同步确认`
- `辅助提示覆盖主结构结论`

## 6. 三处展示位最小对照表

| 场景 | `tech.json` | 报告文案 | 小程序/图表标签 |
| --- | --- | --- | --- |
| 去向候选 | 保留 `post_divergence_route` + 级别映射 + pending gate | `观察期`、`待级别闭合` | `pending/watch`，不得标 confirmed |
| 节奏监视 | 保留 `oscillation_rhythm_state`，仅作辅助 | `节奏偏弱`、`节奏平衡` | `auxiliary` 或轻量观察标签 |
| 预警未确认 | 保留 `zs_monitor_alert` + `未确认` 说明 | `出现预警，但未确认三买/三卖` | `watch/pending`，不得标 3B/3S confirmed |
| 主辅冲突 | 同时保留 `zhongshus` 与 `lei_zhongshus` | `主口径优先，辅助仅作参考` | 分层图例，禁止合并同色 |

## 7. 同一案例三处并排对照

### 7.1 `SZ.000651 30m` `higher_level_range`

对应案例： [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md) 第 2.1 节。

| 展示位 | 推荐写法 | 绝对红线 |
| --- | --- | --- |
| `tech.json` | `post_divergence_route=higher_level_range`，`route_level_from=30m`，`route_level_to=day`，若 `same_level_consumption_level=pending` 则摘要保留“观察期”；旧 payload 缺字段时再回退到 `same_level_decomposition_mode=dual_interpretation_pending` | 不得只因去向字段存在就补成 `confirmed_reverse` 一类状态 |
| 报告 | `背驰后进入更大级别盘整观察期，当前等待日线级别闭合。` | 不得写成 `日线反转已确认` |
| 小程序/图表 | 标签用 `pending/watch`；图例仍显示中枢主口径，必要时补 `待级别闭合` 副标签 | 不得使用 `confirmed`、`反转成立` 之类强确认标签 |

最小消费结论：这个案例允许提升到“更大级别盘整候选”的解释层，但不允许升级到“新趋势已确认”。

级别说明：这是当前最贴近 `30m -> day` 主阅读链的去向示例，应优先于 `60m` 候选案例使用。

### 7.2 `HK.01024 60m` `pre_breakdown`

对应案例： [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md) 第 4.1 节。

| 展示位 | 推荐写法 | 绝对红线 |
| --- | --- | --- |
| `tech.json` | `zs_monitor_alert=pre_breakdown`，摘要保留“出现向下预警，但当前不构成确认三卖” | 不得把预警字段改写成 `confirmed_3s=true` 一类确认状态 |
| 报告 | `出现向下预警，但首次回抽已回中枢，继续等待确认链闭合。` | 不得写成 `确认三卖，可直接执行` |
| 小程序/图表 | 预警卡片显示 `watch/pending`，颜色可偏风险提示，但必须保留 `未确认` 标签 | 不得把预警卡片标题写成 `三卖` 或 `确认卖出` |

最小消费结论：这个案例可以提示风险升高，但不能把预警链偷换成三卖确认链。

级别说明：当前仍保留这个 `60m` 案例，是因为它适合作为更高一级的向下预警补充对照；真实 `1m pre_breakdown` 现已由 `SZ.000651 1m` 承担主锚点。

### 7.3 `01024 1m` confirmed `3S` live anchor

对应案例： [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md) 第 4.5 节；兜底 gate 为 `tests/test_build_miniapp_publish_bundle.py::test_build_summary_and_detail_payload_preserve_1m_confirmed_3s_reference_anchor`。

| 展示位 | 推荐写法 | 绝对红线 |
| --- | --- | --- |

| `tech.json` / payload | 保留 `sell_points=[sell3]`、`same_level_consumption_level=confirmed` 与 `最近卖点：三卖` 一类 confirmed 说明 | 不得把这个真实 confirmed live 卡片再降写成只有 `watch/pending` 的模糊风险提示 |
| 报告 | `1m ... 当前按三卖确认处理。` | 不得把已闭合确认链重新写成 `仅预警` |
| 小程序/图表 | 可显示 `confirmed` 风险或卖点标签，但必须与 `30m/5m` 的 pending/auxiliary 标签区分开 | 不得把 `1m confirmed 3S` 与 `30m pre_breakout`、`5m down_bias` 渲染成同一状态 |

最小消费结论：这个 `1m` confirmed 场景现在已经由真实 `01024 1m` live 样本承担，用来对照 `30m`、`60m` 与真实 `1m pre_breakdown/pre_breakout` 的未确认预警案例；旧 reference gate 只保留作自动化兜底。

### 7.4 `HK.02357 1m` `range ongoing`

对应案例： [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md) 第 1.2 节。

| 展示位 | 推荐写法 | 绝对红线 |
| --- | --- | --- |
| `tech.json` | 保留 `zhongshus=1`、`current_structure_status=ongoing_same_type`、`relationship.kind=undetermined`，并明确 `buy_points=[]`、`sell_points=[]` | 不得只因已有一个中枢就补成 `confirmed range`、`confirmed trend` 或任意买卖点确认 |
| 报告 | `当前只有一个同级别中枢，先按盘整进行中观察，等待重新站回 2.98-3.00。` | 不得写成 `盘整已完成`、`趋势已确认` 或 `一二三类买卖点已出现` |
| 小程序/图表 | 只显示 `watch/pending` 或中性观察标签，图例中保留“结构未完成”说明 | 不得给这个 `1m` 卡片贴 `confirmed` 或交易动作型标签 |

最小消费结论：这个 `1m` 例子用于说明“已有中枢”不等于“已有确认走势或确认买卖点”，是 `1m` 观察态的主锚点。

### 7.5 `HK.01339 1m` `completed_then_new_type`

对应案例： [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md) 第 1.3 节。

| 展示位 | 推荐写法 | 绝对红线 |
| --- | --- | --- |
| `tech.json` | 保留 `last_completed`、`current_ongoing`、`relationship.kind=completed_then_new_type_ongoing` 与 `current_structure_status=completed_then_new_type`，并保持 `buy_points=[]`、`sell_points=[]` | 不得把“前段已完成”偷换成“当前新段买卖点已确认”，也不得回退写成“关系未定” |
| 报告 | `上一段同级别走势已结束，当前新的同级别下行结构运行中，等待是否形成有效确认。` | 不得写成 `新一轮下跌已确认卖点`、`已形成三卖` 或 `趋势已完全确认` |
| 小程序/图表 | 可显示“新段运行中”或“结构切换后观察”标签，但必须与 `watch/pending` 及 `confirmed` 分层 | 不得把这个 `1m` 卡片直接贴成 `confirmed`，也不得和单中枢未定场景混成同一种说明 |

最小消费结论：这个 `1m` 例子用于说明“上一段已完成”只能推出结构切换，不足以直接推出当前新段的确认买卖点，是 `1m` 中间态的主锚点。

### 7.6 `002555 1m` pre_breakout replay anchor

对应案例： [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md) 第 4.4 节。

| 展示位 | 推荐写法 | 绝对红线 |
| --- | --- | --- |
| `tech.json` / replay payload | 保留 `zs_monitor_alert=pre_breakout`、`same_level_decomposition_mode=dual_interpretation_pending`、`same_level_consumption_level=pending`，摘要明确写 `出现向上预警，但当前不构成确认三买。` | 不得把历史 replay 锚点偷换成 `confirmed 3B`，也不得省略 `待确认消费` 降级说明 |
| 报告 | `出现向上预警，但首次回试确认链尚未闭合，继续观察是否回中枢。` | 不得写成 `向上突破已确认`、`确认三买，可直接执行` |
| 小程序/图表 | 可显示 `watch/pending` 上破预警标签，但必须同时保留 `未确认` 或 `待确认消费` 说明 | 不得和 confirmed `3B` 使用同一主标题或同级强标签 |

最小消费结论：这个 `1m` 例子用于说明真实 `pre_breakout` 已经可以进入消费链，但它仍然只是“向上预警未确认”，不是 confirmed 三买。

实现差异说明：当前这个锚点来自历史回放与真实 replay gate，而不是最新 live `tech.json` 快照；因此消费端要锁的是语义一致性，而不是把它误读成当前最新页内终态。

### 7.7 `SH.601328 1m` pre-warning proxy

对应案例： [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md) 第 4.6 节。

| 展示位 | 推荐写法 | 绝对红线 |
| --- | --- | --- |
| `tech.json` | 保留当前 `zhongshus`、顶背驰状态与“等向上离开或向下跌破后再做决策”的摘要语义，并明确当前尚无 `zs_monitor_alert` 落盘 | 不得为了凑齐预警链而凭空补写 `zs_monitor_alert=pre_breakdown` 或把顶背驰迹象升级成 `confirmed 3S` |
| 报告 | `已有顶背驰迹象，但仍在中枢内震荡，等待向上离开或向下跌破后再做决策。` | 不得写成 `向下预警已成立`、`确认三卖` 或 `趋势已转空` |
| 小程序/图表 | 只能显示风险提示或轻量观察标签，并注明“预警前态/待离开中枢” | 不得直接贴 `pre_breakdown`、`confirmed` 或交易动作型标签 |

最小消费结论：这个 `1m` 例子不是正式 `pre_breakdown` 样本，而是用来约束消费端不要把“风险迹象已出现”偷换成“预警已成立”的代理锚点。

实现差异说明：当前它之所以仍是代理锚点，已经不再是因为 `zs_monitor_alert` 缺实现，而是因为它代表“尚未进入正式字段链”的前态阶段；消费端应继续坚持 unknown/watch 降级。

替换触发条件：后续只要正式 `1m pre_breakdown` / `pre_breakout` 任一方向形成稳定落盘与展示链，本节就不应再让 `SH.601328 1m` 占据 `1m` 主预警锚点；它只能保留作“字段尚未落盘前的风险前态”反例或过渡说明。

## 8. 关联文档

1. [zhongshu-review-entry.md](zhongshu-review-entry.md)
2. [zhongshu-core-spec.md](zhongshu-core-spec.md)
3. [zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md)
4. [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md)
5. [theory-implementation-consumer-diff-matrix.md](theory-implementation-consumer-diff-matrix.md)