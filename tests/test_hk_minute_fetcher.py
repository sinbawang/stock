from __future__ import annotations

import argparse
import sys
import types

import pytest

from chanlun.data import hk_minute_fetcher as module


def test_hk_minute_main_parser_defaults_adjust_to_raw(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hk_minute_fetcher.py",
            "--symbol",
            "03690",
        ],
    )

    original_parse_args = argparse.ArgumentParser.parse_args
    captured = {}

    def fake_parse_args(self, *args, **kwargs):
        namespace = original_parse_args(self, *args, **kwargs)
        captured["adjust"] = namespace.adjust
        raise SystemExit(0)

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", fake_parse_args)

    with pytest.raises(SystemExit):
        module.main()

    assert captured["adjust"] == ""


def test_resolve_xueqiu_cookies_prefers_env(monkeypatch):
    monkeypatch.setenv("XUEQIU_COOKIE", "xq_a_token=aaa; xqat=bbb")
    monkeypatch.setattr(module, "_extract_xueqiu_cookie_from_browser", lambda browser=None: {"xq_a_token": "browser"})

    cookies, source = module._resolve_xueqiu_cookies()

    assert source == "env"
    assert cookies == {"xq_a_token": "aaa", "xqat": "bbb"}


def test_resolve_xueqiu_cookies_falls_back_to_browser(monkeypatch):
    monkeypatch.delenv("XUEQIU_COOKIE", raising=False)
    monkeypatch.setattr(module, "_resolve_xueqiu_cookie_file", lambda: None)
    monkeypatch.setattr(module, "_extract_xueqiu_cookie_from_browser", lambda browser=None: {"xq_a_token": "browser"})

    cookies, source = module._resolve_xueqiu_cookies()

    assert source == "browser"
    assert cookies == {"xq_a_token": "browser"}


def test_extract_xueqiu_cookie_from_browser_uses_named_loader(monkeypatch):
    class Cookie:
        def __init__(self, name, value, domain):
            self.name = name
            self.value = value
            self.domain = domain

    fake_module = types.SimpleNamespace(
        edge=lambda domain_name=None: [Cookie("xq_a_token", "token", ".xueqiu.com")],
    )
    monkeypatch.setitem(__import__("sys").modules, "browser_cookie3", fake_module)

    cookies = module._extract_xueqiu_cookie_from_browser("edge")

    assert cookies == {"xq_a_token": "token"}


def test_extract_xueqiu_cookie_from_browser_errors_when_empty(monkeypatch):
    fake_module = types.SimpleNamespace(
        edge=lambda domain_name=None: [],
        chrome=lambda domain_name=None: [],
        brave=lambda domain_name=None: [],
        chromium=lambda domain_name=None: [],
        firefox=lambda domain_name=None: [],
    )
    monkeypatch.setitem(__import__("sys").modules, "browser_cookie3", fake_module)

    with pytest.raises(RuntimeError, match="未能从本机浏览器自动读取雪球 cookie"):
        module._extract_xueqiu_cookie_from_browser()


def test_fetch_hk_minute_reports_expired_env_cookie(monkeypatch):
    def fake_fetch(*args, **kwargs):
        raise module.XueqiuCookieError("检测到环境变量 XUEQIU_COOKIE，但它可能已过期或失效。error_code=400016", "env")

    monkeypatch.setattr(module, "_fetch_hk_minute_xueqiu", fake_fetch)

    with pytest.raises(RuntimeError, match="环境变量 XUEQIU_COOKIE.*已过期或失效"):
        module.fetch_hk_minute("03690", source="xueqiu")


def test_fetch_hk_minute_reports_missing_browser_login(monkeypatch):
    def fake_fetch(*args, **kwargs):
        raise module.XueqiuCookieError("未从浏览器取得有效的雪球登录态，或浏览器里的登录态已经失效。error_code=400016", "browser")

    monkeypatch.setattr(module, "_fetch_hk_minute_xueqiu", fake_fetch)

    with pytest.raises(RuntimeError, match="浏览器.*登录态"):
        module.fetch_hk_minute("03690", source="xueqiu")


def test_fetch_hk_minute_with_policy_uses_primary_without_fallback(monkeypatch):
    monkeypatch.setattr(module, "fetch_hk_minute", lambda *args, **kwargs: [{"ts": "2026-01-01 10:00"}])

    rows, used_source = module.fetch_hk_minute_with_policy("03690")

    assert used_source == "xueqiu"
    assert rows == [{"ts": "2026-01-01 10:00"}]
    assert module.get_last_fetch_metadata()["actual_source"] == "xueqiu"


