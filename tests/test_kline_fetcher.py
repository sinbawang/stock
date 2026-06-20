from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from chanlun.data import kline_fetcher


def _bar(ts: str) -> dict:
    return {
        "ts": ts,
        "open": 1.0,
        "close": 1.0,
        "high": 1.0,
        "low": 1.0,
        "volume": 1,
    }


def test_fetch_kline_intraday_uses_limit_as_target_min_rows(monkeypatch) -> None:
    monkeypatch.setattr(kline_fetcher, "_normalize_symbol", lambda symbol: "sz000001")
    monkeypatch.setattr(kline_fetcher, "_normalize_interval", lambda interval: "m60")
    monkeypatch.setattr(kline_fetcher, "_parse_time", lambda value, is_intraday: None)
    monkeypatch.setattr(kline_fetcher, "_make_opener", lambda: object())
    monkeypatch.setattr(kline_fetcher, "_fetch_intraday", lambda opener, symbol, interval, limit: [])

    called: dict[str, int] = {}

    def fake_xueqiu(norm_symbol, interval, start_dt, end_dt, adjust, min_rows):
        called["min_rows"] = min_rows
        return [_bar(f"2026-06-{day:02d} 10:30") for day in range(1, 6)]

    monkeypatch.setattr(kline_fetcher, "_fetch_intraday_xueqiu", fake_xueqiu)
    monkeypatch.setattr(kline_fetcher, "_fetch_intraday_eastmoney", lambda *args, **kwargs: [])

    rows = kline_fetcher.fetch_kline("sz000001", interval="60m", limit=5)

    assert called["min_rows"] == 5
    assert len(rows) == 5


def test_fetch_kline_intraday_clips_fallback_rows_to_limit(monkeypatch) -> None:
    monkeypatch.setattr(kline_fetcher, "_normalize_symbol", lambda symbol: "sz000001")
    monkeypatch.setattr(kline_fetcher, "_normalize_interval", lambda interval: "m60")
    monkeypatch.setattr(kline_fetcher, "_parse_time", lambda value, is_intraday: None)
    monkeypatch.setattr(kline_fetcher, "_make_opener", lambda: object())
    monkeypatch.setattr(kline_fetcher, "_fetch_intraday", lambda opener, symbol, interval, limit: [])
    monkeypatch.setattr(kline_fetcher, "_fetch_intraday_xueqiu", lambda *args, **kwargs: [_bar(f"2026-06-{day:02d} 10:30") for day in range(1, 11)])
    monkeypatch.setattr(kline_fetcher, "_fetch_intraday_eastmoney", lambda *args, **kwargs: [])

    rows = kline_fetcher.fetch_kline("sz000001", interval="60m", limit=3)

    assert len(rows) == 3
    assert [row["ts"] for row in rows] == [
        "2026-06-08 10:30",
        "2026-06-09 10:30",
        "2026-06-10 10:30",
    ]


def test_fetch_kline_intraday_source_profile_changes_a_share_order(monkeypatch) -> None:
    monkeypatch.setattr(kline_fetcher, "_normalize_symbol", lambda symbol: "sz000001")
    monkeypatch.setattr(kline_fetcher, "_normalize_interval", lambda interval: "m60")
    monkeypatch.setattr(kline_fetcher, "_parse_time", lambda value, is_intraday: None)
    monkeypatch.setattr(kline_fetcher, "_make_opener", lambda: object())

    calls: list[str] = []

    monkeypatch.setattr(
        kline_fetcher,
        "_fetch_intraday_tencent_rows",
        lambda *args, **kwargs: calls.append("tencent") or [_bar("2026-06-01 10:30")],
    )

    def fake_xueqiu(*args, **kwargs):
        calls.append("xueqiu")
        return [_bar(f"2026-06-{day:02d} 10:30") for day in range(1, 6)]

    monkeypatch.setattr(kline_fetcher, "_fetch_intraday_xueqiu", fake_xueqiu)
    monkeypatch.setattr(
        kline_fetcher,
        "_fetch_intraday_eastmoney",
        lambda *args, **kwargs: calls.append("eastmoney") or [_bar("2026-06-09 10:30")],
    )

    rows = kline_fetcher.fetch_kline("sz000001", interval="60m", limit=5, source_profile="xueqiu-first")

    assert calls == ["xueqiu"]
    assert len(rows) == 5


