from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from chanlun.bi import identify_bis
from chanlun.data import read_bars_from_csv
from chanlun.data.cleaner import clean_bars
from chanlun.data.hk_fetcher import fetch_hk_daily, save_to_csv as save_hk_daily_csv
from chanlun.data.hk_minute_fetcher import fetch_hk_minute, save_to_csv as save_hk_minute_csv
from chanlun.data.kline_fetcher import fetch_kline, save_to_csv as save_kline_csv
from chanlun.fractal import filter_consecutive_fractals, identify_fractals
from chanlun.normalize import normalize_bars
from chanlun.zhongshu import identify_zhongshu

from export_structures_with_boxes import (
    calculate_macd,
    export_bis,
    export_confirmed_fractals,
    export_fractals,
    export_macd,
    export_zhongshus,
    write_svg_with_inclusion_boxes,
)
from prepare_and_send_wechat_chart import derive_output_paths, derive_wechat_output_dir, make_sendable_jpg, render_svg
from run_hk_60m_chanlun_to_wechat import analyze_current_state, compute_bi_strengths, write_normalized_csv
from send_wechat_native import send_message


@dataclass(frozen=True)
class Security:
    symbol: str
    name: str
    market: str


SECURITIES = [
    Security("03690", "美团", "HK"),
    Security("01339", "中国人保", "HK"),
    Security("300124", "汇川技术", "A"),
    Security("00728", "中国电信", "HK"),
    Security("000591", "太阳能", "A"),
    Security("02357", "中航科工", "HK"),
    Security("002555", "三七互娱", "A"),
    Security("01024", "快手", "HK"),
    Security("00700", "腾讯", "HK"),
    Security("00981", "中芯国际", "HK"),
]

DEFAULT_HOLDINGS_FILE = ROOT / "data" / "_meta" / "current_holdings.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量生成最新日线和 60M 缠论图、分析文本、操作建议，并可选发送到当前微信会话")
    parser.add_argument("--day-start", default="2026-01-01", help="日线起始日期")
    parser.add_argument("--m60-start", default="2026-01-01 09:30", help="60M 起始时间")
    parser.add_argument(
        "--holdings-file",
        default=str(DEFAULT_HOLDINGS_FILE),
        help="持仓清单 JSON 文件，默认读取 data/_meta/current_holdings.json；不存在时回退到脚本内置名单。",
    )
    parser.add_argument("--send-current-chat", action="store_true", help="生成完成后发送到当前已打开微信会话")
    parser.add_argument("--send-only", action="store_true", help="只发送已生成的最新报告和图片，不重新生成")
    parser.add_argument("--target-label", default="888", help="仅用于日志展示的目标名称")
    return parser.parse_args()


def _market_code_to_security_market(market_code: str, symbol: str) -> str:
    if market_code == "HK":
        return "HK"
    if market_code == "CN":
        return "A"
    return "HK" if len(symbol) == 5 else "A"


def load_securities(holdings_file: Path | None = None) -> list[Security]:
    holdings_path = holdings_file or DEFAULT_HOLDINGS_FILE
    if not holdings_path.exists():
        return SECURITIES

    payload = json.loads(holdings_path.read_text(encoding="utf-8"))
    raw_entries: list[tuple[str | None, dict]] = []
    markets = payload.get("markets")
    if isinstance(markets, dict):
        for market_code, market_holdings in markets.items():
            if not isinstance(market_holdings, list):
                continue
            raw_entries.extend((market_code, entry) for entry in market_holdings if isinstance(entry, dict))
    else:
        for entry in payload.get("holdings", []):
            if isinstance(entry, dict):
                raw_entries.append((payload.get("market"), entry))

    dedup: dict[str, Security] = {}
    for market_code, entry in raw_entries:
        symbol = str(entry.get("symbol") or "").strip()
        name = str(entry.get("name") or "").strip()
        if not symbol or not name:
            continue
        dedup[f"{symbol}:{name}"] = Security(
            symbol=symbol,
            name=name,
            market=_market_code_to_security_market(str(market_code or "").upper(), symbol),
        )
    return list(dedup.values()) or SECURITIES


def fetch_day_rows(security: Security, start: str) -> list[dict]:
    if security.market == "HK":
        return fetch_hk_daily(security.symbol, start=start)
    return fetch_kline(security.symbol, start=start, interval="day")


