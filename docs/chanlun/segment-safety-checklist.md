# 线段改动安全清单

本页用于把“肉眼看图”升级为“可重复、可追溯、可阻断”的改动闸门。

## 适用范围

- 修改 `src/chanlun/segment.py` 的识别逻辑、状态机、bootstrap、strict 规则。
- 修改会影响 `stop_reason` / `stop_category` 的分支判断。
- 修改会影响发布产物中 `segments` 的字段或数量。

## 提交前必跑（本地）

推荐先执行单入口闸门：

```powershell
python scripts/run_segment_safety_gates.py
```

需要缩小范围时可用：

```powershell
python scripts/run_segment_safety_gates.py --only core consumer
```

下列命令保留为明细拆分入口：

1. 核心规则、契约一致性与回归样本

```powershell
python -m pytest -q tests/test_segment.py tests/test_segment_rediscrimination_matrix.py tests/test_zhongshu_contract.py tests/test_analysis_contract.py tests/test_segment_regression_000591.py tests/test_segment_regression_000651.py tests/test_segment_regression_00700.py tests/test_segment_regression_00728.py tests/test_segment_regression_03690.py tests/test_segment_regression_300124.py
```

2. 起点锚定与跨周期一致性

```powershell
python -m pytest -q tests/test_segment_bootstrap_anchor.py tests/test_segment_regression_suite.py
```

3. 段链完整性（截断 / 塌陷类缺陷）

```powershell
python -m pytest -q tests/test_segment_chain_integrity.py
```

该闸门对全部冻结真实窗口断言段链非空、覆盖率与段间跳空在阈值内、且 `practical / theory`
段数不塌陷；用于拦截「段链静默截断、安静少给结构」这一类不报错但丢数据的缺陷。

4. 下游链完整性（中枢 / 类中枢停滞类缺陷）

```powershell
python -m pytest -q tests/test_downstream_chain_integrity.py
```

该闸门对全部冻结真实窗口断言「段 → 标准中枢」与「确认笔 → 笔级类中枢」的推进程度：
段链/确认笔足够多时下游层不得为空，且覆盖位置不得离尾部过远（lag 比例阈值）。
用于拦截「中枢只建在头部几段」这类同样不报错、只是安静少给结构的退化。

5. 发布产物一致性（对照脚本）

```powershell
python build/compare_json_segments.py
python build/verify_01024_cloud_chart.py
```

## 判失败标准（任一命中即阻断）

- 任一 pytest 用例失败。
- 出现 `StopOutcomeCategory.UNKNOWN` 或等价未知分类漂移。
- 对照脚本出现 `segments` 关键字段不一致（数量、方向、起止时间、确认状态）。
- 同一改动在 theory/practical 模式下出现未预期的大幅分歧，且没有文档说明。

## 变更说明模板（建议）

把下面 4 行放进 PR/提交说明，避免口头解释丢失：

```text
Segment Scope: (N1/N2/N3... or concrete branch names)
Expected Behavior Delta: (what should change, what must stay unchanged)
Safety Gates: (list exact commands and pass/fail summary)
Data/Publish Impact: (which symbol/timeframe artifacts were compared)
```

## 最小发布前核验

- 挑 1 只 A 股 + 1 只港股，至少覆盖 `1m/5m/30m/day` 中的 2-3 个周期。
- 对比本地与云端同标的同周期 `charts/*.json` 的 `segments`。
- 记录首次差异位置（若有）与 stop_reason 分类变化。

## 出站门槛（再进入中枢开发前）

- 线段相关回归连续 3 次改动全绿。
- `stop_reason` 契约页与实现保持一致：
  - [segment-stop-reason-contract.md](segment-stop-reason-contract.md)
  - [segment-implementation-guide.md](segment-implementation-guide.md)
- 至少 1 轮本地与云端关键样本一致性核验通过。

## 关联文档

- 现行实现口径： [segment-implementation-guide.md](segment-implementation-guide.md)
- 稳定接口契约： [segment-stop-reason-contract.md](segment-stop-reason-contract.md)
- 线段文档导航： [segment-doc-map.md](segment-doc-map.md)
- 原文对照与任务看板： [../analysis/chanlun-line-segment-original-and-comparison.md](../analysis/chanlun-line-segment-original-and-comparison.md)
