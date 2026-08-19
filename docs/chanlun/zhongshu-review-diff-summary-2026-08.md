# 中枢 review 增量摘要（2026-08）

本页用于总结本轮 `zhongshu` 文档整理相对于前一阶段的实际增量，目标不是重复规范正文，而是回答三件事：

1. 这轮到底新增了哪些 review 入口和案例材料。
2. 哪些样例页已经从“模板集合”推进成“可直接进入 review 的案例入口”。
3. 当前还缺什么，下一步最值得补哪里。

本轮示例级别策略：尽可能优先使用 `1m / 5m / 30m / day` 这条链。当前已稳定落地的是 `1m / 5m / 30m / day映射`，其中 `HK.02357 1m` 已补为 watch/pending 场景锚点，`HK.01339 1m` 已补为 completed_then_new_type 场景锚点，真实 `SZ.000651 1m` 已补为正式 `pre_breakdown` 场景锚点，`SH.601328 1m` 已补为预警前态代理锚点；`1m confirmed 3S` 当前仍主要由 regression reference gate 承担。后续优先缺口已收敛为正式 `1m pre_breakout` 样本与真实 confirmed 页内卡片。

## 1. 本轮新增内容

### 1.1 入口层

本轮新增或显著强化了以下入口：

1. [zhongshu-review-entry.md](zhongshu-review-entry.md)
   用途：把原文定义、主辅消费口径、高风险样例和下游消费红线压到单页入口。
2. [zhongshu-core-spec.md](zhongshu-core-spec.md)
   用途：已补回 `review entry` 的推荐分层与关联文档回链。
3. [zhongshu-original-review-matrix.md](zhongshu-original-review-matrix.md)
   用途：顶部已增加“先看 review 入口”的导流。

### 1.2 样例层

本轮把 `zhongshu-visual-example-library.md` 从纯模板页推进成“模板 + 现成案例入口 + 页内真实卡片”：

1. 第18/20课中枢定理与扩张示例，已回链到 `sample-case-pack-2026-08-v1/v2` 的 30m 样例。
1. 第18/20课中枢定理与扩张示例，已回链到 `sample-case-pack-2026-08-v1/v2` 的 30m 样例，并内嵌 `SZ.000651 30m` 中枢扩张候选真实卡片。
2. 第29课背驰后三级去向示例，已回链到 `higher_level_range`、`higher_level_reverse_trend` 与“候选回退”样例；当前优先锚点是 `SZ.000651 30m -> day`，`HK.00700 60m` 保留作补充对照。
3. 第39课节奏示例，已回链到两批样例包和两份阈值回放记录；当前优先锚点是 `SH.601318 5m down_bias`，`HK.01024 15m balanced` 暂作补充对照。
4. 第92课监视器预警与确认链对照示例，已回链到 `pre_breakout/pre_breakdown` 回中枢与确认失败案例；当前优先锚点是 `SZ.002594 30m pre_breakout` 与真实 `SZ.000651 1m pre_breakdown`，`HK.01024 60m pre_breakdown` 暂作补充对照，`SH.601328 1m` 仅保留作 `1m` 预警前态代理样本，`1m confirmed 3S` 则继续由 regression reference gate 承担对照角色。

### 1.3 review 路径层

本轮已经形成比较明确的 `zhongshu` review 路径：

1. 先读 [zhongshu-review-entry.md](zhongshu-review-entry.md)
2. 再核对 [zhongshu-original-review-matrix.md](zhongshu-original-review-matrix.md)
3. 然后进入 [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md) 第 1 至第 4 节，先审页内真实卡片，再对照已填充样例包和 replay log

## 2. 关键增量对照

