from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from chanlun.data.hk_minute_fetcher import (  # noqa: E402
    _DEFAULT_COOKIE_FILE_CANDIDATES,
    _build_xueqiu_session,
    _extract_xueqiu_cookie_from_browser,
    _parse_cookie_string,
    _resolve_xueqiu_cookie_file,
)


def _mask_cookie_value(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _summarize_cookie_text(cookie_text: str) -> str:
    cookies = _parse_cookie_string(cookie_text)
    if not cookies:
        return "present but unparsable"
    parts = [f"{key}={_mask_cookie_value(value)}" for key, value in sorted(cookies.items())]
    return "; ".join(parts)


def _print_cookie_file_status() -> None:
    explicit_path = __import__("os").environ.get("XUEQIU_COOKIE_FILE", "").strip()
    explicit = Path(explicit_path).resolve() if explicit_path else None
    print("cookie_file_candidates:")
    if explicit is not None:
        print(f"- explicit: {explicit}")
    for candidate in _DEFAULT_COOKIE_FILE_CANDIDATES:
        label = "exists" if candidate.exists() else "missing"
        print(f"- {candidate} [{label}]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose Xueqiu cookie resolution and API reachability.")
    parser.add_argument("symbol", nargs="?", default="09988", help="HK symbol used for the API probe")
    parser.add_argument("--skip-probe", action="store_true", help="Only inspect cookie sources; do not call Xueqiu APIs")
    return parser.parse_args()


def _probe_xueqiu_api(symbol: str) -> int:
    session, cookie_source = _build_xueqiu_session(symbol)
    print(f"probe_cookie_source={cookie_source}")

    quote_response = session.get(
        "https://stock.xueqiu.com/v5/stock/quote.json",
        params={"symbol": symbol, "extend": "detail"},
        timeout=20,
    )
    print(f"quote_http={quote_response.status_code}")
    quote_payload = quote_response.json()
    print(f"quote_error_code={quote_payload.get('error_code')}")

    chart_response = session.get(
        "https://stock.xueqiu.com/v5/stock/chart/kline.json",
        params={
            "symbol": symbol,
            "begin": "1717200000000",
            "period": "60m",
            "type": "before",
            "count": "-10",
            "indicator": "kline",
        },
        timeout=20,
    )
    print(f"chart_http={chart_response.status_code}")
    chart_payload = chart_response.json()
    print(f"chart_error_code={chart_payload.get('error_code')}")
    item_count = len((chart_payload.get("data") or {}).get("item") or [])
    print(f"chart_items={item_count}")

    if quote_payload.get("error_code") not in (None, 0):
        print("quote_payload_preview=" + json.dumps(quote_payload, ensure_ascii=False)[:300])
        return 1
    if chart_payload.get("error_code") not in (None, 0) or item_count == 0:
        print("chart_payload_preview=" + json.dumps(chart_payload, ensure_ascii=False)[:300])
        return 1
    return 0


def main() -> None:
    args = parse_args()
    env_cookie = (Path.cwd(),)
    raw_env_cookie = __import__("os").environ.get("XUEQIU_COOKIE", "").strip()

    print("xueqiu_cookie_diagnosis")
    if raw_env_cookie:
        print("source=env")
        print(f"env_cookie={_summarize_cookie_text(raw_env_cookie)}")
        if args.skip_probe:
            return
        raise SystemExit(_probe_xueqiu_api(args.symbol))

    resolved = _resolve_xueqiu_cookie_file()
    if resolved is not None:
        cookies, source = resolved
        masked = "; ".join(f"{key}={_mask_cookie_value(value)}" for key, value in sorted(cookies.items()))
        print(f"source={source}")
        print(f"file_cookie={masked}")
        if args.skip_probe:
            return
        raise SystemExit(_probe_xueqiu_api(args.symbol))

    _print_cookie_file_status()
    try:
        cookies = _extract_xueqiu_cookie_from_browser()
    except Exception as exc:  # noqa: BLE001
        print("source=unavailable")
        print(f"browser_error={type(exc).__name__}: {exc}")
        print("next_steps=")
        print("1. Put a full XUEQIU_COOKIE line into data/_meta/xueqiu_cookie.env")
        print("2. Or run this terminal as administrator before relying on Chrome cookie extraction")
        print("3. Or export XUEQIU_COOKIE in the same shell before running runone")
        raise SystemExit(1)

    masked = "; ".join(f"{key}={_mask_cookie_value(value)}" for key, value in sorted(cookies.items()))
    print("source=browser")
    print(f"browser_cookie={masked}")
    if args.skip_probe:
        return
    raise SystemExit(_probe_xueqiu_api(args.symbol))


if __name__ == "__main__":
    main()