def test_fetch_kline_intraday_tushare_first_profile_prefers_tushare(monkeypatch) -> None:
    monkeypatch.setattr(kline_fetcher, "_normalize_symbol", lambda symbol: "sz000001")
    monkeypatch.setattr(kline_fetcher, "_normalize_interval", lambda interval: "m60")
    monkeypatch.setattr(kline_fetcher, "_parse_time", lambda value, is_intraday: None)
    monkeypatch.setattr(kline_fetcher, "_make_opener", lambda: object())

    calls: list[str] = []

    monkeypatch.setattr(
        kline_fetcher,
        "_fetch_intraday_tushare",
        lambda *args, **kwargs: calls.append("tushare") or [_bar(f"2026-06-{day:02d} 10:30") for day in range(1, 6)],
    )
    monkeypatch.setattr(
        kline_fetcher,
        "_fetch_intraday_tencent_rows",
        lambda *args, **kwargs: calls.append("tencent") or [_bar("2026-06-01 10:30")],
    )
    monkeypatch.setattr(
        kline_fetcher,
        "_fetch_intraday_xueqiu",
        lambda *args, **kwargs: calls.append("xueqiu") or [_bar("2026-06-01 10:30")],
    )
    monkeypatch.setattr(
        kline_fetcher,
        "_fetch_intraday_eastmoney",
        lambda *args, **kwargs: calls.append("eastmoney") or [_bar("2026-06-01 10:30")],
    )

    rows = kline_fetcher.fetch_kline("sz000001", interval="60m", limit=5, source_profile="tushare-first")

    assert calls == ["tushare"]
    assert len(rows) == 5
    assert kline_fetcher.get_last_fetch_metadata()["actual_source"] == "tushare"


def test_fetch_kline_intraday_metadata_tracks_fallback_source(monkeypatch) -> None:
    monkeypatch.setattr(kline_fetcher, "_normalize_symbol", lambda symbol: "sz000001")
    monkeypatch.setattr(kline_fetcher, "_normalize_interval", lambda interval: "m15")
    monkeypatch.setattr(kline_fetcher, "_parse_time", lambda value, is_intraday: None)
    monkeypatch.setattr(kline_fetcher, "_make_opener", lambda: object())

    def fake_tushare(*args, **kwargs):
        raise RuntimeError("抱歉，您访问接口(stk_mins)频率超限(1次/分钟)")

    monkeypatch.setattr(kline_fetcher, "_fetch_intraday_tushare", fake_tushare)
    monkeypatch.setattr(kline_fetcher, "_fetch_intraday_tencent_rows", lambda *args, **kwargs: [_bar("2026-06-01 10:30")])
    monkeypatch.setattr(
        kline_fetcher,
        "_fetch_intraday_xueqiu",
        lambda *args, **kwargs: [_bar(f"2026-06-{day:02d} 10:30") for day in range(1, 6)],
    )
    monkeypatch.setattr(kline_fetcher, "_fetch_intraday_eastmoney", lambda *args, **kwargs: [])

    rows = kline_fetcher.fetch_kline("sz000001", interval="15m", limit=5, source_profile="mainland")
    meta = kline_fetcher.get_last_fetch_metadata()

    assert len(rows) == 5
    assert meta["source_plan"] == "tushare->tencent->xueqiu->eastmoney"
    assert meta["actual_source"] == "xueqiu"
    assert meta["source_attempts"][0]["source"] == "tushare"
    assert meta["source_attempts"][0]["status"] == "error"
    assert meta["source_attempts"][2]["source"] == "xueqiu"
    assert meta["source_attempts"][2]["row_count"] == 5


def test_fetch_kline_daylike_mainland_profile_prefers_tushare(monkeypatch) -> None:
    monkeypatch.setattr(kline_fetcher, "_normalize_symbol", lambda symbol: "sh601328")
    monkeypatch.setattr(kline_fetcher, "_normalize_interval", lambda interval: "day")
    monkeypatch.setattr(kline_fetcher, "_parse_time", lambda value, is_intraday: None)
    monkeypatch.setattr(kline_fetcher, "_make_opener", lambda: object())

    calls: list[str] = []

    monkeypatch.setattr(
        kline_fetcher,
        "_fetch_daylike_tushare",
        lambda *args, **kwargs: calls.append("tushare") or [_bar(f"2026-06-{day:02d}") for day in range(1, 6)],
    )
    monkeypatch.setattr(
        kline_fetcher,
        "_fetch_day_like_rows",
        lambda *args, **kwargs: calls.append("day_like") or [_bar("2026-06-01")],
    )

    rows = kline_fetcher.fetch_kline("601328", interval="day", limit=5, source_profile="mainland")

    assert calls == ["tushare"]
    assert len(rows) == 5
    assert kline_fetcher.get_last_fetch_metadata()["actual_source"] == "tushare"


