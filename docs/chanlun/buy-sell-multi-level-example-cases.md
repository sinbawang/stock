# 买卖点案例库（真实样本卡 + 构造反例索引）

本页是 BS6 / D2 / T1 的**案例包**：把「每类买卖点到底有多严格」拆成可复核、可回归的单元。

与相邻文档的分工：

| 文档 | 职责 |
| --- | --- |
| [buy-sell-multi-level-spec.md](buy-sell-multi-level-spec.md) §2 / §3-§9 | 应然规则（严格确认要件、失效条件、区间套与小转大） |
| **本页** | **案例证据**：真实窗口样本卡（§3 标准点 / 类比点，§7 区间套 / 小转大）+ 构造正/反/易混淆例索引 + 覆盖缺口 |
| [buy-sell-multi-level-visual-example-library.md](buy-sell-multi-level-visual-example-library.md) | 图形化模板与卡片格式 |
| `tests/test_example_library_real_cases.py` | 本页每张真实卡片的自动化锚点 |

## 1. 用法

- **review 某个点类型是否够严格**：先看 §2 覆盖矩阵定位证据所在，再看 §3 该类型的真实卡片（含退场轨迹）与 §4 的反例索引。
- **改动了买卖点规则**：先跑 `pytest tests/test_example_library_real_cases.py`。卡片的锚点、价格、依据码、cutoff 序列任一变化都会失败，失败信息会打印该 cutoff 的实际发点，便于判断是「有意变更」还是「回归」。
- **不要把本页当规格**：本页只记录**实测**。规则怎么写见 spec §2。

真实卡片口径（与闸门共用 `tests/real_fixture_support.py::analysis_cutoffs`）：

- 冻结窗口来自 `tests/fixtures/real/`：**21 个窗口，共 287 帧**（每窗 13–14 帧；`frames=12` 是步长
  参数，不是帧数上限）。
- 线段 `bootstrap_mode`：`1m` 用 `FIRST_VALID_SEED`，其余用 `PREFER_EARLIER_START`；`strict_segment_rules=True`；`pending_reverse_mode="effective_only"`。
- 只在 `lifecycle_state == confirmed` 上取样本。
- §7 的区间套 / 小转大卡片口径不同：需要**同标的两个级别**，高级别取 cutoff，次级别按同一时刻
  T 截断（详见 §7）。

## 2. 覆盖矩阵

真实样本统计口径：21 个冻结窗口 × 287 帧，只计 `confirmed`。

| 点类型 | 构造正例 | 构造反例 / 易混淆例 | 真实正例 | 真实退场轨迹 |
| --- | --- | --- | --- | --- |
| `buy1` 一买 | ✅ | ✅ | ✅ 3 次 / 2 窗口 | ✅ `superseded(zs_superseded)` |
| `sell1` 一卖 | ✅ | ✅ | ❌ **0** | ❌ 无样本 |
| `buy2` 二买 | ✅ | ✅ | ❌ **0** | ❌ 无样本 |
| `sell2` 二卖 | ✅ | ✅ | ❌ **0** | ❌ 无样本 |
| `buy3` 三买 | ✅ | ✅ | ✅ 28 次 / 11 窗口 | ✅ `superseded(zs_superseded)` |
| `sell3` 三卖 | ✅ | ✅ | ✅ 73 次 / 18 窗口 | ✅ `invalidated(third_class_reentered_zs)` / `superseded(reanchored)` |
| `buy1like` 类一买 | ✅ | ✅ | ✅ 6 次 / 2 窗口 | ⚠️ 样本位于末帧，未观察到退场 |
| `sell1like` 类一卖 | ✅ | ✅ | ❌ **0** | ❌ 无样本 |
| `buy2like` 类二买 | ✅ | ✅ | ✅ 7 次 / 4 窗口 | ✅ `invalidated(gap_divergence_lost)` |
| `sell2like` 类二卖 | ✅ | ✅ | ✅ 12 次 / 6 窗口 | ✅ `invalidated(gap_divergence_lost)` |

**读法**：构造正/反例覆盖 10/10 类型；**真实窗口正例只覆盖 6/10 类型**。`sell1`、`sell2`、`buy2`、`sell1like`
在 287 个真实窗口帧上一次都没有 `confirmed` 发点，其判定逻辑目前**只在构造输入上被验证**（见 §5）。