def fetch_m60_rows(security: Security, start: str) -> list[dict]:
    if security.market == "HK":
        return fetch_hk_minute(security.symbol, period="60", start=start, adjust="qfq", source="xueqiu")
    return fetch_kline(security.symbol, start=start, interval="m60")


def save_rows(security: Security, timeframe: str, rows: list[dict], path: Path) -> None:
    if timeframe == "day":
        if security.market == "HK":
            save_hk_daily_csv(rows, str(path))
        else:
            save_kline_csv(rows, str(path))
        return

    if security.market == "HK":
        save_hk_minute_csv(rows, str(path))
    else:
        save_kline_csv(rows, str(path))


def extract_signals(bis, zhongshus, macd_points) -> dict[str, object]:
    confirmed_bis = [bi for bi in bis if bi.is_confirmed]
    strengths = compute_bi_strengths(bis, macd_points)
    latest_confirmed_up = next((bi for bi in reversed(confirmed_bis) if bi.is_up()), None)
    previous_confirmed_up = None
    if latest_confirmed_up is not None:
        seen_latest = False
        for bi in reversed(confirmed_bis):
            if bi.bi_id == latest_confirmed_up.bi_id:
                seen_latest = True
                continue
            if seen_latest and bi.is_up():
                previous_confirmed_up = bi
                break

    latest_down = next((bi for bi in reversed(bis) if bi.is_down()), None)
    top_divergence = False
    if latest_confirmed_up and previous_confirmed_up:
        last_strength = strengths.get(latest_confirmed_up.bi_id, {})
        prev_strength = strengths.get(previous_confirmed_up.bi_id, {})
        top_divergence = (
            latest_confirmed_up.high > previous_confirmed_up.high
            and last_strength.get("macd_sum_abs", 0.0) < prev_strength.get("macd_sum_abs", 0.0)
        )

    bottom_divergence = False
    previous_confirmed_down = next((bi for bi in reversed(confirmed_bis) if bi.is_down()), None)
    if latest_down and previous_confirmed_down and latest_down.bi_id != previous_confirmed_down.bi_id:
        last_strength = strengths.get(latest_down.bi_id, {})
        prev_strength = strengths.get(previous_confirmed_down.bi_id, {})
        bottom_divergence = (
            latest_down.low < previous_confirmed_down.low
            and last_strength.get("macd_sum_abs", 0.0) < prev_strength.get("macd_sum_abs", 0.0)
        )

    current_zs = zhongshus[-1] if zhongshus else None
    buy_points: list[str] = []
    sell_points: list[str] = []
    if current_zs and latest_down and bottom_divergence and latest_down.low <= current_zs.zs_low:
        buy_points.append("buy_1")
    if current_zs and latest_confirmed_up and top_divergence and latest_confirmed_up.high >= current_zs.zs_high:
        sell_points.append("sell_1")
    if current_zs and latest_confirmed_up and latest_confirmed_up.high > current_zs.zs_high and latest_down and latest_down.low >= current_zs.zs_high:
        buy_points.append("buy_3")
    if current_zs and latest_down and latest_down.low < current_zs.zs_low and latest_confirmed_up and latest_confirmed_up.high <= current_zs.zs_low:
        sell_points.append("sell_3")
    return {
        "current_zs": current_zs,
        "latest_confirmed_up": latest_confirmed_up,
        "latest_down": latest_down,
        "top_divergence": top_divergence,
        "bottom_divergence": bottom_divergence,
        "buy_points": buy_points,
        "sell_points": sell_points,
    }


