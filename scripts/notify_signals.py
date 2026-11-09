"""扫描技术面 tech.json 中的缠论买卖点，去重后推送到飞书。

用法示例：
    # 首次建立基线（不实际推送，只记录当前信号为已通知）
    python scripts/notify_signals.py --seed-only
    # 日常：只推送新出现的买卖点
    python scripts/notify_signals.py --timeframes 30m
    # 预览将要推送的内容（不发送）
    python scripts/notify_signals.py --dry-run

凭据通过环境变量注入：FEISHU_WEBHOOK_URL（必填）、FEISHU_SIGN_SECRET（可选）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from notify.signal_notifier import (  # noqa: E402
    collect_signal_events_from_reports,
    load_market_index_advice,
    notify_new_signals,
)
from storage_layout import REPORTS_DIR, REPORTS_META_DIR  # noqa: E402


DEFAULT_STATE_FILE = REPORTS_META_DIR / "notify_state.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="扫描买卖点并推送飞书通知")
    parser.add_argument("--reports-dir", default=str(REPORTS_DIR), help="技术面报告根目录（含 <symbol>/<timeframe>/tech.json）")
    parser.add_argument("--state-file", default=str(DEFAULT_STATE_FILE), help="去重状态文件路径")
    parser.add_argument("--timeframes", nargs="*", default=None, help="仅扫描指定周期，如 30m 60m；缺省扫描全部")
    parser.add_argument("--title", default="缠论买卖点提醒", help="飞书卡片标题")
    parser.add_argument("--no-forming", action="store_true", help="只推确认买卖点，不推预备/迹象")
    parser.add_argument("--dry-run", action="store_true", help="只打印将要推送的新信号，不发送、不改状态")
    parser.add_argument("--seed-only", action="store_true", help="只把当前信号标记为已通知以建立基线，不实际推送")
    return parser.parse_args()


def run(args: argparse.Namespace) -> list:
    events = collect_signal_events_from_reports(
        args.reports_dir,
        timeframes=args.timeframes,
        include_forming=not args.no_forming,
    )
    new_events = notify_new_signals(
        events,
        state_path=args.state_file,
        title=args.title,
        market_advice=load_market_index_advice(args.reports_dir),
        dry_run=args.dry_run,
        seed_only=args.seed_only,
    )
    return new_events


def main() -> None:
    args = parse_args()
    new_events = run(args)
    if args.dry_run:
        print(f"[dry-run] 将推送 {len(new_events)} 条新信号：")
        for event in new_events:
            print(f"  - {event.symbol} {event.timeframe} {event.lifecycle_label}·{event.point_label} @ {event.time}")
        return
    if args.seed_only:
        print(f"[seed-only] 已把 {len(new_events)} 条当前信号标记为基线，未推送")
        return
    print(f"已推送 {len(new_events)} 条新买卖点信号")


if __name__ == "__main__":
    main()
