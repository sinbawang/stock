"""RS0 发布前闸门（spec §2.8）：已发布 tech.json 的 confirmed 买卖点跨帧不得凭空消失 / 翻转。

signal_repaint_violations 由 `derive_signal_lifecycle_transitions` 逐次运行对比得出并写入
`summary`。正确锚定（confirmed 只锚已确认笔 / 线段）下该集合应恒为空；非空即违反 repaint 红线。
依赖 `data/reports/**`（gitignored）真实产物，无本地报告时跳过（与 segment regression 一致）。
spec_id: SPEC.BUY_SELL.CORE。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from storage_layout import REPORTS_DIR  # noqa: E402


def _tech_json_paths() -> list[Path]:
    if not REPORTS_DIR.exists():
        return []
    return sorted(REPORTS_DIR.rglob("tech.json"))


def test_no_signal_repaint_violations_in_published_reports() -> None:
    paths = _tech_json_paths()
    if not paths:
        pytest.skip("no local tech.json reports under data/reports (gitignored)")

    offenders: list[tuple[str, object]] = []
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        violations = ((payload.get("summary") or {}).get("signal_repaint_violations")) or []
        if violations:
            offenders.append((str(path.relative_to(REPORTS_DIR)), violations))

    assert not offenders, f"confirmed 买卖点 repaint 违规（spec §2.8 红线）：{offenders}"
