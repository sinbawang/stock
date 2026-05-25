from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import generate_h_share_single_compact_report as module


def test_compact_capital_flow_omits_non_operational_sections() -> None:
    text = """# 资金面评分卡: 00700 腾讯

- 市场: HK
- 交易日: 2026-05-22
- 总分: 52.5/100
- 评级: C
- 数据源: eastmoney.southbound_net_buy
- 原始引用: raw.csv
- 口径说明: very long source note

关键资金指标:
- 南向净买入: -1
- 3日南向净买入: -2

维度得分:
- 资金方向: 8.5/25

正向线索:
- 未见明显过热信号

风险线索:
- 关键资金指标出现净流出

综合判断:
资金面存在风险信号，技术面结论需要降低确认度。
"""

    lines = module._compact_capital_flow(text)
    output = "\n".join(lines)

    assert "日期: 2026-05-22" in output
    assert "评级: C / 52.5/100" in output
    assert "南向净买入" in output
    assert "资金面存在风险信号" in output
    assert "数据源" not in output
    assert "原始引用" not in output
    assert "口径说明" not in output
    assert "维度得分" not in output
    assert "资金方向" not in output


def test_generate_report_writes_compact_single_stock_text(tmp_path: Path, monkeypatch) -> None:
    meta_dir = tmp_path / "meta"
    meta_dir.mkdir()
    (meta_dir / "00700_腾讯_platform_internet_v1_blended_fundamental_brief_20260525_010000.txt").write_text(
        """腾讯基本面简报
评级: A  总分: 86.10

亮点:
- 盈利质量较好。

当前缺失字段:
- guidance_attainment

补充说明:
- 综合说明: 当前综合评级为 A，平台基本面整体处于可跟踪区间。
""",
        encoding="utf-8",
    )
    (meta_dir / "00700_腾讯_capital_flow_20260525_010000.txt").write_text(
        """# 资金面评分卡: 00700 腾讯
- 交易日: 2026-05-22
- 总分: 52.5/100
- 评级: C
- 数据源: hidden

关键资金指标:
- 南向净买入: -1

风险线索:
- 关键资金指标出现净流出

综合判断:
资金面存在风险信号。
""",
        encoding="utf-8",
    )
    (meta_dir / "00700_腾讯_tech_60m_20260525_010000.txt").write_text(
        """# 技术面观察: 00700 腾讯
- 结论: 偏空，优先减仓或兑现。
- 建议: 反抽不过 479.60 以减仓为主。

结构：
- 未确认向下笔。

信号：
- 卖点：sell_3
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "_find_latest_chart", lambda symbol, name: Path("chart.jpg"))

    path = module.generate_report(
        symbol="00700",
        name="腾讯",
        meta_dir=meta_dir,
        output_dir=tmp_path,
    )

    output = path.read_text(encoding="utf-8")
    assert "腾讯 00700｜三轴操盘摘要" in output
    assert "【基本面】" in output
    assert "【资金面】" in output
    assert "【技术面】" in output
    assert "【附件】" not in output
    assert "60M图: chart.jpg" not in output
    assert "数据源: hidden" not in output