def test_fetch_hk_minute_with_policy_falls_back_when_allowed(monkeypatch):
    calls: list[str] = []

    def fake_fetch(symbol, period="60", start=None, end=None, adjust="qfq", source="xueqiu"):
        calls.append(source)
        if source == "xueqiu":
            raise RuntimeError("cookie expired")
        return [{"ts": "2026-01-01 10:00"}]

    monkeypatch.setattr(module, "fetch_hk_minute", fake_fetch)

    rows, used_source = module.fetch_hk_minute_with_policy(
        "03690",
        primary_source="xueqiu",
        fallback_sources=("akshare",),
    )

    assert calls == ["xueqiu", "akshare"]
    assert used_source == "akshare"
    assert rows == [{"ts": "2026-01-01 10:00"}]
    meta = module.get_last_fetch_metadata()
    assert meta["source_plan"] == "xueqiu->akshare"
    assert meta["actual_source"] == "akshare"
    assert meta["source_attempts"][0]["source"] == "xueqiu"
    assert meta["source_attempts"][1]["source"] == "akshare"


def test_fetch_hk_minute_with_policy_does_not_probe_other_sources_by_default(monkeypatch):
    calls: list[str] = []

    def fake_fetch(symbol, period="60", start=None, end=None, adjust="qfq", source="xueqiu"):
        calls.append(source)
        raise RuntimeError("cookie expired")

    monkeypatch.setattr(module, "fetch_hk_minute", fake_fetch)

    with pytest.raises(RuntimeError, match="尝试顺序: xueqiu"):
        module.fetch_hk_minute_with_policy("03690")

    assert calls == ["xueqiu"]


def test_fetch_hk_minute_with_policy_tries_fallback_when_primary_returns_empty(monkeypatch):
    calls: list[str] = []

    def fake_fetch(symbol, period="60", start=None, end=None, adjust="qfq", source="xueqiu"):
        calls.append(source)
        if source == "xueqiu":
            return []
        return [{"ts": "2026-01-01 10:00"}]

    monkeypatch.setattr(module, "fetch_hk_minute", fake_fetch)

    rows, used_source = module.fetch_hk_minute_with_policy(
        "03690",
        primary_source="xueqiu",
        fallback_sources=("akshare",),
    )

    assert calls == ["xueqiu", "akshare"]
    assert used_source == "akshare"
    assert rows == [{"ts": "2026-01-01 10:00"}]


def test_fetch_hk_minute_with_policy_returns_best_available_rows_when_probe_target_not_met(monkeypatch):
    calls: list[str] = []

    def fake_fetch(symbol, period="60", start=None, end=None, adjust="qfq", source="xueqiu"):
        calls.append(source)
        if source == "xueqiu":
            return [{"ts": f"2026-01-01 10:{index:02d}"} for index in range(499)]
        raise RuntimeError("remote disconnected")

    monkeypatch.setattr(module, "fetch_hk_minute", fake_fetch)

    rows, used_source = module.fetch_hk_minute_with_policy(
        "03690",
        primary_source="xueqiu",
        fallback_sources=("akshare",),
        min_rows=600,
    )

    assert calls == ["xueqiu", "akshare"]
    assert used_source == "xueqiu"
    assert len(rows) == 499


def test_fetch_hk_minute_with_policy_records_error_and_best_source(monkeypatch):
    def fake_fetch(symbol, period="60", start=None, end=None, adjust="qfq", source="xueqiu"):
        if source == "xueqiu":
            raise RuntimeError("cookie expired")
        return [{"ts": f"2026-01-01 10:{index:02d}"} for index in range(3)]

    monkeypatch.setattr(module, "fetch_hk_minute", fake_fetch)

    rows, used_source = module.fetch_hk_minute_with_policy(
        "03690",
        primary_source="xueqiu",
        fallback_sources=("akshare",),
    )
    meta = module.get_last_fetch_metadata()

    assert len(rows) == 3
    assert used_source == "akshare"
    assert meta["actual_source"] == "akshare"
    assert meta["source_attempts"][0]["status"] == "error"
    assert meta["source_attempts"][0]["error"] == "cookie expired"
    assert meta["source_attempts"][1]["row_count"] == 3


def test_main_prints_source_plan_and_actual_source(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        module,
        "fetch_hk_minute_with_policy",
        lambda *args, **kwargs: ([{"ts": "2026-01-01 10:00", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}], "xueqiu"),
    )
    monkeypatch.setattr(
        module,
        "get_last_fetch_metadata",
        lambda: {"source_plan": "xueqiu->akshare", "actual_source": "xueqiu"},
    )
    monkeypatch.setattr(module, "save_to_csv", lambda rows, filepath: None)
    monkeypatch.setattr(sys, "argv", [
        "hk_minute_fetcher.py",
        "--symbol",
        "01339",
        "--period",
        "60",
        "--output",
        str(tmp_path / "rows.csv"),
    ])

    module.main()

    output = capsys.readouterr().out
    assert "抓取链路: xueqiu->akshare" in output
    assert "实际命中源: xueqiu" in output