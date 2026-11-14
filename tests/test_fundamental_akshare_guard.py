"""akshare 接口特征探测：缺接口时要给「可诊断」的错误，而不是裸 AttributeError。

事故背景（2026-11-14）：容器内 akshare 缺 `stock_financial_abstract_ths` →
AttributeError 让整个 A 股报告子进程 exit 1，小程序上 A 股分析报告整页消失。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fundamental.data import cn_snapshot_fetcher as cn_fetcher  # noqa: E402


def test_akshare_attr_returns_existing_interface() -> None:
    func = cn_fetcher._akshare_attr("stock_financial_abstract_ths")
    assert callable(func)


def test_akshare_attr_reports_installed_version_when_missing(monkeypatch) -> None:
    class _FakeAk:
        __version__ = "9.9.9"

    monkeypatch.setitem(sys.modules, "akshare", _FakeAk())

    with pytest.raises(RuntimeError) as excinfo:
        cn_fetcher._akshare_attr("stock_financial_abstract_ths")

    message = str(excinfo.value)
    assert "stock_financial_abstract_ths" in message
    assert "9.9.9" in message
    assert "1.18.64" in message
