from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import generate_a_share_single_mixed_report as module


def test_save_combined_report_writes_latest_overview_file(tmp_path: Path) -> None:
    row = SimpleNamespace(
        target=SimpleNamespace(symbol="600900", name="长江电力"),
        fundamental=SimpleNamespace(score=82.0, rating="A"),
        technical=SimpleNamespace(conclusion="偏强", suggestion="耐心持有"),
        capital_flow=SimpleNamespace(bucket="strong", source="eastmoney", score=88.0, rating="A"),
        combined_bucket="P1",
        combined_comment="三轴共振偏强",
    )

    overview_path = module._save_combined_report(
        row=row,
        output_dir=tmp_path,
        fundamental_path=tmp_path / "base.json",
        technical_path=tmp_path / "60m" / "tech.json",
        capital_flow_path=tmp_path / "fund.json",
    )

    assert overview_path == tmp_path / "overview.txt"
    assert overview_path.exists()
    assert "600900 长江电力" in overview_path.read_text(encoding="utf-8")
    assert list(tmp_path.glob("*_mixed_overview_*.txt"))