## 3. 真实案例卡（正例）

字段说明：`cutoff 帧` 是 `analysis_cutoffs` 的下标；`锚点` 为 `signal_bi_id`；`关联中枢` 为 `related_zs_id`；
`退场` 来自 `replay_confirmed_signal_lifecycle`（固定窗口起点，逐帧扩张尾段）。

七张卡片的回放窗口上 **repaint 违规 = 0**：每个锚点的消失都有 `invalidated`（带 `invalidated_reason` /
`invalidated_premise`）或 `superseded`（带 `evidence`）归类，没有「凭空消失」。

### 3.1 一买 · `000591` day

| 字段 | 值 |
| --- | --- |
| cutoff 帧 | f10（`cutoff=1010`，窗口起点 2021-09-30） |
| 点 / 锚点 / 价格 | `buy1` / `bi77` / `4.19` |
| 关联中枢 | `zs1` |
| 依据码 | `bottom_divergence_near_zs_low`（中枢下沿附近出现底背驰） |
| 退场轨迹 | f11 `superseded`，evidence `zs_superseded` |

**严格性要点**：该点在 `ongoing_type == down` 下成立，依附 `zs1` 且回溯到「最近中枢 + 离开段 + 背驰」
三元组（spec §2.2）；f11 后其依附中枢被推进取代，故按**更替**而非**失效**退场——这是 §3.5 的证据表分支。

### 3.2 类一买 · `00700` 1m

| 字段 | 值 |
| --- | --- |
| cutoff 帧 | f13（`cutoff=3500`，窗口起点 2026-08-28 11:41） |
| 点 / 锚点 / 价格 | `buy1like` / `bi96` / `436.4` |
| 关联中枢 | `zs0` |
| 依据码 | `consolidation_divergence_reverse_low`（盘整背驰，离开段结束向上转折即生成） |
| 退场轨迹 | 位于末帧，未观察到退场 |

**严格性要点**：`buy1like` 全库只有 2 个窗口出现过，其中 `00700 1m` 是**唯一稳定**的（f9–f13 连续五帧
同锚点 `bi96`；另有 `03690 5m` 单帧样本 `bi48`）。它体现类一买的门控差异：`ongoing_type == range` +
`current_structure_status == ongoing_same_type`（spec §2.5）；同一窗口的 `sell1like` 在所有 287 帧上
从未出现（见 §5）。

### 3.3 类二买 · `00700` 5m

| 字段 | 值 |
| --- | --- |
| cutoff 帧 | f11（`cutoff=1831`，窗口起点 2026-07-31 14:25） |
| 点 / 锚点 / 价格 | `buy2like` / `bi105` / `432.8` |
| 关联中枢 | `zs1` |
| 依据码 | `gap_segment_divergence_pullback_end`（同级别隔段背驰，回踩结束即生成） |
| 退场轨迹 | f12 `invalidated`，reason `gap_divergence_lost`，premise `price` |

**严格性要点**：同窗口另有两次 `buy2like` 失效（`bi87` @f9、`bi105` 之前的 `bi98` 反手失效 @f10），
说明类二买**不设破前低约束**但**必须持续满足隔段力度衰减**：一旦 A_{i+2} 力度不再弱于 A_i 立即失效
（spec §2.6 + §2.8）。

### 3.4 三买 · `00728` day

| 字段 | 值 |
| --- | --- |
| cutoff 帧 | f11（`cutoff=1105`，窗口起点 2021-10-29） |
| 点 / 锚点 / 价格 | `buy3` / `bi63` / `5.26` |
| 关联中枢 | `zs0` |
| 依据码 | `leave_zs_then_pullback_holds_upper_edge`（离开中枢后回踩上沿未失守） |
| 退场轨迹 | f12 `superseded`，evidence `zs_superseded` |

**严格性要点**：本样本在 f9 / f10 / f11 三帧连续成立（稳定样本，非抖动用例）。
定性注记：该窗口中枢只有一个，离开真实、回踩确实守住上沿——属**迟发但成立**的三买，不是噪声点
（与 2026-09-12 日线复核结论一致）。

### 3.5 类二卖 + 三卖重合 · `000651` 1m