def test_fetch_kline_daylike_defaults_to_tushare_first_for_a_share(monkeypatch) -> None:
    monkeypatch.setattr(kline_fetcher, "_normalize_symbol", lambda symbol: "sh601328")
    monkeypatch.setattr(kline_fetcher, "_normalize_interval", lambda interval: "day")
    monkeypatch.setattr(kline_fetcher, "_parse_time", lambda value, is_intraday: None)
    monkeypatch.setattr(kline_fetcher, "_make_opener", lambda: object())

    calls: list[str] = []

    captured: dict[str, object] = {}

    def fake_daylike_tushare(norm_symbol, interval, start_dt, end_dt, adjust):
        calls.append("tushare")
        captured["adjust"] = adjust
        return [_bar(f"2026-06-{day:02d}") for day in range(1, 1006)]

    monkeypatch.setattr(kline_fetcher, "_fetch_daylike_tushare", fake_daylike_tushare)
    monkeypatch.setattr(
        kline_fetcher,
        "_fetch_day_like_rows",
        lambda *args, **kwargs: calls.append("day_like") or [_bar("2026-06-01")],
    )

    rows = kline_fetcher.fetch_kline("601328", interval="day")
    meta = kline_fetcher.get_last_fetch_metadata()

    assert calls == ["tushare"]
    assert len(rows) == 1000
    assert rows[0]["ts"] == "2026-06-06"
    assert rows[-1]["ts"] == "2026-06-1005"
    assert captured["adjust"] == ""
    assert meta["source_plan"] == "tushare->day_like"
    assert meta["actual_source"] == "tushare"


def test_fetch_kline_daylike_falls_back_to_day_like_when_tushare_fails(monkeypatch) -> None:
    monkeypatch.setattr(kline_fetcher, "_normalize_symbol", lambda symbol: "sh601328")
    monkeypatch.setattr(kline_fetcher, "_normalize_interval", lambda interval: "day")
    monkeypatch.setattr(kline_fetcher, "_parse_time", lambda value, is_intraday: None)
    monkeypatch.setattr(kline_fetcher, "_make_opener", lambda: object())

    monkeypatch.setattr(kline_fetcher, "_fetch_daylike_tushare", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("rate limit")))
    monkeypatch.setattr(
        kline_fetcher,
        "_fetch_day_like_rows",
        lambda *args, **kwargs: [_bar(f"2026-06-{day:02d}") for day in range(1, 4)],
    )

    rows = kline_fetcher.fetch_kline("601328", interval="day", limit=3, source_profile="mainland")
    meta = kline_fetcher.get_last_fetch_metadata()

    assert len(rows) == 3
    assert meta["source_plan"] == "tushare->day_like"
    assert meta["actual_source"] == "day_like"
    assert meta["source_attempts"][0]["source"] == "tushare"
    assert meta["source_attempts"][0]["status"] == "error"
    assert meta["source_attempts"][1]["source"] == "day_like"
    assert meta["source_attempts"][1]["row_count"] == 3
    assert "已回退到 day_like" in str(meta["warning"])
    assert "请求 3 根，实际返回 3 根" in str(meta["warning"])


def test_fetch_intraday_tushare_empty_raises_rate_limit_hint(monkeypatch) -> None:
    class FakeTs:
        @staticmethod
        def pro_api(token):
            return object()

        @staticmethod
        def pro_bar(**kwargs):
            return None

    monkeypatch.setenv("TUSHARE_TOKEN", "token")
    original_module = sys.modules.get("tushare")
    sys.modules["tushare"] = FakeTs
    try:
        try:
            kline_fetcher._fetch_intraday_tushare("sz000001", "m60", None, None, "qfq", 1200)
        except RuntimeError as exc:
            message = str(exc)
            assert "stk_mins" in message
            assert "1 次/分钟" in message
        else:
            raise AssertionError("expected RuntimeError")
    finally:
        if original_module is None:
            del sys.modules["tushare"]
        else:
            sys.modules["tushare"] = original_module


def test_fetch_intraday_tushare_generic_error_is_wrapped_with_hint(monkeypatch) -> None:
    class FakeTs:
        @staticmethod
        def pro_api(token):
            return object()

        @staticmethod
        def pro_bar(**kwargs):
            raise Exception("ERROR.")

    monkeypatch.setenv("TUSHARE_TOKEN", "token")
    original_module = sys.modules.get("tushare")
    sys.modules["tushare"] = FakeTs
    try:
        try:
            kline_fetcher._fetch_intraday_tushare("sz000001", "m60", None, None, "qfq", 1200)
        except RuntimeError as exc:
            message = str(exc)
            assert "Tushare A 股分钟线抓取失败" in message
            assert "stk_mins" in message
            assert "原始提示: ERROR." in message
        else:
            raise AssertionError("expected RuntimeError")
    finally:
        if original_module is None:
            del sys.modules["tushare"]
        else:
            sys.modules["tushare"] = original_module