"""看板进度口径闸门测试。

`docs/chanlun/chanlun-spec-tasks.md` 曾同时存在两类口径缺陷：

1. 同一个任务在两处写成不同状态／百分比（例：`标准线段级中枢主实现` 一处「进行中 93%」、
   另一处「完成 94%」；`中枢严格定义图示库` 一处 87%、另一处 82%）。
2. `严格理论自动化实现` / `综合进度` 是人工估算（曾为 47%/60%，后为 58%/68%），
   与 §3.1–§3.4 分项无法互相推导，读者无法复算。

`scripts/check_spec_progress.py` 把这两点变成可校验规则，本测试把它锁进 CI，并额外
用合成文档验证闸门**真的会报警**（防止闸门静默空转 —— 这类空转缺陷本仓库已出现过）。
"""

import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
DOC = ROOT / "docs" / "chanlun" / "chanlun-spec-tasks.md"

_spec = importlib.util.spec_from_file_location(
    "check_spec_progress",
    SCRIPTS / "check_spec_progress.py",
)
module = importlib.util.module_from_spec(_spec) if _spec and _spec.loader else None
if module is not None:
    sys.modules[_spec.name] = module
    _spec.loader.exec_module(module)
else:
    raise RuntimeError("failed to load check_spec_progress.py for tests")


# --- 合成文档：不依赖真实看板的具体数字，确保注入验证不会被文档改动带偏 ---

_SYNTHETIC_HEADER = """| 维度 | 说明 | 完成度 |
| --- | --- | --- |
| 严格理论规格整理 | x | 80% |
| 原文逐课复核 | x | 90% |
| 当前工程口径沉淀 | x | 70% |
| 严格理论自动化实现 | x | 80% |
| 综合进度 | x | 80% |
"""

_SYNTHETIC_TABLE = """
### 3.1

| 任务 | 状态 | 完成度 | 说明 |
| --- | --- | --- | --- |
| 甲 | 完成 | 80% | x |
| 甲 | 完成 | 80% | y |
"""


def _synthetic(header: str = _SYNTHETIC_HEADER, extra_table_rows: str = "") -> str:
    return header + _SYNTHETIC_TABLE + extra_table_rows


def test_synthetic_baseline_passes() -> None:
    failures, _ = module.evaluate(_synthetic())

    assert failures == [], f"合成基线应通过，却报错：{failures}"


def test_gate_detects_same_name_status_conflict() -> None:
    """同名任务状态/百分比冲突必须被检出（历史缺陷 1）。"""
    text = _synthetic(extra_table_rows="| 甲 | 进行中 | 80% | z |\n")

    failures, _ = module.evaluate(text)

    assert any("同名任务状态/百分比冲突" in f for f in failures), failures


def test_gate_detects_percent_conflict_with_same_status() -> None:
    text = _synthetic(extra_table_rows="| 甲 | 完成 | 93% | z |\n")

    failures, _ = module.evaluate(text)

    assert any("同名任务状态/百分比冲突" in f for f in failures), failures


def test_gate_detects_aggregate_drift() -> None:
    """聚合值与分项脱节必须被检出（历史缺陷 2）。"""
    stale = _synthetic().replace("| 综合进度 | x | 80% |", "| 综合进度 | x | 58% |", 1)

    failures, info = module.evaluate(stale)

    assert any("聚合值脱节" in f and "综合进度" in f for f in failures), (failures, info)


def test_gate_detects_implementation_aggregate_drift() -> None:
    stale = _synthetic().replace("| 严格理论自动化实现 | x | 80% |", "| 严格理论自动化实现 | x | 58% |", 1)

    failures, _ = module.evaluate(stale)

    assert any("聚合值脱节" in f and "严格理论自动化实现" in f for f in failures), failures


def test_gate_flags_vacuous_same_name_scan() -> None:
    """没有任何同名行可比对时，同名校验形同空转，必须显式报错而不是静默通过。"""
    unique = _SYNTHETIC_HEADER + """
### 3.1

| 任务 | 状态 | 完成度 | 说明 |
| --- | --- | --- | --- |
| 甲 | 完成 | 80% | x |
"""

    failures, info = module.evaluate(unique)

    assert any("空转" in f for f in failures), (failures, info)


def test_rounding_is_half_up_not_bankers() -> None:
    """85.5 必须进位到 86，避免 banker's rounding 造成不可复现的口径分歧。"""
    assert module._round_half_up(85.5) == 86
    assert module._round_half_up(81.65) == 82
    assert module._round_half_up(80.5) == 81


def test_selftest_passes() -> None:
    assert module.selftest() == 0


# --- 真实看板：这才是真正的闸门 ---


def test_real_board_is_self_consistent() -> None:
    failures, info = module.evaluate(DOC.read_text(encoding="utf-8"))

    assert failures == [], f"看板口径不自洽：{failures}\n{info}"


def test_real_board_has_duplicate_groups_to_cross_check() -> None:
    """守门测试：若合并表格导致同名行少于 2 组，同名校验会失去意义，需要显式复核。"""
    _, info = module.evaluate(DOC.read_text(encoding="utf-8"))

    scanned = next(line for line in info if "同名多现" in line)

    assert "同名多现 0 组" not in scanned, f"同名校验已无可比对行：{scanned}"


def test_real_board_aggregates_match_arithmetic_mean() -> None:
    text = DOC.read_text(encoding="utf-8")
    tracked, _, _ = module._parse(text)
    headline = module._headline(text)

    values = [pct for _, _, _, pct in tracked]
    expected_impl = module._round_half_up(sum(values) / len(values))
    dims = ["严格理论规格整理", "原文逐课复核", "当前工程口径沉淀"]
    expected_overall = module._round_half_up((sum(headline[d] for d in dims) + expected_impl) / 4)

    assert headline["严格理论自动化实现"] == expected_impl
    assert headline["综合进度"] == expected_overall
    assert expected_impl >= 70, "实现口径低于 70% 时请确认是否漏改了已完成分项"


@pytest.mark.parametrize(
    "task",
    ["类中枢与标准中枢字段完全拆分", "趋势背驰严格自动判定", "盘整背驰严格自动判定"],
)
def test_previously_stale_items_are_marked_complete(task: str) -> None:
    """这三项曾滞留「进行中」，已按模块看板与代码证据订正为「完成」，防止回退。"""
    tracked, _, _ = module._parse(DOC.read_text(encoding="utf-8"))
    rows = [row for row in tracked if row[1] == task]

    assert rows, f"看板中找不到分项：{task}"
    assert all(row[2] == "完成" for row in rows), rows