| 字段 | 值 |
| --- | --- |
| cutoff 帧 | f7（`cutoff=2062`，窗口起点 2026-08-24 11:25） |
| 点 / 锚点 / 价格 | `sell2like` / `bi110` / `39.09`（同锚点另有 `sell3`） |
| 关联中枢 | `zs1` |
| 依据码 | `gap_segment_divergence_rebound_end` |
| 退场轨迹 | f8 两个点**各自按自己的前提失效**：`sell3` → `third_class_reentered_zs`；`sell2like` → `gap_divergence_lost` |

**严格性要点**：这是 spec §2.7「二类点与三类点可能重合」的**真实样本**——同一锚点 `bi110` 上 `sell3`
与 `sell2like` 并存，且失效时**各自用自己的前提判定**（三类点看是否重新站回中枢下沿，类二类点看隔段
背驰是否还在）。这张卡是「前提必须按点自己的门控读」这条修复（commit `8c97226`）的直接证据。

### 3.6 三卖 · `000591` 5m

| 字段 | 值 |
| --- | --- |
| cutoff 帧 | f13（`cutoff=2000`，窗口起点 2026-07-17 09:35） |
| 点 / 锚点 / 价格 | `sell3` / `bi59` / `4.4` |
| 关联中枢 | `zs0` |
| 依据码 | `leave_zs_then_rebound_fails_lower_edge` |
| 退场轨迹 | 位于末帧，未观察到退场 |

**严格性要点**：同窗口更早的两个 `sell3`（`bi45` @f10、`bi49` @f12）均以 `superseded(reanchored)`
退场，说明三卖锚点会随结构推进前移，而**不会**以「位置前提被破坏」的形态留下假报警。

### 3.7 三卖 · `000591` day

| 字段 | 值 |
| --- | --- |
| cutoff 帧 | f5（`cutoff=535`，窗口起点 2021-09-30） |
| 点 / 锚点 / 价格 | `sell3` / `bi52` / `5.81` |
| 关联中枢 | `zs0` |
| 依据码 | `leave_zs_then_rebound_fails_lower_edge` |
| 退场轨迹 | f6 `superseded`，evidence `reanchored` |

**严格性要点**：这是日线上**最早的**三卖样本（cutoff 仅 535），用于覆盖「窗口只够识别单一中枢」的
退化场景——三卖仍能依附该中枢给出，但按 §3.4 同口径属迟发类型。

## 4. 构造类反例 / 易混淆例索引

以下用例为**构造输入**（合成 bi / 中枢），锁的是判定逻辑本身。全部位于 `tests/test_chanlun_analysis.py`。

### 4.1 一类点

| 用例 | 类型 | 锁定内容 |
| --- | --- | --- |
| `test_analyze_chanlun_signals_flags_first_buy_on_bottom_divergence_below_zs_low` | 正例 | 中枢下沿下方的底背驰 → 一买 |
| `test_analyze_chanlun_signals_flags_first_sell_on_top_divergence_above_zs_high` | 正例 | 中枢上沿上方的顶背驰 → 一卖 |
| `test_analyze_chanlun_signals_buy1_anchors_on_exit_segment_end_bi` | 正例（锚点） | 一买锚定**离开段末端笔**，不是最近笔 |
| `test_analyze_chanlun_signals_does_not_flag_buy1_on_boundary_touch_without_divergence` | **反例** | **仅触边不背驰**不得报一买（spec §2.2 红线） |
| `test_analyze_chanlun_signals_requires_up_turn_confirmation_before_buy1` | **反例** | 未出现反向转折笔时不得确认 |
| `test_analyze_chanlun_signals_buy1_and_sell1_require_confirmed_departure_and_turn` | **反例** | 离开段未确认 / 未转折 → 不发点，买卖两侧对称 |
| `test_analyze_chanlun_signals_buy1_uses_segment_divergence_strict_strength` | 严格性 | 力度口径必须是**段级** MACD 面积衰减 |
| `test_analyze_chanlun_signals_buy1_requires_segment_strength_decay` | 严格性 | 无段级力度衰减不发点 |
| `test_analyze_chanlun_signals_sell1_uses_segment_divergence_strict_strength` | 严格性 | 一卖侧同口径 |

### 4.2 二类点

