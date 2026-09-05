from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "build" / "scan_real_candidate_new_type_samples.py"

spec = importlib.util.spec_from_file_location("scan_real_candidate_new_type_samples", MODULE_PATH)
assert spec is not None and spec.loader is not None
scan_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = scan_module
spec.loader.exec_module(scan_module)


def _latest_raw_csv(symbol: str, timeframe: str) -> Path:
    candidates = sorted(
        path
        for path in (ROOT / "data" / "reports" / symbol / timeframe / "analyze").glob(f"*_{timeframe}_*.csv")
        if "_normalized" not in path.name
    )
    assert candidates, f"no raw CSV found for {symbol} {timeframe}"
    return candidates[-1]


def test_iter_raw_csv_paths_skips_normalized_files() -> None:
    paths = scan_module.iter_raw_csv_paths(timeframes=["1m"], symbols={"06088"})

    assert paths
    assert any(path.name.startswith("06088_1m_") for path in paths)
    assert all("_normalized" not in path.name for path in paths)


def test_find_candidate_new_type_builds_payload_from_first_match(monkeypatch) -> None:
    path = ROOT / "data" / "reports" / "06088" / "1m" / "analyze" / "placeholder.csv"
    bars = [SimpleNamespace(ts=datetime(2026, 8, 25, 9, 30) + timedelta(minutes=index)) for index in range(120)]
    calls = {"load": 0, "prefixes": []}

    def fake_load_clean_bars(csv_path: Path):
        calls["load"] += 1
        assert csv_path == path
        return bars

    def fake_build_state_for_prefix(loaded_bars, count: int):
        assert loaded_bars is bars
        calls["prefixes"].append(count)
        if count < 80:
            return loaded_bars[:count], {"relationship": {"transition_state": "none"}}
        return loaded_bars[:count], {
            "relationship": {"transition_state": "candidate_new_type"},
            "current_ongoing": {"type": "range", "zs_count_so_far": 1},
            "last_completed": {"type": "down", "zs_count": 2},
            "type_chain": [{"type": "down", "status": "completed"}, {"type": "range", "status": "ongoing"}],
            "current_structure_status": "candidate_completed_waiting_stability",
            "consumption_level": "pending",
        }

    monkeypatch.setattr(scan_module, "load_clean_bars", fake_load_clean_bars)
    monkeypatch.setattr(scan_module, "build_state_for_prefix", fake_build_state_for_prefix)

    payload = scan_module.find_candidate_new_type(path, min_bars=60, step=10)

    assert calls["load"] == 1
    assert calls["prefixes"] == [60, 70, 80]
    assert payload is not None
    assert payload["symbol"] == "06088"
    assert payload["timeframe"] == "1m"
    assert payload["bar_count"] == 80
    assert payload["cutoff_ts"] == bars[79].ts.isoformat(timespec="seconds")
    assert payload["current_structure_status"] == "candidate_completed_waiting_stability"
    assert payload["same_level_consumption_level"] == "pending"
    assert payload["type_chain"] == [{"type": "down", "status": "completed"}, {"type": "range", "status": "ongoing"}]


def test_find_candidate_new_type_finds_candidate_for_00175_1m() -> None:
    # 严格同级别分解后，00175 1m 的当前 ongoing 盘整（前段已完成）即为新走势候选，
    # find_candidate_new_type 应在真实窗口命中 candidate_new_type。
    path = _latest_raw_csv("00175", "1m")

    payload = scan_module.find_candidate_new_type(path, min_bars=60, step=10)

    assert payload is not None
    assert payload["symbol"] == "00175"
    assert payload["timeframe"] == "1m"
    assert payload["current_structure_status"] == "candidate_completed_waiting_stability"
    assert payload["same_level_consumption_level"] == "pending"