| 主题 | 之前状态 | 当前状态 |
| --- | --- | --- |
| review 入口 | 主要分散在 core spec、原文矩阵、样例页之间 | 已有 [zhongshu-review-entry.md](zhongshu-review-entry.md) 作为单页入口 |
| 原文矩阵入口性 | 可读，但没有明确 review 起点 | 已可先从 review entry 进入，再回到矩阵 |
| 样例库 | 以模板流程图和卡片模板为主 | 已直接回链到已填充案例、replay log，并开始内嵌页内真实卡片 |
| 扩张案例 | 主要依赖跳转样例 | 已能从样例库第 1 节直接进入 review，并页内审中枢扩张候选 |
| 去向案例 | 主要存在于样例包本身 | 已能从样例库第 2 节直接进入 review，并页内审 `higher_level_range` / `higher_level_reverse_trend` |
| 节奏案例 | 需要分别翻样例包和回放记录 | 已能从样例库第 3 节集中进入，并页内审 `down_bias` / `balanced` |
| 预警未确认案例 | 有案例，但入口分散 | 已能从样例库第 4 节集中进入，并页内审 `pre_breakdown` / `pre_breakout` 回中枢 |

## 3. 当前最有价值的现成入口

如果现在就开始做 `zhongshu` review，建议按以下顺序读取：

1. [zhongshu-review-entry.md](zhongshu-review-entry.md)
2. [zhongshu-original-review-matrix.md](zhongshu-original-review-matrix.md)
3. [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md) 第 1 至第 4 节
4. [sample-case-pack-2026-08-v2.md](sample-case-pack-2026-08-v2.md) 第 1.1、2.2、3.2、3.3 节
5. [rhythm-replay-log-2026-08-second-batch.md](rhythm-replay-log-2026-08-second-batch.md) 第 6 节

## 4. 仍未完成的缺口

本轮虽然把入口和案例跳转收拢了，但还有几块没有真正收敛：

1. 第 1 至第 4 节都已有页内真实卡片，但当前仍主要覆盖单卡片示例，尚未形成同场景多案例对照页。
2. 已新增 [zhongshu-consumer-display-examples.md](zhongshu-consumer-display-examples.md)，把页内卡片继续上提成“报告、小程序、`tech.json` 三处展示差异”对照页；当前已补入 `HK.02357 1m range ongoing`、`HK.01339 1m completed_then_new_type`、真实 `SZ.000651 1m pre_breakdown`、`SH.601328 1m pre-warning proxy`，并继续保留 `1m confirmed 3S` regression reference，形成 `1m` 的五类对照。当前这套 `1m` 对照中，`SH.601328 1m` 只承担“预警前态代理/过渡说明”角色，不代表正式 `1m pre_break*` 已落盘；真实 `SZ.000651 1m` 则已经接管 `1m` 向下预警主位。与此同时，本轮代码侧已把 `zs_monitor_alert`、`zs_monitor_midline`、`zs_monitor_bias`、`same_level_decomposition_mode`、`post_divergence_route`、`oscillation_rhythm_state` 接入稳定主链，并补上 `route_level_from/to`、节奏辅助文案与 `30m pre_breakdown/pre_breakout -> published summary/detail` 的回归锚点；本次继续把主批量发布链收紧为 `segment` 唯一主口径，并让 `identify_zhongshu(..., structure_level="segment")` 只消费已确认线段，避免 `pending_confirmation` 尾段直接污染标准中枢主链。进一步地，若 reclaim/重写把 segment 链并回单个未确认尾段，segment 中枢结果现在会整体清空，避免旧中心残留；同时线段 `is_reclaimed` / `absorbed_segment_ids` 已接入尾段解释层、`segments.csv` 以及小程序 `summary/detail` 的消费输出，重写吸收边界已具备 machine-readable 锚点。本轮还修掉八类具体漂移路径：当初始转折仍处于 `TransitionState.PENDING` 时，practical `reverse_break` 不再提前把该段确认为已完成；当 `auto` / `prefer_earlier_start` 选首种子时，更靠右的 later confirmed 新段若仍落在更靠左未确认旧段的未解决窗口内，也不再被当成 bootstrap 最优候选；首种子评分已去掉对三笔以上首段的额外长度奖励，而 practical 下的 `gap false defer` 也已从 bootstrap 模式中解耦，使 `first_valid_seed` / `auto` / `prefer_earlier_start` 在 `000591`、`300124`、`00700`、`03690` 共 7 组真实 fixture 上的首段起点、方向、`is_confirmed` 与 `stop_reason` 都已对齐；本轮进一步修掉“local gap false invalidation 后仍沿用旧 extreme”的后续段漂移，`00700-60m` 的 practical 第 3 段已回到和 theory 一致的 `feature_sequence_fractal`，不再被更晚的 `reverse_break` 抢跑；并且当 gap 候选在同一轮被判纯 `INVALIDATED` 且 transition reclaim 已经成立时，practical 路径现已优先走 reclaim，而不会先被 invalidated-gap 分支吞掉；但若该 `INVALIDATED` 是前一轮 local gap false `DEFERRED` 的落地结果，则当前段会先锁定 `gap false` 并保留后续 `reverse_break` 确认轮，避免被 reclaim 或同轮 fallback 过早吞掉，这条 deferred->invalidated 路径现已同时有 focused unit、focused matrix tests 与真实 fixture regression gate 共同覆盖；除此之外，practical 主循环现在不再在首个未确认段处无条件停机，只要后面已经存在能独立走出 confirmed 段的新三笔种子，就会继续向后扫描而不是把整条链冻结成单个 pending 尾段，这一收敛已经把 `300124 15m` practical 从两段链推进到 `0->2 / 3->9 / 10->18 / 19->21 / 22->24 / 25->29` 六段结构，并让 `000591-day` 当前 live 窗口 practical 不再人为残留 preprocessing 尾段；同时 `000591 60m` 的 real restart anchor 已被单独锁定为 `break_bi_id=9 -> next start_bi_id=9`，`000591 60m long` 的中段 overlap/reuse 语义也已锁定为 `middle break_bi_id=17` 且后续上升段继续从 `15` 起并复用到 `17`，`300124 60m` 的 mixed overlap/restart 语义也已锁定为 `up 4->8` practical `break_bi_id=11` 继续被后续下跌段复用，而其后的 `reverse_break` 段则分别按 `12`、`17` 精确重启，`00700 60m` 的对应 real restart anchor 也已锁定为 `break_bi_id=16 -> next start_bi_id=16`，`03690 30m` 的 dedicated regression 已同步到当前真实窗口并锁定超长 `up 13->31` practical 段的 `break_bi_id=32 -> next start_bi_id=32` restart 语义，而 `03690 60m` 现在也已新增 overlap/reuse + preprocess-tail 锚点：首段 `down 0->2` practical `break_bi_id=5` 必须继续落在后续未确认 `up` 段窗口内，且尾段仍保持 `same_direction_not_extending`；另外 `000591-day` 与 `00700-30m` 的旧 fixture 路径也已切回当前 live 窗口，避免回归链被过期样本直接打断。当前缺口已收敛到“仍缺真实 `1m pre_breakout` 落盘样本、真实 confirmed 页内卡片、正式样本替换代理锚点后的其余入口收口、节奏严格阈值校准，以及更复杂的 reclaim/重写与 gap 再分辨交界未完全统一导致的中枢漂移问题”。
3. 后续仍可继续补“中枢主口径 vs 类中枢辅口径”在多入口展示中的更多反例和对照文案。