| 用例 | 类型 | 锁定内容 |
| --- | --- | --- |
| `test_analyze_chanlun_signals_flags_second_buy_after_buy1_rebound` | 正例 | 一买后首次回试不破前低 → 二买 |
| `test_analyze_chanlun_signals_flags_second_sell_after_sell1_rebound` | 正例 | 一卖后首次反抽不破前高 → 二卖 |
| `test_analyze_chanlun_signals_does_not_flag_buy2_when_renew_up_fails_new_high` | **反例** | 恢复向上但未创新高 → 不发 |
| `test_analyze_chanlun_signals_does_not_flag_buy2_without_renew_up_after_pullback` | **反例** | 回试后无「再度走强」 |
| `test_analyze_chanlun_signals_does_not_reflag_buy2_on_second_pullback` | **反例** | 第二次回试不得回写成同一买点的二买 |
| `test_analyze_chanlun_signals_does_not_flag_buy2_on_continuation_pullback_breaking_prior_low` | **易混淆** | **中继震荡破前低**不得误判为二买 |
| `test_analyze_chanlun_signals_bi_level_zhongshu_does_not_flag_second_buy_level_convergence` | **易混淆** | 笔级别中枢不得当作段级二买依据 |
| `test_analyze_chanlun_signals_does_not_flag_sell2_*`（3 个） | 反例 | 二卖侧对称 |

### 4.3 三类点

| 用例 | 类型 | 锁定内容 |
| --- | --- | --- |
| `test_analyze_chanlun_signals_flags_third_buy_after_leave_zs_and_pullback_holds_upper_edge` | 正例 | 离开中枢后首次回抽守上沿 → 三买 |
| `test_analyze_chanlun_signals_flags_third_sell_after_leave_zs_and_rebound_fails_lower_edge` | 正例 | 三卖侧 |
| `test_analyze_chanlun_signals_buy3_anchors_first_hold_not_latest_pullback` | 正例（锚点） | 锚定**首次**回试，不是最新回抽 |
| `test_analyze_chanlun_signals_buy3_requires_segment_pullback` | 严格性 | 回踩须成**线段**，未成段不得提前报点（spec §2.4） |
| `test_analyze_chanlun_signals_does_not_flag_buy3_when_first_pullback_reenters_zs` | **反例** | **回抽回中枢** → 三买不成立 |
| `test_analyze_chanlun_signals_does_not_flag_buy3_without_renew_up_after_pullback` | **反例** | 回抽后无「再度走强」 |
| `test_analyze_chanlun_signals_flags_buy3_when_renew_up_resumes_without_new_high` | 边界 | 再度走强**不要求创新高**（与二类点口径差异） |

### 4.4 类一类点

| 用例 | 类型 | 锁定内容 |
| --- | --- | --- |
| `test_analyze_chanlun_signals_flags_buy_1like_on_range_consolidation_divergence` | 正例 | range 盘整背驰 → 类一买 |
| `test_analyze_chanlun_signals_flags_sell_1like_on_range_consolidation_divergence` | 正例 | 类一卖侧 |
| `test_analyze_chanlun_signals_buy_1_not_buy_1like_under_down_trend_gate` | **易混淆** | 下跌趋势门控下走**标准一买**，不降级为类一买（互斥门控） |
| `test_analyze_chanlun_signals_no_buy_1like_without_consolidation_divergence` | **反例** | 无盘整背驰 |
| `test_analyze_chanlun_signals_no_buy_1like_without_reverse_turn` | **反例** | 无反向转折 |
| `test_analyze_chanlun_signals_no_buy_1like_when_structure_status_candidate` | **反例** | `candidate_completed_waiting_stability` 下只观察不发点（spec §2.5 门控） |
| `test_analyze_chanlun_signals_no_sell_1like_without_consolidation_divergence` | **反例** | 类一卖侧对称 |

### 4.5 类二类点

