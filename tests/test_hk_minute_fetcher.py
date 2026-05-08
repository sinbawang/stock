from __future__ import annotations

import types

import pytest

from chanlun.data import hk_minute_fetcher as module


def test_resolve_xueqiu_cookies_prefers_env(monkeypatch):
    monkeypatch.setenv("XUEQIU_COOKIE", "xq_a_token=aaa; xqat=bbb")
    monkeypatch.setattr(module, "_extract_xueqiu_cookie_from_browser", lambda browser=None: {"xq_a_token": "browser"})

    cookies, source = module._resolve_xueqiu_cookies()

    assert source == "env"
    assert cookies == {"xq_a_token": "aaa", "xqat": "bbb"}


def test_resolve_xueqiu_cookies_falls_back_to_browser(monkeypatch):
    monkeypatch.delenv("XUEQIU_COOKIE", raising=False)
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