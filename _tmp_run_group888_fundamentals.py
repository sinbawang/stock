from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import traceback

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from fundamental.config.registry import get_submodel_for_symbol
from fundamental.reporting import save_blended_fundamental_brief, save_fundamental_brief
from fundamental.services import (
    fetch_and_analyze_cn_blended_fundamentals,
    fetch_and_analyze_hk_blended_fundamentals,
    fetch_and_analyze_hk_snapshot,
)
from housekeep_generated_reports import build_housekeep_plan, execute_plan
from send_wechat_current_chat_text import send_current_chat_text, send_current_chat_text_file
from send_wechat_native import send_message


PROGRESS_LOG = ROOT / "data" / "_meta" / "_tmp_group888_progress.log"
DEFAULT_MANUAL_SUPPLEMENT_DIR = ROOT / "data" / "_meta" / "manual_supplements"
SUPPORTED_HK_BLENDED_SUBMODELS = {
    "platform_internet_v1",
    "digital_infra_v1",
    "semiconductor_hardtech_v1",
    "auto_manufacturing_v1",
    "insurance_v1",
    "broker_v1",
}


def log_line(message: str) -> None:
    stamped = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
    print(stamped, flush=True)
    with PROGRESS_LOG.open("a", encoding="utf-8") as handle:
        handle.write(stamped + "\n")


def resolve_manual_supplement_path(symbol: str) -> str | None:
    candidates = sorted(DEFAULT_MANUAL_SUPPLEMENT_DIR.glob(f"{symbol}_*.*"))
    if not candidates:
        return None
    return str(candidates[0])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Temporary group888 fundamental report orchestrator.")
    parser.add_argument("--phase", choices=("generate", "send", "housekeep", "all"), default="all")
    return parser.parse_args()


def generate_reports() -> tuple[list[dict[str, object]], Path, Path]:
    holdings = json.loads((ROOT / "data" / "_meta" / "current_holdings.json").read_text(encoding="utf-8"))
    output_dir = ROOT / "data" / "_meta"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    entries: list[dict[str, object]] = []

    for market in ("CN", "HK"):
        for item in holdings.get("markets", {}).get(market, []):
            symbol = str(item["symbol"])
            name = str(item["name"])
            manual_supplement_path = resolve_manual_supplement_path(symbol)
            log_line(f"generate:start {market} {symbol} {name}")
            if market == "HK":
                submodel = get_submodel_for_symbol(symbol)
                if submodel is None:
                    raise RuntimeError(f"unable to resolve submodel for {symbol}")
                if submodel.submodel_id in SUPPORTED_HK_BLENDED_SUBMODELS:
                    result = fetch_and_analyze_hk_blended_fundamentals(
                        symbol,
                        name=name,
                        manual_supplement_path=manual_supplement_path,
                    )
                    blended = result.blended
                    report_path = save_blended_fundamental_brief(blended=blended, output_dir=output_dir)
                    annual_period = blended.annual_anchor.snapshot.report_period.isoformat()
                    interim_period = (
                        blended.interim_overlay.snapshot.report_period.isoformat()
                        if blended.interim_overlay is not None
                        else "NA"
                    )
                    rating = blended.blended_rating
                    score = blended.blended_total_score
                    freshness = blended.freshness_label
                    submodel_id = blended.submodel_id
                else:
                    result = fetch_and_analyze_hk_snapshot(
                        symbol,
                        name=name,
                        manual_supplement_path=manual_supplement_path,
                    )
                    report_path = save_fundamental_brief(
                        scorecard=result.scorecard,
                        snapshot=result.fetched.snapshot,
                        field_sources=result.fetched.field_sources,
                        output_dir=output_dir,
                    )
                    annual_period = result.fetched.snapshot.report_period.isoformat()
                    interim_period = "NA"
                    rating = result.scorecard.rating
                    score = result.scorecard.total_score
                    freshness = "snapshot_only"
                    submodel_id = result.scorecard.submodel_id
            else:
                result = fetch_and_analyze_cn_blended_fundamentals(symbol, name=name)
                blended = result.blended
                report_path = save_blended_fundamental_brief(blended=blended, output_dir=output_dir)
                annual_period = blended.annual_anchor.snapshot.report_period.isoformat()
                interim_period = blended.interim_overlay.snapshot.report_period.isoformat() if blended.interim_overlay is not None else "NA"
                rating = blended.blended_rating
                score = blended.blended_total_score
                freshness = blended.freshness_label
                submodel_id = blended.submodel_id
            log_line(f"generate:done {symbol} -> {report_path.name}")
            entries.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "market": market,
                    "rating": rating,
                    "score": score,
                    "submodel": submodel_id,
                    "freshness": freshness,
                    "annual_period": annual_period,
                    "interim_period": interim_period,
                    "path": report_path,
                }
            )

    entries.sort(key=lambda item: (-float(item["score"]), str(item["symbol"])))
    rating_buckets: dict[str, list[str]] = defaultdict(list)
    for entry in entries:
        rating_buckets[str(entry["rating"])].append(f"{entry['name']}({entry['symbol']})")

    top = entries[:3]
    bottom = list(reversed(entries[-3:]))
    overview_lines = [
        "888群 持仓基本面总览（最新批量版）",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"持仓数量：{len(entries)} 只",
        "",
        "评级分布：",
    ]
    for rating in ("A", "B", "C", "D"):
        names = rating_buckets.get(rating, [])
        overview_lines.append(f"- {rating}档：{'、'.join(names) if names else '无'}")
    overview_lines.extend(
        [
            "",
            "头部观察：" + "；".join(f"{item['name']} {float(item['score']):.2f}" for item in top),
            "尾部观察：" + "；".join(f"{item['name']} {float(item['score']):.2f}" for item in bottom),
            "",
            "明细：",
        ]
    )
    for item in entries:
        if item["freshness"] == "annual_only":
            period_text = str(item["annual_period"])
        else:
            period_text = f"{item['annual_period']} -> {item['interim_period']}"
        overview_lines.append(
            f"- {item['name']}({item['symbol']}) | {item['rating']} | {float(item['score']):.2f} | {item['submodel']} | {item['freshness']} | 报告期 {period_text}"
        )

    overview_path = output_dir / f"group888_fundamental_overview_{stamp}.txt"
    overview_path.write_text("\n".join(overview_lines) + "\n", encoding="utf-8")
    log_line(f"overview:done {overview_path.name}")

    manifest_path = output_dir / f"group888_fundamental_send_manifest_{stamp}.txt"
    manifest_lines = ["群聊 888 基本面待发送清单", "", f"综合总览: {overview_path}", ""]
    for item in entries:
        manifest_lines.append(f"{item['name']} ({item['symbol']})")
        manifest_lines.append(f"- 基本面简报: {item['path']}")
        manifest_lines.append("")
    manifest_path.write_text("\n".join(manifest_lines), encoding="utf-8")
    log_line(f"manifest:done {manifest_path.name}")
    return entries, overview_path, manifest_path