| 用例 | 类型 | 锁定内容 |
| --- | --- | --- |
| `test_analyze_chanlun_signals_flags_buy_2like_on_gap_segment_divergence` | 正例 | 隔段背驰 A_i vs A_{i+2} → 类二买 |
| `test_analyze_chanlun_signals_flags_buy_2like_when_pullback_holds_prev_low` | 正例 | **不破前低也成立**（与标准二买的关键差异） |
| `test_analyze_chanlun_signals_flags_sell_2like_on_gap_segment_divergence` | 正例 | 类二卖侧 |
| `test_analyze_chanlun_signals_no_buy_2like_without_gap_divergence` | **反例** | 无隔段力度衰减 |
| `test_analyze_chanlun_signals_no_buy_2like_when_pullback_not_ended` | **反例** | 回踩未结束不发点 |
| `test_analyze_chanlun_signals_no_buy_2like_when_decomposition_pending` | **反例** | `dual_interpretation_pending` 下不发机械类二类点（spec §2.6 门控） |
| `test_analyze_chanlun_signals_no_sell_2like_without_gap_divergence` | **反例** | 类二卖侧 |

### 4.6 生命周期（退场判据）

| 用例 | 锁定内容 |
| --- | --- |
| `test_replay_marks_buy_1_invalidated_when_departure_low_broken` | 一买：离开段极值被跌破 → 失效 |
| `test_replay_marks_buy_3_invalidated_when_pullback_reenters_zs` | 三买：回试重新跌回中枢 → 失效 |
| `tests/test_example_library_real_cases.py::test_case_card_reproduces_on_frozen_window` | §3 每张真实卡片的锚点/价格/依据码/cutoff 锚定 |

## 5. 已知缺口

1. **4 个点类型无真实窗口正例**：`sell1`、`sell2`、`buy2`、`sell1like` 在 21 窗 × 287 帧上一次 `confirmed`
   都没有。原因**尚未定性**：既可能是这些类型的门控（趋势门控 + 首次确认性回抽 + 段级要求）在日/分钟级
   冻结窗口上确实难以同时满足，也可能是「判定过严」的缺陷。**在定性前不得假设它是缺陷**。
   - 该缺口清单由 `test_zero_real_coverage_types_are_still_absent` 盯住：一旦某类型开始在真实窗口发点，
     该用例会失败并要求同步本页。
   - 缩小缺口的最直接办法是扩大冻结样本（更多标的 / 更长窗口），属 T3 范围。
2. **两张卡片位于末帧**（§3.2 类一买、§3.6 三卖），未观察到退场轨迹。需要更长窗口才能补全。
3. **区间套 / 小转大高位档在真实窗口上未观测到**：详见 §7.3。`actionable`、`third_class_confirmed`、
   `higher_level_confirmed` 只有构造回归覆盖，没有真实卡片。
4. **`precision_entry` 在已冻结的仓库产物中不存在**：4 个冻结 `tech.json` 的 `summary.precision_entry`
   均为 `None`。原因已定性（**不是**功能死链）：冻结快照取自 `data/reports/<sym>/<tf>/tech.json`，
   而该文件由 `scripts/batch_prepare_chanlun_reports.py` 产出，其 `build_technical_summary(...)` 调用
   **不传** `precision_entry`（默认 `None`）；真正会填该字段的是
   `scripts/generate_{a,h}_share_single_mixed_report.py`（`summary_payload["precision_entry"]`）。
   对比之下，`tests/test_build_miniapp_publish_bundle.py` 里的区间套断言是**手写 payload 的透传测试**，
   不校验推导，也无法用作本节的真实锚点。

### 5.1 现有 002555 锚点的可复现性问题（待处理）

`docs/chanlun/buy-sell-multi-level-visual-example-library.md` §6.6（`002555 1m -> 5M` 候选观察链）对应的
`tests/test_build_miniapp_publish_bundle.py::test_build_summary_and_detail_payload_preserve_real_1m_pre_breakout_sample`
存在两个可复现性缺陷，已实测确认：

- 该模块在**导入期**加载 `build/probe_intraday_prebreak_sample.py`，而 `build/` 是 gitignore（`git ls-files build`
  为 **0** 个文件）。在仅含已跟踪文件的树上运行该模块会在**收集阶段**直接报错：
  `FileNotFoundError: .../build/probe_intraday_prebreak_sample.py`，`no tests collected`。
- 即使本地有该文件，其 `_load_rows` 只从 `data/reports/**` 与 `data/cache/kline/**`读取，而这些目录同样
  未入版本库；数据被 `scripts/report_retention.py` 剪掉后样本即失效。

因此该锚点**不能被当作「可回归」证据**。修复方向：把区间套 / 小转大的锚点全部换成 `tests/fixtures/real/`
驱动（本页 §7 已按此口径落地），再逐步把该模块的 replay 依赖从 `build/` + `data/` 移到冻结 fixture。

