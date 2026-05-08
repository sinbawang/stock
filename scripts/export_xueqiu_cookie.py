"""导出本机浏览器中的雪球 cookie，便于诊断或生成环境变量。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from chanlun.data.hk_minute_fetcher import _extract_xueqiu_cookie_from_browser


def _format_cookie(cookies: dict[str, str]) -> str:
    preferred = ["xq_a_token", "xqat", "u"]
    keys = [key for key in preferred if key in cookies] + [key for key in sorted(cookies) if key not in preferred]
    return "; ".join(f"{key}={cookies[key]}" for key in keys)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="导出本机浏览器中的雪球 cookie")
    parser.add_argument("--browser", default="auto", help="浏览器: auto/chrome/edge/brave/firefox/chromium")
    parser.add_argument("--format", default="ps1", choices=["raw", "env", "ps1"], help="输出格式")
    parser.add_argument("--output", default=None, help="输出文件；为空则打印到 stdout")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cookies = _extract_xueqiu_cookie_from_browser(args.browser)
    cookie_text = _format_cookie(cookies)

    if args.format == "raw":
        content = cookie_text
    elif args.format == "env":
        content = f"XUEQIU_COOKIE={cookie_text}"
    else:
        content = f"$env:XUEQIU_COOKIE = '{cookie_text}'"

    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content + "\n", encoding="utf-8")
        print(f"已导出到 {path}")
        return

    print(content)


if __name__ == "__main__":
    main()