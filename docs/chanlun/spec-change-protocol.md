# Spec Change Protocol（规格变更协议）

本页把 SDD 的「规格先行」固化成可执行的五步流程，并配套 git hook 与 PR 模板。

## 适用范围

- 修改 `docs/chanlun/*-spec*.md`、`docs/chanlun/*-contract*.md`。
- 修改 `src/chanlun/*_contract.py`（机器可读契约：`zhongshu_contract.py`、`analysis_contract.py`）。
- 任何改变 `stop_reason` / `transition_state` / `consumption_level` / `zs_monitor_*` 等契约枚举的变更。

## 五步流程

任何行为变更都按下面顺序走，避免「先写代码、后补规格」的惯性：

1. **先改 spec**：在 spec 文档里写清「规则 / 术语 / 验收标准 / 变更理由 / 影响面」。不写 spec 就动手改实现，视为违规。
2. **同步 contract**：若涉及契约枚举，同时更新 Markdown 契约页与 `src/chanlun/*_contract.py`（两者必须一致，`tests/test_*_contract.py` 会校验）。
3. **先写/改测试（红）**：为改动的 spec 规则补 focused regression；先跑出失败。
4. **改实现（绿）**：改代码使 spec + 测试都通过。
5. **回写 changelog / diff-matrix**：更新 `*-changelog.md` 与 `*-diff-matrix.md`，让「应然 vs 实然」的差距可追溯。

## 机器闸门

### git pre-commit hook

安装（仓库根目录执行一次）：

```powershell
git config core.hooksPath .githooks
```

效果：任何 staged 提交里，若改动了 spec / contract（`docs/**/*-spec*.md`、`docs/**/*-contract*.md`、`src/chanlun/*_contract.py`）却没有改动 `tests/**`，提交会被阻断。

typo 勘误可显式跳过：

```powershell
$env:SPEC_CHANGE_CHECK_ALLOW_DOCS_ONLY = "1"; git commit ...
```

手动复跑检查：

```powershell
python scripts/check_spec_change.py          # 检查暂存区
python scripts/check_spec_change.py HEAD     # 检查最近一次提交
```

### CI 门禁

`.github/workflows/spec-gates.yml` 在 PR 时自动跑「纯 synthetic + 契约一致性 + 闸门逻辑」测试。依赖 `data/reports/**` 真实 CSV 快照的 regression 不在 CI 跑（`data/` 被 gitignore），这些由本地 `run_segment_safety_gates.py` 覆盖。

### 发布前闸门

`python scripts/run_segment_safety_gates.py` 覆盖「核心规则 + 契约漂移 + 回归样本 + 消费冒烟」四类护栏，见 [segment-safety-checklist.md](segment-safety-checklist.md)。

## PR 模板

见 `.github/pull_request_template.md`。涉及规格/契约变更的 PR 必须勾选五步 checklist，否则 reviewer 可以拒绝合并。

## spec 文档 frontmatter 规范

核心 spec / contract 文档顶部须带 YAML frontmatter，让 AI/工具自动发现「这份 spec 约束哪些代码、由哪些测试锁定」：

```markdown
---
spec_id: SPEC.SEGMENT.STOP_REASON
status: stable          # stable | draft | deprecated
owner: chanlun
applyTo: src/chanlun/segment.py
tests: tests/test_segment_rediscrimination_matrix.py, tests/test_segment.py
---

# 文档标题
```

`spec_id` 命名约定：`SPEC.<DOMAIN>.<TOPIC>`，例如 `SPEC.CHANLUN.THEORY`、`SPEC.SEGMENT.STOP_REASON`、`SPEC.ZHONGSHU.CORE`。代码 docstring 与测试 docstring 引用同一 `spec_id`，实现「spec ↔ 代码 ↔ 测试」三方可追溯（用 `build/scan_spec_traceability.py` 做覆盖率扫描）。

## 应然 / 实然分离规则

- **spec / contract 文档只写「应然」**：目标、术语、规则（带 spec_id）、验收标准、变更历史。不得写「当前实现是…」「现已落地…」「目前…」这类现状描述。
- **「实然」只允许出现在 `*-diff-matrix.md` 与 `*-changelog.md`**：现状 vs 目标的差距、工程近似、样本缺口都收敛到这里。
- **判别信号**：spec 正文出现「当前」「现已」「已落地」「目前」「暂」等词，大概率是实然混入应然，应搬到 diff-matrix。
- **`*-tasks.md` 例外**：任务看板本来就是进度记录，允许写「已落地 / 进行中」；但它不承担规格事实源职责。

### 待整理清单（后续分批执行）

`2026-08-23` 已全部完成应然/实然分离整理：

- `zhongshu-core-spec.md`：当前定位加实然指引 + 主链口径标「实然」。
- `chanlun-rule-spec.md`：工程化线段口径标「实然」+ diff-matrix 指引。
- `buy-sell-multi-level-spec.md`：`## 当前实现状态` 改为「实然指引」，移除开篇完成度行。
- `trend-divergence-spec.md`：`## 当前实现状态` 改为「实然指引」，移除开篇完成度行。
- `base-structure-spec.md`：移除开篇完成度行，加实然指引。

以上各 spec 的「当前实现完成度」行与「当前实现状态」节已收敛为「实然指引」+ diff-matrix / tasks 跳转；后续新增 spec 一律按此规则，不在应然正文写现状。

## 回写规则

- 线段规则变更：同步 [segment-implementation-guide.md](segment-implementation-guide.md)。
- 契约枚举变更：同步 `src/chanlun/*_contract.py` + `tests/test_*_contract.py` + Markdown 契约页。
- 总进度变化：回写 [chanlun-spec-tasks.md](chanlun-spec-tasks.md)。