def send_to_group888(entries: list[dict[str, object]], overview_path: Path) -> None:
    intro = f"最新持仓基本面报告 {len(entries)} 份，另附综合总览 1 份。"
    log_line("send:start intro")
    send_current_chat_text(intro, duplicate_send_window_seconds=300)
    time.sleep(1.0)
    log_line(f"send:text {overview_path.name}")
    send_current_chat_text_file(overview_path, duplicate_send_window_seconds=300)
    time.sleep(0.8)
    for entry in entries:
        report_path = Path(str(entry["path"]))
        log_line(f"send:text {report_path.name}")
        send_current_chat_text_file(report_path, duplicate_send_window_seconds=300)
        time.sleep(0.8)


def housekeep() -> tuple[Path, ...]:
    data_dir = ROOT / "data"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    plan = build_housekeep_plan(data_dir, "_archive_keep_latest", stamp)
    log_line(f"housekeep:planned {len(plan.actions)} moves")
    return execute_plan(plan)


def main() -> None:
    args = parse_args()
    PROGRESS_LOG.write_text("", encoding="utf-8")

    entries: list[dict[str, object]] = []
    overview_path: Path | None = None
    manifest_path: Path | None = None

    try:
        if args.phase in {"generate", "all"}:
            entries, overview_path, manifest_path = generate_reports()
            print(f"overview={overview_path}")
            print(f"manifest={manifest_path}")
            for entry in entries:
                print(f"report={entry['path']}")

        if args.phase in {"send", "all"}:
            if not entries:
                raise RuntimeError("send phase requires generation in the same run")
            if overview_path is None:
                raise RuntimeError("missing overview path for send phase")
            send_to_group888(entries, overview_path)

        if args.phase in {"housekeep", "all"}:
            manifests = housekeep()
            for manifest in manifests:
                print(f"archive_manifest={manifest}")
    except Exception:
        log_line("error:start")
        log_line(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()