## 6. 维护与验收

- BS6 验收第 1 条（「重点样例可被自动化回归支撑」）由 `tests/test_example_library_real_cases.py` 承担：
  标准点 / 类比点 7 张卡片（§3）+ 区间套 / 小转大 5 张卡片（§7）+ 两个非空转守卫 +
  两个清单同步守卫，共 **16 个用例，约 48s**。
- BS6 验收第 2 条（「新增规则能及时暴露行为变化」）由同一闸门承担：卡片钉住
  `signal_bi_id` / `related_zs_id` / `price` / `basis` / cutoff 序列（§3），以及
  `status` / `small_to_large_status` / `window_basis_label` / `nested_from.side` /
  `nested_from.trigger` / `dynamic_grade` 六元组（§7）。
- 卡片失效时的正确处置顺序：① 确认是否**有意**变更规则；② 是则更新卡片与对应表格并说明原因；
  ③ 否则按回归缺陷处理。**不要**放宽断言或删除卡片。
- 闸门自证（均已实测）：
  - 把任一标准点卡片的价格或锚点改错，**只有该卡片**失败。
  - 把任一区间套卡片的 `dynamic_grade` 改错，**只有该卡片**失败。
  - 把已观测到的 `candidate` 错误地列入「应缺席」清单，§7.3 的守卫会失败并报出实际计数——
    证明缺席断言确实在读实测计数，不是形同虚设。
- 两个「清单同步守卫」的作用：`test_zero_real_coverage_types_are_still_absent`（§5 缺口 1）与
  `test_precision_higher_states_stay_unobserved_on_real_windows`（§7.3）都带空转守卫，
  保证「未观测到」的结论建立在足够多的扫描帧上。
- 重新冻结 `tests/fixtures/real/` 会让本页全部 cutoff 与数值失效——重冻结后必须整体重跑本闸门并按
  新口径更新本节所有表格。

## 7. 区间套 / 小转大案例（T3）

与 §3 同一口径（`FIXTURES_ROOT` + `analysis_cutoffs`），但需要**同标的两个级别**：
高级别取 cutoff，次级别按**同一时刻 T** 截断（模拟生产 `_build_lower_precision_entry` 同时取两级数据），
再调 `build_lower_timeframe_precision_entry`。生产配置为：

- `PRIMARY_TECHNICAL_TIMEFRAME = "30m"`（操作级别）、`LOWER_PRECISION_TIMEFRAME = "5m"`（区间套执行级别）
- `LOWER_PRECISION_PENDING_REVERSE_MODE = "effective_only"`

### 7.1 覆盖矩阵

| 档位 | 构造 / 契约回归 | 真实窗口卡片 |
| --- | --- | --- |
| `status = standby`（上级别无窗口） | ✅ | ✅ P4 |
| `status = watch`（窗口已绑定、次级别未出点） | ✅ | ✅ P1 / P2 / P3 / P5 |
| `status = actionable`（次级别已出精确点） | ✅ | ❌ **未观测到** |
| `small_to_large_status = null` | ✅ | ✅ P4 / P5 |
| `small_to_large_status = candidate` | ✅ | ✅ P1 / P2 / P3 |
| `small_to_large_status = third_class_confirmed` | ✅ | ❌ **未观测到** |
| `small_to_large_status = higher_level_confirmed` | ✅ | ❌ **未观测到** |
| `small_to_large_reverse_confirm`（区间套反向确认） | ✅ | ❌ **未观测到** |

`window_basis_label` 三档都已取到真实样本：`中枢到锚点窗口`（P1/P3）、`离开笔窗口`（P2）、
`锚点跟踪窗口`（P5）。

### 7.2 真实卡片

| 卡片 | 组合 | 帧 / cutoff | status | small_to_large | window_basis | 侧 / 触发 | dynamic_grade | 上级别消费等级 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **P1** | `00700` 30m→5m | f9 / 915 | `watch` | `candidate` | 中枢到锚点窗口 | sell / `higher_range_divergence` | `oscillation_opportunity`（震荡机会） | `pending` |
| **P2** | `03690` 5m→1m | f11 / 1831 | `watch` | `candidate` | 离开笔窗口 | buy / `buy2like` | `warning`（警戒） | `confirmed` |
| **P3** | `000591` 1m→5m | f13 / 3500 | `watch` | `candidate` | 中枢到锚点窗口 | sell / `higher_range_divergence` | `oscillation_opportunity` | `pending` |
| **P4** | `000591` day→5m | f12 / 1200 | `standby` | `null` | — | — | — | — |
| **P5** | `000591` 1m→5m | f2 / 632 | `watch` | `null` | 锚点跟踪窗口 | buy / `higher_bottom_divergence` | — | `auxiliary` |

