from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

module_spec = importlib.util.spec_from_file_location(
    "batch_generate_and_send_portfolio_mixed_reports",
    SCRIPTS / "batch_generate_and_send_portfolio_mixed_reports.py",
)
assert module_spec and module_spec.loader
module = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = module
module_spec.loader.exec_module(module)


def test_generate_bundle_runs_three_timeframe_chart_pipeline(monkeypatch, tmp_path):
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "SCRIPTS", tmp_path / "scripts")
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "_meta").mkdir(parents=True, exist_ok=True)

    report_root = tmp_path / "data" / "reports" / "00728"
    mixed_report = report_root / "60m" / "report.txt"
    technical_report = report_root / "60m" / "tech.json"
    capital_flow_report = report_root / "capital_flow.txt"
    combined_report = report_root / "combined.txt"

    commands: list[list[str]] = []

    def fake_run_command(command: list[str]) -> str:
        commands.append(command)
        if command[1].endswith("generate_h_share_single_mixed_report.py"):
            mixed_report.parent.mkdir(parents=True, exist_ok=True)
            mixed_report.write_text("mixed", encoding="utf-8")
            technical_report.write_text("{}", encoding="utf-8")
            capital_flow_report.write_text("capital", encoding="utf-8")
            combined_report.write_text("combined", encoding="utf-8")
            return "\n".join(
                [
                    f"fundamental_brief={report_root / 'fundamental.txt'}",
                    f"technical_report={technical_report}",
                    f"capital_flow_report={capital_flow_report}",
                    f"combined_report={combined_report}",
                    "combined_bucket=confirming",
                ]
            )

        if command[1].endswith("batch_prepare_chanlun_reports.py"):
            holdings_path = Path(command[3])
            payload = json.loads(holdings_path.read_text(encoding="utf-8"))
            assert payload == {
                "markets": {
                    "CN": [],
                    "HK": [{"symbol": "00728", "name": "中国电信"}],
                }
            }
            for timeframe in ("day", "60m", "15m"):
                timeframe_dir = report_root / timeframe
                timeframe_dir.mkdir(parents=True, exist_ok=True)
                (timeframe_dir / "structure.jpg").write_text("jpg", encoding="utf-8")
                (timeframe_dir / "structure.svg").write_text("svg", encoding="utf-8")
            return "Prepared 中国电信"

        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(module, "_run_command", fake_run_command)
    monkeypatch.setattr(module, "_should_reuse_existing_base", lambda holding, skip_gen_base: True)

    bundle = module.generate_bundle(module.Holding(market="HK", symbol="00728", name="中国电信"))

    assert len(commands) == 2
    assert commands[0][1].endswith("generate_h_share_single_mixed_report.py")
    assert commands[1][1].endswith("batch_prepare_chanlun_reports.py")
    assert commands[1][2] == "--holdings-file"
    assert bundle.chart_jpg == report_root / "60m" / "structure.jpg"
    assert bundle.chart_svg == report_root / "60m" / "structure.svg"
    assert (report_root / "day" / "structure.jpg").exists()
    assert (report_root / "15m" / "structure.jpg").exists()