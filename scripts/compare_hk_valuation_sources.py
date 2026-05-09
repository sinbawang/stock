from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fundamental.data.hk_snapshot_fetcher import (  # noqa: E402
    _coerce_float,
    _fetch_hk_quote_xueqiu,
    _fetch_hk_valuation_comparison_df,
    _normalize_hk_symbol,
)


def _build_rows(symbol: str) -> list[dict[str, object]]:
    code = _normalize_hk_symbol(symbol)
    valuation_df = _fetch_hk_valuation_comparison_df(code)
    if valuation_df.empty:
        raise RuntimeError(f"未取到港股 {code} 的 Eastmoney/AkShare 估值对比数据")

    valuation_row = valuation_df.iloc[0]
    xueqiu_quote = _fetch_hk_quote_xueqiu(code)
    rows = [
        {
            "field": "pe_ttm",
            "eastmoney": _coerce_float(valuation_row.iloc[2]),
            "xueqiu": _coerce_float(xueqiu_quote.get("pe_ttm")),
            "eastmoney_label": "Eastmoney valuation comparison",
            "xueqiu_label": "Xueqiu quote",
        },
        {
            "field": "pb",
            "eastmoney": _coerce_float(valuation_row.iloc[6]),
            "xueqiu": _coerce_float(xueqiu_quote.get("pb")),
            "eastmoney_label": "Eastmoney valuation comparison",
            "xueqiu_label": "Xueqiu quote",
        },
        {
            "field": "ps_ttm",
            "eastmoney": _coerce_float(valuation_row.iloc[10]),
            "xueqiu": _coerce_float(xueqiu_quote.get("psr")),
            "eastmoney_label": "Eastmoney valuation comparison",
            "xueqiu_label": "Xueqiu quote psr",
        },
        {
            "field": "market_cap",
            "eastmoney": None,
            "xueqiu": _coerce_float(xueqiu_quote.get("market_capital")),
            "eastmoney_label": "not available in current snapshot builder",
            "xueqiu_label": "Xueqiu quote",
        },
        {
            "field": "dividend_yield",
            "eastmoney": None,
            "xueqiu": _coerce_float(xueqiu_quote.get("dividend_yield")),
            "eastmoney_label": "not available in current snapshot builder",
            "xueqiu_label": "Xueqiu quote",
        },
    ]
    return rows


def _build_comparison(symbol: str, name: Optional[str] = None) -> dict[str, object]:
    code = _normalize_hk_symbol(symbol)
    return {
        "symbol": code,
        "name": name or code,
        "rows": _build_rows(code),
    }


