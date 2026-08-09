import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_cn_60m_chanlun_report as report


def test_parse_args_accepts_bootstrap_options(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prog",
            "--symbol",
            "300124",
            "--name",
            "汇川技术",
            "--bootstrap-mode",
            "skip_left_edge",
            "--bootstrap-skip-confirmed-bis",
            "3",
            "--no-strict-segment-rules",
        ],
    )

    args = report.parse_args()

    assert args.bootstrap_mode == "skip_left_edge"
    assert args.bootstrap_skip_confirmed_bis == 3
    assert args.strict_segment_rules is False