## 5. 下一步建议

最合理的下一步不是继续加入口，而是开始把现成样例内嵌回样例库：

1. 先把第 1 至第 4 节中的单卡片场景继续扩成“同主题双案例对照”，提高 review 判别力。
2. 优先补真实落盘的 `1m pre_breakout/pre_breakdown` 案例，让正式样本接管当前 `SH.601328 1m` 所在的主预警入口，并把该代理锚点下沉成过渡说明样本；代码侧 `zs_monitor_alert` 与相关 pending gate 已有稳定实现与测试锚点。
3. 然后继续丰富 [zhongshu-consumer-display-examples.md](zhongshu-consumer-display-examples.md) 中的反例和 UI 对照文案。

## 6. 关联文档

1. [zhongshu-review-entry.md](zhongshu-review-entry.md)
2. [zhongshu-core-spec.md](zhongshu-core-spec.md)
3. [zhongshu-original-review-matrix.md](zhongshu-original-review-matrix.md)
4. [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md)
5. [sample-case-pack-2026-08-v1.md](sample-case-pack-2026-08-v1.md)
6. [sample-case-pack-2026-08-v2.md](sample-case-pack-2026-08-v2.md)
7. [rhythm-replay-log-2026-08-first-batch.md](rhythm-replay-log-2026-08-first-batch.md)
8. [rhythm-replay-log-2026-08-second-batch.md](rhythm-replay-log-2026-08-second-batch.md)