def _format_number(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    if abs(value) >= 1_000_000:
        return f"{value:,.2f}"
    return f"{value:.4f}"


def _format_delta(eastmoney: Optional[float], xueqiu: Optional[float]) -> str:
    if eastmoney is None or xueqiu is None:
        return "N/A"
    return f"{xueqiu - eastmoney:+.4f}"


def _build_summary(rows: list[dict[str, object]]) -> list[str]:
    summary: list[str] = []
    comparable = [row for row in rows if row["eastmoney"] is not None and row["xueqiu"] is not None]
    for row in comparable:
        eastmoney = row["eastmoney"]
        xueqiu = row["xueqiu"]
        assert isinstance(eastmoney, float)
        assert isinstance(xueqiu, float)
        delta = abs(xueqiu - eastmoney)
        if row["field"] == "pe_ttm":
            summary.append(
                f"`pe_ttm` 双源都可用，当前差值 {delta:.4f}，可作为稳定性交叉校验字段。"
            )
        elif row["field"] == "pb":
            summary.append(
                f"`pb` 双源都可用，当前差值 {delta:.4f}，数值接近时可继续以 Eastmoney 为主、雪球做旁路校验。"
            )
        elif row["field"] == "ps_ttm":
            summary.append(
                f"`ps_ttm` 与雪球 `psr` 当前差值 {delta:.4f}，字段口径看起来可比，但仍应标注来源避免混淆。"
            )

    xueqiu_only = [row["field"] for row in rows if row["eastmoney"] is None and row["xueqiu"] is not None]
    if xueqiu_only:
        summary.append(
            "雪球当前还能直接补这些字段: " + ", ".join(f"`{field}`" for field in xueqiu_only) + ", 适合作为 overlay 而不是主财务源。"
        )
    return summary


def _field_value(rows: list[dict[str, object]], field_name: str, source: str) -> Optional[float]:
    for row in rows:
        if row["field"] == field_name:
            value = row[source]
            return value if isinstance(value, float) else None
    return None


def build_batch_report(symbol_names: list[tuple[str, Optional[str]]]) -> str:
    comparisons = [_build_comparison(symbol, name) for symbol, name in symbol_names]
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# 港股估值字段双源批量对照",
        "",
        f"生成时间: {generated_at}",
        "",
        "## 汇总表",
        "",
        "| symbol | name | pe_ttm delta | pb delta | ps_ttm delta | xueqiu market_cap | xueqiu dividend_yield |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]

    for item in comparisons:
        rows = item["rows"]
        assert isinstance(rows, list)
        lines.append(
            "| {symbol} | {name} | {pe_delta} | {pb_delta} | {ps_delta} | {market_cap} | {dividend_yield} |".format(
                symbol=item["symbol"],
                name=item["name"],
                pe_delta=_format_delta(_field_value(rows, "pe_ttm", "eastmoney"), _field_value(rows, "pe_ttm", "xueqiu")),
                pb_delta=_format_delta(_field_value(rows, "pb", "eastmoney"), _field_value(rows, "pb", "xueqiu")),
                ps_delta=_format_delta(_field_value(rows, "ps_ttm", "eastmoney"), _field_value(rows, "ps_ttm", "xueqiu")),
                market_cap=_format_number(_field_value(rows, "market_cap", "xueqiu")),
                dividend_yield=_format_number(_field_value(rows, "dividend_yield", "xueqiu")),
            )
        )

    lines.extend([
        "",
        "## 逐标的结论",
        "",
    ])
    for item in comparisons:
        rows = item["rows"]
        assert isinstance(rows, list)
        lines.append(f"### {item['name']} ({item['symbol']})")
        lines.append("")
        for summary_line in _build_summary(rows):
            lines.append(f"- {summary_line}")
        lines.append("")

    lines.extend([
        "## 批量建议",
        "",
        "- 如果大部分标的的 `pe_ttm`、`pb`、`ps_ttm` 差值都保持在小范围内，可以继续把 Eastmoney/AkShare 作为主源，雪球作为估值交叉校验。",
        "- 如果某只标的出现单字段异常跳变，优先把它视为 source drift 候选，而不是立即切换整条主源策略。",
        "- 雪球更适合补 `market_cap`、`dividend_yield` 这类当前主源未稳定落盘的字段。",
    ])
    return "\n".join(lines) + "\n"


def build_report(symbol: str, name: Optional[str] = None) -> str:
    code = _normalize_hk_symbol(symbol)
    display_name = name or code
    rows = _build_rows(code)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"# 港股估值字段双源对照: {display_name} ({code})",
        "",
        f"生成时间: {generated_at}",
        "",
        "## 对照表",
        "",
        "| field | Eastmoney/AkShare | Xueqiu | delta(xueqiu-eastmoney) | 备注 |",
        "| --- | ---: | ---: | ---: | --- |",
    ]

    for row in rows:
        lines.append(
            "| {field} | {eastmoney} | {xueqiu} | {delta} | {remark} |".format(
                field=row["field"],
                eastmoney=_format_number(row["eastmoney"]),
                xueqiu=_format_number(row["xueqiu"]),
                delta=_format_delta(row["eastmoney"], row["xueqiu"]),
                remark=f"{row['eastmoney_label']} vs {row['xueqiu_label']}",
            )
        )

    lines.extend([
        "",
        "## 结论",
        "",
    ])
    for item in _build_summary(rows):
        lines.append(f"- {item}")

    lines.extend([
        "",
        "## 建议",
        "",
        "- 财务表和多期指标继续以 Eastmoney/AkShare 为主源。",
        "- `pe_ttm`、`pb`、`ps_ttm` 可以保留双源对照能力，用于识别异常跳变或口径漂移。",
        "- `market_cap`、`dividend_yield` 这类当前主源未落到标准快照的字段，优先由雪球 overlay 补齐。",
    ])
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="对比港股估值字段的 Eastmoney/AkShare 与 Xueqiu 数据")
    parser.add_argument("symbol", nargs="?", default=None, help="港股代码，例如 03690")
    parser.add_argument("--name", default=None, help="证券名称，仅用于报告显示")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=None,
        help="批量港股代码，例如 03690 00700 00981",
    )
    parser.add_argument(
        "--symbol-file",
        default=None,
        help="批量输入文件，每行一个代码，或 `代码,名称`",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="输出 markdown 文件；为空则打印到 stdout",
    )
    return parser.parse_args()


def _load_symbol_names(args: argparse.Namespace) -> list[tuple[str, Optional[str]]]:
    symbol_names: list[tuple[str, Optional[str]]] = []
    if args.symbol:
        symbol_names.append((args.symbol, args.name))
    if args.symbols:
        symbol_names.extend((symbol, None) for symbol in args.symbols)
    if args.symbol_file:
        for line in Path(args.symbol_file).read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            if "," in text:
                symbol, name = text.split(",", 1)
                symbol_names.append((symbol.strip(), name.strip() or None))
            else:
                symbol_names.append((text, None))
    if not symbol_names:
        raise ValueError("请提供 symbol、--symbols 或 --symbol-file")
    return symbol_names


def main() -> None:
    args = parse_args()
    symbol_names = _load_symbol_names(args)
    if len(symbol_names) == 1:
        symbol, name = symbol_names[0]
        report = build_report(symbol, name)
    else:
        report = build_batch_report(symbol_names)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"已写入 {output_path}")
        return
    print(report)


if __name__ == "__main__":
    main()