def build_advice(name: str, timeframe_label: str, raw_bars, signals: dict[str, object]) -> str:
    current_zs = signals["current_zs"]
    latest_up = signals["latest_confirmed_up"]
    latest_down = signals["latest_down"]
    buy_points = signals["buy_points"]
    sell_points = signals["sell_points"]
    top_divergence = signals["top_divergence"]
    bottom_divergence = signals["bottom_divergence"]
    close_price = raw_bars[-1].close

    lines = [f"【{name} {timeframe_label} 操作建议】"]
    if buy_points:
        stop_hint = f"{latest_down.low:.2f}" if latest_down else "最近低点"
        lines.extend(
            [
                "结论：偏多，允许轻仓试错。",
                f"理由：出现 {'、'.join(buy_points)}，结构上已有缠论买点雏形。",
                f"建议：分批试仓，跌破 {stop_hint} 则严格止损。",
            ]
        )
    elif sell_points:
        reduce_hint = f"{latest_up.high:.2f}" if latest_up else "最近高点"
        lines.extend(
            [
                "结论：偏空，优先减仓或兑现。",
                f"理由：出现 {'、'.join(sell_points)}，结构偏向卖点。",
                f"建议：反抽不过 {reduce_hint} 以减仓为主，不逆势加仓。",
            ]
        )
    elif current_zs and latest_down and latest_down.low < current_zs.zs_low:
        lines.extend(
            [
                "结论：偏弱，先观望。",
                f"理由：价格仍在最新中枢下沿 {current_zs.zs_low:.2f} 下方。",
                f"建议：等待重新站回 {current_zs.zs_low:.2f}-{current_zs.zs_high:.2f} 再考虑参与，未站回前不追。",
            ]
        )
    elif current_zs and close_price >= current_zs.zs_high:
        lines.extend(
            [
                "结论：偏强，持有为主。",
                f"理由：价格运行在中枢上沿 {current_zs.zs_high:.2f} 附近或上方。",
                f"建议：已有仓位可继续持有，回踩不破 {current_zs.zs_high:.2f} 再考虑加仓。",
            ]
        )
    elif current_zs:
        lines.extend(
            [
                "结论：震荡，等待方向选择。",
                f"理由：当前主要围绕中枢 {current_zs.zs_low:.2f}-{current_zs.zs_high:.2f} 波动。",
                "建议：中枢内少折腾，等向上离开或向下跌破后再做决策。",
            ]
        )
    else:
        lines.extend(
            [
                "结论：信号一般，保持耐心。",
                "理由：当前尚未形成清晰中枢和明确买卖点。",
                "建议：只做跟踪，不做主观重仓下注。",
            ]
        )

    if bottom_divergence and not buy_points:
        lines.append("补充：已有底背驰迹象，但买点尚未确认，最多列入观察名单。")
    if top_divergence and not sell_points:
        lines.append("补充：已有顶背驰迹象，若后续反弹无力，应优先考虑保护利润。")
    lines.append("说明：以上仅基于缠论结构与 MACD 强弱，不构成投资建议。")
    return "\n".join(lines)


def export_case(security: Security, timeframe: str, rows: list[dict], base_dir: Path, stem: str, title: str) -> dict[str, Path]:
    prefix = f"{stem}_normalized"
    raw_csv = base_dir / f"{stem}.csv"
    normalized_csv = base_dir / f"{prefix}.csv"
    svg = base_dir / f"{prefix}_with_boxes.svg"
    png, jpg = derive_output_paths(svg)
    analysis_path = base_dir / f"{prefix}_analysis.txt"
    advice_path = base_dir / f"{prefix}_advice.txt"
    report_path = base_dir / f"{prefix}_report.txt"

    save_rows(security, timeframe, rows, raw_csv)
    raw_bars = clean_bars(read_bars_from_csv(str(raw_csv)))
    normalized_bars = normalize_bars(raw_bars)
    write_normalized_csv(normalized_csv, normalized_bars)
    fractals = filter_consecutive_fractals(identify_fractals(normalized_bars))
    bis = identify_bis(fractals, normalized_bars)
    confirmed_bis = [bi for bi in bis if bi.is_confirmed]
    zhongshus = identify_zhongshu(confirmed_bis)
    macd_points = calculate_macd(raw_bars)

    confirmed_fx_ids: set[int] = set()
    for bi in bis:
        if bi.is_confirmed:
            confirmed_fx_ids.add(bi.start_fx_id)
            confirmed_fx_ids.add(bi.end_fx_id)
    unconfirmed_end_fx_ids = {bi.end_fx_id for bi in bis if not bi.is_confirmed}

    export_fractals(base_dir / f"{prefix}_fractals.csv", normalized_bars, fractals, confirmed_fx_ids, unconfirmed_end_fx_ids)
    export_confirmed_fractals(base_dir / f"{prefix}_confirmed_fractals.csv", normalized_bars, fractals, confirmed_fx_ids)
    export_bis(base_dir / f"{prefix}_bis.csv", bis)
    export_zhongshus(base_dir / f"{prefix}_zhongshu.csv", zhongshus)
    export_macd(base_dir / f"{prefix}_macd.csv", macd_points)
    normalized_shims = [
        type(
            "NormalizedCsvRowShim",
            (),
            {
                "idx": bar.idx,
                "ts_start": bar.ts_start,
                "ts_end": bar.ts_end,
                "ts_high": bar.ts_high,
                "ts_low": bar.ts_low,
                "high": bar.high,
                "low": bar.low,
                "direction": bar.direction or "",
                "src_indices": bar.src_indices,
            },
        )()
        for bar in normalized_bars
    ]
    write_svg_with_inclusion_boxes(
        raw_bars,
        normalized_shims,
        fractals,
        confirmed_fx_ids,
        bis,
        zhongshus,
        macd_points,
        svg,
        title,
    )
    render_svg(svg, png)
    make_sendable_jpg(png, jpg)

    analysis_text = analyze_current_state(security.name, raw_bars, bis, zhongshus, macd_points)
    if timeframe == "day":
        analysis_text = analysis_text.replace("60M", "日线")
        timeframe_label = "日线"
    else:
        timeframe_label = "60M"
    signals = extract_signals(bis, zhongshus, macd_points)
    advice_text = build_advice(security.name, timeframe_label, raw_bars, signals)
    report_text = analysis_text + "\n\n" + advice_text + "\n"

    analysis_path.write_text(analysis_text + "\n", encoding="utf-8")
    advice_path.write_text(advice_text + "\n", encoding="utf-8")
    report_path.write_text(report_text, encoding="utf-8")
    return {
        "analysis": analysis_path,
        "advice": advice_path,
        "report": report_path,
        "jpg": jpg,
        "png": png,
        "svg": svg,
    }