def test_summarize_near_match_scores_ongoing_new_type_report(tmp_path: Path) -> None:
    tech_path = tmp_path / "00175" / "1m" / "tech.json"
    tech_path.parent.mkdir(parents=True, exist_ok=True)
    tech_path.write_text(
        json.dumps(
            {
                "symbol": "00175",
                "timeframe": "1m",
                "structure_state": {
                    "last_completed": {"type": "down"},
                    "current_ongoing": {
                        "zs_count_so_far": 2,
                        "confirmation_basis": "forming_next_same_level_zhongshu",
                    },
                    "relationship": {
                        "kind": "completed_then_new_type_ongoing",
                        "transition_state": "ongoing_new_type",
                    },
                    "current_structure_status": "completed_then_new_type",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = scan_module.summarize_near_match(tech_path)

    assert summary is not None
    assert summary.symbol == "00175"
    assert summary.timeframe == "1m"
    assert summary.ongoing_zs_count == 2
    assert summary.score == 14
    assert summary.reason == "explicit_ongoing_new_type, ongoing_zs_count=2, forming_next_same_level_zhongshu"


def test_collect_near_matches_sorts_high_score_first(monkeypatch) -> None:
    paths = [Path("a/00175/1m/tech.json"), Path("b/01339/1m/tech.json")]

    class FakeSummary:
        def __init__(self, path: str, score: int, ongoing_zs_count: int):
            self.path = path
            self.score = score
            self.ongoing_zs_count = ongoing_zs_count

        def to_dict(self):
            return {
                "path": self.path,
                "score": self.score,
                "ongoing_zs_count": self.ongoing_zs_count,
            }

    monkeypatch.setattr(scan_module, "iter_tech_json_paths", lambda **kwargs: paths)
    monkeypatch.setattr(
        scan_module,
        "summarize_near_match",
        lambda path: FakeSummary(str(path), 14 if "00175" in str(path) else 10, 2 if "00175" in str(path) else 3),
    )

    near_matches = scan_module.collect_near_matches(timeframes=["1m"], symbols=None)

    assert near_matches == [
        {"path": "a/00175/1m/tech.json", "score": 14, "ongoing_zs_count": 2},
        {"path": "b/01339/1m/tech.json", "score": 10, "ongoing_zs_count": 3},
    ]


def test_main_writes_json_output_file(monkeypatch, tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "candidate-new-type.json"
    monkeypatch.setattr(
        scan_module,
        "parse_args",
        lambda: SimpleNamespace(
            timeframes=["1m"],
            symbols=None,
            min_bars=60,
            step=10,
            limit=20,
            json=True,
            output=str(output_path),
            near_limit=10,
        ),
    )
    monkeypatch.setattr(scan_module, "iter_raw_csv_paths", lambda **kwargs: [])
    monkeypatch.setattr(scan_module, "collect_near_matches", lambda **kwargs: [{"path": "data/reports/00175/1m/tech.json", "score": 14}])
    monkeypatch.setattr(scan_module, "recommend_probe_targets", lambda near_matches, limit, symbol_name_map=None: [{"symbol": "00175", "name": "吉利汽车", "timeframe": "1m", "score": 14}])
    monkeypatch.setattr(scan_module, "load_symbol_name_map", lambda path=None: {"00175": "吉利汽车"})

    exit_code = scan_module.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == ""
    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "timeframes": ["1m"],
        "exact_candidate_matches": [],
        "near_matches": [{"path": "data/reports/00175/1m/tech.json", "score": 14}],
        "recommended_probe_targets": [{"symbol": "00175", "name": "吉利汽车", "timeframe": "1m", "score": 14}],
    }


def test_recommend_probe_targets_deduplicates_symbol_timeframe() -> None:
    near_matches = [
        {"symbol": "000651", "timeframe": "5m", "path": "a", "score": 14, "reason": "r1", "current_structure_status": "completed_then_new_type", "transition_state": "ongoing_new_type", "ongoing_zs_count": 2},
        {"symbol": "000651", "timeframe": "5m", "path": "b", "score": 13, "reason": "r2", "current_structure_status": "completed_then_new_type", "transition_state": "ongoing_new_type", "ongoing_zs_count": 3},
        {"symbol": "002555", "timeframe": "1m", "path": "c", "score": 14, "reason": "r3", "current_structure_status": "completed_then_new_type", "transition_state": "ongoing_new_type", "ongoing_zs_count": 2},
    ]

    recommendations = scan_module.recommend_probe_targets(near_matches, limit=5)
    executable = f'"{scan_module.sys.executable}"'

    assert recommendations == [
        {
            "symbol": "000651",
            "name": "占位名称",
            "timeframe": "5m",
            "path": "a",
            "score": 14,
            "reason": "r1",
            "current_structure_status": "completed_then_new_type",
            "transition_state": "ongoing_new_type",
            "ongoing_zs_count": 2,
            "exact_probe_command": f"{executable} build/probe_candidate_new_type_sample.py 000651 --name 占位名称 --timeframe 5m --target-state exact_candidate_new_type --limit 5 --output build/probe_000651_5m_exact_candidate.json",
            "new_type_zs1_probe_command": f"{executable} build/probe_candidate_new_type_sample.py 000651 --name 占位名称 --timeframe 5m --target-state new_type_zs1 --limit 5 --output build/probe_000651_5m_new_type_zs1.json",
        },
        {
            "symbol": "002555",
            "name": "占位名称",
            "timeframe": "1m",
            "path": "c",
            "score": 14,
            "reason": "r3",
            "current_structure_status": "completed_then_new_type",
            "transition_state": "ongoing_new_type",
            "ongoing_zs_count": 2,
            "exact_probe_command": f"{executable} build/probe_candidate_new_type_sample.py 002555 --name 占位名称 --timeframe 1m --target-state exact_candidate_new_type --limit 5 --output build/probe_002555_1m_exact_candidate.json",
            "new_type_zs1_probe_command": f"{executable} build/probe_candidate_new_type_sample.py 002555 --name 占位名称 --timeframe 1m --target-state new_type_zs1 --limit 5 --output build/probe_002555_1m_new_type_zs1.json",
        },
    ]


def test_load_symbol_name_map_reads_holdings_payload(tmp_path: Path) -> None:
    holdings_path = tmp_path / "stock_holdings.json"
    holdings_path.write_text(
        json.dumps(
            {
                "markets": {
                    "CN": [{"symbol": "000651", "name": "格力电器"}],
                    "HK": [{"symbol": "002555", "name": "三七互娱"}],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    symbol_name_map = scan_module.load_symbol_name_map(holdings_path)

    assert symbol_name_map == {"000651": "格力电器", "002555": "三七互娱"}