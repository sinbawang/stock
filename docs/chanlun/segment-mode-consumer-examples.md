# 线段双模式最小接入示例

本页给下游消费方一个最小可运行口径：同一笔序列，如何分别消费 `theory` 与 `practical` 结果。

## 1. 适用场景

- 策略端需要“严格几何信号”与“实盘兜底信号”分层展示。
- 报告端需要在同一资产上对照两种终结口径。
- 发布端需要避免把 `pending` 误当成已终结信号。

## 2. 最小代码示例

```python
from chanlun.segment import (
    SEGMENT_BOOTSTRAP_FIRST_VALID_SEED,
    StopOutcomeCategory,
    classify_stop_reason,
    identify_segments,
)


def run_dual_mode_segments(bis):
    common_kwargs = {
        "bootstrap_mode": SEGMENT_BOOTSTRAP_FIRST_VALID_SEED,
        "strict_segment_rules": False,
    }

    theory_segments = identify_segments(
        bis,
        termination_mode="theory",
        **common_kwargs,
    )
    practical_segments = identify_segments(
        bis,
        termination_mode="practical",
        **common_kwargs,
    )

    return theory_segments, practical_segments


def summarize_confirmed_segments(segments):
    rows = []
    for segment in segments:
        category = classify_stop_reason(segment.stop_reason)
        rows.append(
            {
                "segment_id": segment.segment_id,
                "stop_reason": segment.stop_reason,
                "stop_category": category.value,
                "is_confirmed": segment.is_confirmed,
                "is_terminal": category
                in {
                    StopOutcomeCategory.THEORY_CONFIRMED,
                    StopOutcomeCategory.FALLBACK_CONFIRMED,
                },
            }
        )
    return rows
```

## 3. 消费约定（最小规则）

1. `theory` 模式
- 只把 `stop_category=theory_confirmed` 当作“严格终结”。
- `pending` 一律当作“待确认”。

2. `practical` 模式
- 可把 `theory_confirmed + fallback_confirmed` 当作“可执行终结”。
- UI 或报告需标注来源，避免把 fallback 误解为理论终结。

3. 两模式共同约束
- 若出现 `unknown`，视为契约异常，阻断发布。

## 4. 发布前最小核验

```powershell
python -m pytest -q tests/test_segment.py tests/test_segment_rediscrimination_matrix.py
python -m pytest -q tests/test_segment_regression_suite.py tests/test_segment_bootstrap_anchor.py
python -m pytest -q tests/test_segment_lesson_boundary_fixtures.py
```

## 5. 推荐接入顺序

1. 先接入本页双模式最小代码。
2. 再按 [segment-stop-reason-contract.md](segment-stop-reason-contract.md) 固化分类消费。
3. 最后接入 [segment-safety-checklist.md](segment-safety-checklist.md) 作为改动闸门。

## 6. 双模式 stop_reason 对照样例

| stop_reason | theory 消费结果 | practical 消费结果 | 说明 |
| --- | --- | --- | --- |
| `feature_sequence_fractal` | terminal（theory_confirmed） | terminal（theory_confirmed） | 理论主路径确认 |
| `feature_sequence_gap_fractal_delayed_true` | terminal（theory_confirmed） | terminal（theory_confirmed） | 缺口分型延迟确认 |
| `reverse_break` | pending（theory-mode-pending） | terminal（fallback_confirmed） | 实盘兜底确认，theory 不直接终结 |
| `same_direction_not_extending` | pending | pending | 同向推进不足，保持待确认 |
| `transition_pending` | pending | pending | 过渡态待定，不应当作终结 |

这个对照表应与 [segment-stop-reason-contract.md](segment-stop-reason-contract.md) 和 `summarize_stop_reason_outcome(...)` 保持一致。