def build_send_text(security: Security, day_report: Path, m60_report: Path) -> str:
    return (
        f"【{security.name} {security.symbol}】\n\n"
        f"{day_report.read_text(encoding='utf-8').strip()}\n\n"
        f"{m60_report.read_text(encoding='utf-8').strip()}"
    )


def build_send_text_60m_only(security: Security, m60_report: Path) -> str:
    return f"【{security.name} {security.symbol} 60M】\n\n{m60_report.read_text(encoding='utf-8').strip()}"


def _extract_summary_line(advice_path: Path, prefix: str) -> str:
    for raw_line in advice_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    return ""


def build_group_operation_summary(bundle: list[tuple[Security, dict[str, Path], dict[str, Path]]]) -> str:
    lines = [
        "【全部持仓 60M 缠论综合操作建议】",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"覆盖数量：{len(bundle)} 只持仓",
        "",
        "逐只建议：",
    ]

    bullish: list[str] = []
    neutral: list[str] = []
    bearish: list[str] = []

    for security, _day_case, m60_case in bundle:
        conclusion = _extract_summary_line(m60_case["advice"], "结论：") or "信号一般，保持耐心。"
        suggestion = _extract_summary_line(m60_case["advice"], "建议：") or "继续跟踪后续一笔与中枢突破。"
        lines.append(f"- {security.name}({security.symbol})：{conclusion} 建议：{suggestion}")

        if any(keyword in conclusion for keyword in ("偏多", "偏强", "持有为主", "允许轻仓试错")):
            bullish.append(f"{security.name}({security.symbol})")
        elif any(keyword in conclusion for keyword in ("偏空", "偏弱", "减仓", "兑现")):
            bearish.append(f"{security.name}({security.symbol})")
        else:
            neutral.append(f"{security.name}({security.symbol})")

    lines.extend(
        [
            "",
            "组合层结论：",
            f"- 偏强观察组：{'、'.join(bullish) if bullish else '无'}",
            f"- 震荡观察组：{'、'.join(neutral) if neutral else '无'}",
            f"- 风险控制组：{'、'.join(bearish) if bearish else '无'}",
            "- 操作原则：60M 只用于节奏和仓位管理，真正加减仓以中枢突破/跌破后的确认笔为准。",
            "- 说明：以上仅基于最新 60M 缠论结构与 MACD 强弱，不构成投资建议。",
        ]
    )
    return "\n".join(lines) + "\n"


def write_group_operation_summary(bundle: list[tuple[Security, dict[str, Path], dict[str, Path]]]) -> Path:
    output_path = ROOT / "data" / "_meta" / f"group888_60m_operation_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    output_path.write_text(build_group_operation_summary(bundle), encoding="utf-8")
    return output_path