逐卡要点：

- **P1**：生产口径（`30m` 操作 + `5m` 执行）。上级别路线为 `higher_level_range`（盘整背驰），
  故可进入小转大判定；但 5M 窗口内**没有任何同向买卖点**（`lower signal_points = []`），
  因此只能落 `watch + candidate`。这正是「已有窗口 ≠ 已确认买点」的真实样本。
- **P2**：唯一取到 **`离开笔窗口`** 的样本（上级别已确认离开笔，窗口被收缩）。
  上级别为 `higher_level_reverse_trend` + `confirmed`，`dynamic_grade = warning`——
  说明「上级别已经很强」并不自动把小转大升档，仍取决于次级别是否出现三类点。
- **P3**：`1m` 操作 + `5m` 执行的生产口径之一，窗口极窄（`2026-09-11 09:38 → 11:11`），
  次级别同样未出点。
- **P4**：**无窗口**分支。上级别路线为 `None`，`precision_entry` 整体降级为 `standby`，
  且 `small_to_large_status` / `window_basis_label` / `dynamic_grade` 全为 `null`——
  用于锁「上级别无背驰段窗口时不得凭空给出区间套与小转大结论」。
- **P5**：上级别路线为 `last_zs_extension`（既非趋势背驰也非盘整背驰），
  故 `small_to_large_status = null` 但窗口仍然激活（`锚点跟踪窗口`）——
  用于锁「窗口激活」与「小转大候选」是**两个独立条件**，不得混为一谈。

### 7.3 实测：高位档在真实窗口上未观测到

对 5 个标的 × 6 个级别组合 × 全部 cutoff（共 **126** 帧，其中生产口径三组合 **86** 帧）实测：

| 档位 | 全部组合 | 生产口径组合 |
| --- | --- | --- |
| `status = watch` | 76 | 34 |
| `status = standby` | 50 | 38 |
| `status = watch` 且 `stl = candidate` | 21 | 14 |
| `status = actionable` | **0** | **0** |
| `small_to_large_status = third_class_confirmed` | **0** | **0** |
| `small_to_large_status = higher_level_confirmed` | **0** | **0** |

即：**`actionable` 与两档高位 `small_to_large_status` 在真实冻结窗口上一次都没出现过**，
目前只有构造回归与契约回归覆盖（`test_build_lower_timeframe_precision_entry_*`）。
所有 21 个 `candidate` 样本的 `signal_points` 都是空的。该清单由
`test_precision_higher_states_stay_unobserved_on_real_windows` 盯住（含空转守卫：
要求 `scans >= 100`、`watch >= 10`、`standby >= 5`、`candidate >= 5`）。

**不得把这当作缺陷**：`actionable` 需要「次级别出现同向且落在窗口内的精确买卖点」，
而窗口来自上级别中枢结束/离开笔完成到触发锚点之间，本身很窄；样本量（126 帧）也远小于
§3 的 287 帧语料。合理结论是「**在已覆盖的真实语料上未观测到**」，而不是「不可达」。
要定性需要更大的多级别语料。

### 7.4 与其它文档的已知不一致

- [buy-sell-multi-level-visual-example-library.md](buy-sell-multi-level-visual-example-library.md) §6.5 把
  `5M buy3 -> third_class_confirmed` 描述为「**回归卡片 B**」，这仍然准确（它是构造/契约回归）。
  但同页 §7 映射表把它与 `002555` 卡片并列在「案例 -> 回归锚点映射表」里，容易让 reviewer 以为
  两者都是真实样本——**§6.6 那张的锚点存在 §5.1 描述的可复现性问题**。
- 本页 §7.2 的 5 张卡片是这一批里**唯一**完全由冻结 fixture 驱动、可在任意机器上复现的
  区间套 / 小转大真实锚点。
