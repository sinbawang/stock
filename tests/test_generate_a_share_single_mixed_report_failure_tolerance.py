"""A 股单股报告：外部数据源（基本面/资金面）失败时不得拖垮技术面报告。

事故背景（2026-11-14）：服务容器内 akshare 缺少 `stock_financial_abstract_ths`，
基本面生成抛 AttributeError → 整个 `generate_a_share_single_mixed_report.py` 子进程
exit 1 → base/fund/tech 全部 `requested_but_not_generated`，小程序上 A 股分析报告整页
消失（港股不受影响）。

本文件钉住「降级不中断」这一条红线。
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import generate_a_share_single_mixed_report as module


def _args(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        symbol="600900",
        name="长江电力",
        output_dir=str(tmp_path),
        start=None,
        end=None,
        adjust="",
        source_profile=None,
        cache_dir=str(tmp_path / "cache"),
        max_cache_age_days=7,
        skip_gen_base=False,
        skip_gen_fund=False,
        skip_gen_tech=False,
        export_structure_images=False,
        generate_lower_precision=False,
    )


def test_main_keeps_technical_report_when_fundamental_and_capital_flow_fail(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(module, "parse_args", lambda: _args(tmp_path))

    def boom(*args, **kwargs):
        raise RuntimeError(
            "akshare 缺少接口 stock_financial_abstract_ths（已安装版本 1.18.88）"
        )

    monkeypatch.setattr(module, "fetch_and_analyze_cn_blended_fundamentals", boom)
    monkeypatch.setattr(module, "fetch_and_analyze_cn_flow", boom)

    tech_path = tmp_path / "30m" / "tech.json"
    tech_path.parent.mkdir(parents=True, exist_ok=True)
    tech_path.write_text("{}", encoding="utf-8")

    def fake_save_technical_report(**kwargs):
        ref = module.TechnicalRef(conclusion="偏强", suggestion="耐心持有", path=tech_path)
        return ref, tech_path

    monkeypatch.setattr(module, "_save_technical_report", fake_save_technical_report)

    module.main()

    # 技术面仍然生成并被写进三轴报告
    assert tech_path.exists()
    overview = (tmp_path / "overview.txt").read_text(encoding="utf-8")
    assert "偏强" in overview
    assert "耐心持有" in overview
    # 基本面缺失降级为 missing 文案，而不是让进程失败
    assert "基本面: missing" in overview
    # 失败时不写 base.json / fund.json（避免污染后续「复用旧报告」判定）
    assert not (tmp_path / "base.json").exists()
    assert not (tmp_path / "fund.json").exists()
