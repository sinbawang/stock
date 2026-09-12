"""校验 `docs/chanlun/chanlun-spec-tasks.md` 的进度口径是否自洽。

背景
----
该看板曾出现两类问题（2026-09-12 核对时发现）：

1. **同页自相矛盾**：同一个任务在两处写成不同状态／百分比
   （例：`标准线段级中枢主实现` 一处「进行中 93%」、另一处「完成 94%」）。
2. **聚合值与分项脱节**：`严格理论自动化实现` / `综合进度` 是人工估算，
   与 §3.1–§3.4 分项无法互相推导（曾为 47%/60%，后为 58%/68%）。

本脚本把这两点变成机器可校验的闸门：

- `aggregate_*`：要求 §1 的 `严格理论自动化实现` == §3.1–§3.4 分项完成度的算术平均，
  `综合进度` == §1 四个维度的算术平均。
- `duplicate_*`：要求同名任务行的状态与百分比一致。

用法：``python scripts/check_spec_progress.py``（返回码非 0 表示口径不自洽）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "chanlun" / "chanlun-spec-tasks.md"

TRACKED_SECTIONS = ("3.1", "3.2", "3.3", "3.4")
PERCENT_RE = re.compile(r"^(\d{1,3})%$")
SECTION_RE = re.compile(r"^### (\S+)")
NORMALIZE_RE = re.compile(r"[\s`*\\]|（.*?）|\(.*?\)")


def _round_half_up(value: float) -> int:
    """四舍五入（half-up），避开 Python 默认的 banker's rounding 导致的复现性歧义。"""
    return int(value + 0.5)


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _normalize(name: str) -> str:
    """去掉反引号、空白与括号补充，便于跨表格比对同一任务。"""
    return NORMALIZE_RE.sub("", name)


def _parse(text: str) -> tuple[list[tuple[str, str, str, int]], list[tuple[str, str, str, str]], list[str]]:
    """返回 (分项行, 所有带百分比的表格行, 命名冲突)。"""
    tracked: list[tuple[str, str, str, int]] = []
    every: list[tuple[str, str, str, str]] = []
    problems: list[str] = []

    section = "?"
    heading = "?"
    for line in text.splitlines():
        m = SECTION_RE.match(line)
        if m:
            section = m.group(1)
        elif line.startswith("## "):
            heading = line[3:].strip()
            section = "?"

        if not line.startswith("|") or set(line) <= set("|- "):
            continue
        cells = _cells(line)
        if len(cells) < 4:
            continue

        name = cells[0]
        # §3.x 分项表列序：任务 | 状态 | 完成度 | 说明
        if section in TRACKED_SECTIONS:
            pct = PERCENT_RE.match(cells[2])
            if pct:
                tracked.append((section, name, cells[1], int(pct.group(1))))

        # 全局扫「状态 | 完成度」相邻形态：
        #   §3.x 分项表 → 任务 | 状态 | 完成度 | 说明（idx=1）
        #   §3.0A epic 表 → 任务 | 优先级 | 说明 | 状态 | 完成度 | …（idx=3）
        for idx in (1, 2, 3):
            if len(cells) > idx + 1 and PERCENT_RE.match(cells[idx + 1]) and cells[idx] in {
                "完成",
                "进行中",
                "阶段性完成",
                "待完成",
            }:
                every.append((heading, name, cells[idx], cells[idx + 1]))
                break

    # 同名任务一致性
    grouped: dict[str, list[tuple[str, str, str]]] = {}
    for head, name, status, pct in every:
        grouped.setdefault(_normalize(name), []).append((head, status, pct))
    for key, entries in grouped.items():
        if len({(s, p) for _, s, p in entries}) > 1:
            detail = " ; ".join(f"{h}: {s} {p}" for h, s, p in entries)
            problems.append(f"同名任务状态/百分比冲突 → {key}: {detail}")

    return tracked, every, problems