def latest_file(directory: Path, pattern: str) -> Path:
    matches = list(directory.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"未找到文件: {directory / pattern}")
    return max(matches, key=lambda item: item.stat().st_mtime)


def load_existing_case(security: Security, timeframe: str) -> dict[str, Path]:
    base_dir = ROOT / "data" / f"{security.symbol}_{security.name}" / timeframe
    wechat_dir = derive_wechat_output_dir(base_dir / "placeholder.svg")
    return {
        "report": latest_file(base_dir, "*_normalized_report.txt"),
        "analysis": latest_file(base_dir, "*_normalized_analysis.txt"),
        "advice": latest_file(base_dir, "*_normalized_advice.txt"),
        "jpg": latest_file(wechat_dir, "*_normalized_wechat.jpg"),
        "png": latest_file(wechat_dir, "*_normalized_full.png"),
        "svg": latest_file(base_dir, "*_normalized_with_boxes.svg"),
    }


def send_batch_current_chat(
    bundle: list[tuple[Security, dict[str, Path], dict[str, Path]]],
    target_label: str,
    summary_path: Path,
) -> None:
    print(f"Sending consolidated 60M summary to current chat ({target_label})")
    send_message(
        contact=None,
        message=summary_path.read_text(encoding="utf-8"),
        current_chat_only=True,
        best_effort_current_chat_text=True,
    )

    for security, day_case, m60_case in bundle:
        message_text = build_send_text_60m_only(security, m60_case["report"])
        print(f"Sending {security.name} to current chat ({target_label})")
        send_message(
            contact=None,
            message=message_text,
            current_chat_only=True,
            best_effort_current_chat_text=True,
        )
        send_message(contact=None, message=None, filepaths=[str(m60_case["jpg"])], current_chat_only=True)


def main() -> None:
    args = parse_args()
    securities = load_securities(Path(args.holdings_file) if args.holdings_file else None)
    bundle: list[tuple[Security, dict[str, Path], dict[str, Path]]] = []
    summary_path: Path | None = None
    if args.send_only:
        for security in securities:
            day_case = load_existing_case(security, "day")
            m60_case = load_existing_case(security, "60m")
            bundle.append((security, day_case, m60_case))
            print(f"Loaded {security.name}")
    else:
        for security in securities:
            day_rows = fetch_day_rows(security, args.day_start)
            m60_rows = fetch_m60_rows(security, args.m60_start)

            security_dir = ROOT / "data" / f"{security.symbol}_{security.name}"
            day_dir = security_dir / "day"
            m60_dir = security_dir / "60m"
            day_dir.mkdir(parents=True, exist_ok=True)
            m60_dir.mkdir(parents=True, exist_ok=True)

            day_stem = f"{security.symbol}_daily_{day_rows[0]['ts'].replace('-', '')}_to_{day_rows[-1]['ts'].replace('-', '')}"
            m60_stem = (
                f"{security.symbol}_60m_{m60_rows[0]['ts'][0:10].replace('-', '')}_"
                f"to_{m60_rows[-1]['ts'][0:10].replace('-', '')}"
            )

            day_case = export_case(security, "day", day_rows, day_dir, day_stem, f"{security.symbol} {security.name} day")
            m60_case = export_case(security, "60m", m60_rows, m60_dir, m60_stem, f"{security.symbol} {security.name} 60m")
            bundle.append((security, day_case, m60_case))
            print(f"Prepared {security.name}")

        manifest = ROOT / "data" / "_meta" / f"group888_send_manifest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        lines = ["群聊 888 待发送清单", ""]
        for security, day_case, m60_case in bundle:
            lines.append(f"{security.name} ({security.symbol})")
            lines.append(f"- 60M 报告: {m60_case['report']}")
            lines.append(f"- 60M 图片: {m60_case['jpg']}")
            lines.append("")
        manifest.write_text("\n".join(lines), encoding="utf-8")
        print(f"Manifest: {manifest}")

    summary_path = write_group_operation_summary(bundle)
    print(f"Summary: {summary_path}")

    if args.send_current_chat:
        if summary_path is None:
            raise RuntimeError("missing summary path")
        send_batch_current_chat(bundle, args.target_label, summary_path)


if __name__ == "__main__":
    main()