## 变更类型（勾选适用项）

- [ ] 规格变更（`docs/**/*-spec*.md` / `*-contract*.md` / `src/chanlun/*_contract.py`）
- [ ] 实现变更（`src/chanlun/**`）
- [ ] 测试变更（`tests/**`）
- [ ] 进度/任务记录更新（`docs/**/*-tasks.md`）

## Spec Change Protocol（涉及规格/契约变更时必填，见 docs/chanlun/spec-change-protocol.md）

- [ ] 1. spec 已更新，并写明变更理由 + 影响面
- [ ] 2. contract 已同步（Markdown 契约 + `src/chanlun/*_contract.py` 代码契约）
- [ ] 3. 测试已先写/改（对应 spec 规则）
- [ ] 4. 实现已改到满足 spec + 测试
- [ ] 5. `*-changelog.md` / `*-diff-matrix.md` 已回写

## 变更说明（沿用 segment-safety-checklist.md 模板）

```text
Segment Scope: <N1/N2/N3... 或具体分支名>
Expected Behavior Delta: <什么该变，什么必须不变>
Safety Gates: <跑过的命令与通过/失败摘要>
Data/Publish Impact: <对比过的 symbol/timeframe 产物>
```

## Safety Gates（勾选已跑且通过）

- [ ] `python scripts/run_segment_safety_gates.py`（本地，含真实 fixture 回归）
- [ ] `python -m pytest -q tests/`（或至少离线缠论回归子集）
- [ ] `python scripts/check_spec_change.py HEAD`（spec/contract 变更伴随 test 变更）

## 备注（可选）