def _headline(text: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = _cells(line)
        if len(cells) >= 3 and PERCENT_RE.match(cells[2]):
            out[cells[0]] = int(PERCENT_RE.match(cells[2]).group(1))
    return out


def evaluate(text: str) -> tuple[list[str], list[str]]:
    """返回 (失败信息, 信息行)。纯函数，便于自检。"""
    tracked, every, problems = _parse(text)
    headline = _headline(text)
    info: list[str] = []

    if not tracked:
        return ["未解析到 §3.1–§3.4 分项行，文档结构可能已变"], info

    counts: dict[str, int] = {}
    for _, name, _, _ in every:
        key = _normalize(name)
        counts[key] = counts.get(key, 0) + 1
    multi = sum(1 for n in counts.values() if n > 1)

    values = [pct for _, _, _, pct in tracked]
    mean_tracked = _round_half_up(sum(values) / len(values))
    info.append(f"分项：{len(tracked)} 项，合计 {sum(values)}，均值 {sum(values)/len(values):.2f} → {mean_tracked}%")

    dims = ["严格理论规格整理", "原文逐课复核", "当前工程口径沉淀"]
    absent = [d for d in dims if d not in headline]
    if absent:
        return [f"§1 维度表缺少行：{absent}"], info
    mean_overall = _round_half_up((sum(headline[d] for d in dims) + mean_tracked) / 4)
    info.append(f"综合：维度 {[headline[d] for d in dims]} + 实现 {mean_tracked} → 均值 {mean_overall}%")
    info.append(f"扫描带百分比行 {len(every)} 行，同名多现 {multi} 组")

    failures = list(problems)
    if multi == 0:
        # 防止闸门静默空转：没有任何同名行可比对时，冲突校验形同虚设。
        failures.append("同名校验无可比对行（表格结构可能已变），闸门形同空转")
    for name, expected in (("严格理论自动化实现", mean_tracked), ("综合进度", mean_overall)):
        actual = headline.get(name)
        if actual is None:
            failures.append(f"§1 缺少聚合行「{name}」")
        elif actual != expected:
            failures.append(f"聚合值脱节 → 「{name}」写的是 {actual}%，应为 {expected}%")
    return failures, info


def _report(failures: list[str], info: list[str]) -> int:
    for line in info:
        print(line)
    for line in failures:
        print(f"[FAIL] {line}")
    if failures:
        return 1
    print("[OK] 进度口径自洽：聚合值可由分项推导，且无同名冲突")
    return 0


def main() -> int:
    failures, info = evaluate(DOC.read_text(encoding="utf-8"))
    return _report(failures, info)


def selftest() -> int:
    """证明两道闸门都真的会报警，而不是永远返回 OK。"""
    base = DOC.read_text(encoding="utf-8")
    problems: list[str] = []

    base_failures, _ = evaluate(base)
    if base_failures:
        problems.append(f"基线本应通过，却报错：{base_failures}")

    # 闸门 1：同名任务状态冲突
    target = "| 标准线段级中枢主实现 | 完成 | 94% |"
    if target not in base:
        problems.append(f"自检锚点缺失，无法验证同名校验：{target}")
    else:
        injected = base.replace(
            target,
            target + "\n| 标准线段级中枢主实现 | 进行中 | 93% | 自检注入 |",
            1,
        )
        dup_failures, _ = evaluate(injected)
        if not any("同名任务状态/百分比冲突" in f for f in dup_failures):
            problems.append("注入同名冲突后未被检出")

    # 闸门 2：聚合值与分项脱节
    stale = base.replace("| 综合进度 | 上表四个维度的算术平均 | 86% |", "| 综合进度 | 上表四个维度的算术平均 | 58% |", 1)
    if stale == base:
        problems.append("自检锚点缺失，无法验证聚合校验：综合进度行")
    else:
        agg_failures, _ = evaluate(stale)
        if not any("聚合值脱节" in f for f in agg_failures):
            problems.append("注入过期聚合值后未被检出")

    for line in problems:
        print(f"[FAIL] {line}")
    if problems:
        return 1
    print("[OK] 自检通过：同名冲突与聚合脱节都能被检出，闸门未空转")
    return 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else main())
