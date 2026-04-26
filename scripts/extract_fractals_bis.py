"""提取全部顶底分型与笔，并导出 CSV。"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from chanlun.data import read_bars_from_csv
from chanlun.data.cleaner import clean_bars
from chanlun.normalize import normalize_bars
from chanlun.fractal import identify_fractals, filter_consecutive_fractals
from chanlun.bi import identify_bis


def _bar_context_row(norm_bars, index: int, prefix: str) -> dict:
    if index < 0 or index >= len(norm_bars):
        return {
            f"{prefix}_bar_idx": None,
            f"{prefix}_bar_ts_start": None,
            f"{prefix}_bar_ts_end": None,
            f"{prefix}_bar_high": None,
            f"{prefix}_bar_low": None,
        }

    bar = norm_bars[index]
    return {
        f"{prefix}_bar_idx": bar.idx,
        f"{prefix}_bar_ts_start": bar.ts_start,
        f"{prefix}_bar_ts_end": bar.ts_end,
        f"{prefix}_bar_high": bar.high,
        f"{prefix}_bar_low": bar.low,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="提取全部顶底分型和笔")
    parser.add_argument("--input", required=True, help="输入 K 线 CSV")
    parser.add_argument("--output-dir", default="data", help="输出目录")
    parser.add_argument("--prefix", default="result", help="输出文件名前缀")
    parser.add_argument("--confirmed-only", action="store_true", help="仅导出已确认笔")
    parser.add_argument("--start-ts", default=None, help="仅导出起点时间 >= 该值的笔，如 2025-10-09")
    parser.add_argument("--fractals-from-bis", action="store_true", help="分型仅保留来自导出笔端点的分型")
    args = parser.parse_args()

    bars = read_bars_from_csv(args.input)
    bars = clean_bars(bars)
    norm_bars = normalize_bars(bars)

    fractals = identify_fractals(norm_bars)
    fractals = filter_consecutive_fractals(fractals)
    bis = identify_bis(fractals, norm_bars)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    confirmed_fx_ids = set()
    for bi in bis:
        if bi.is_confirmed:
            confirmed_fx_ids.add(bi.start_fx_id)
            confirmed_fx_ids.add(bi.end_fx_id)

    unconfirmed_end_fx_ids = {bi.end_fx_id for bi in bis if not bi.is_confirmed}

    fractal_rows = []
    for fx in fractals:
        is_confirmed = fx.fx_id in confirmed_fx_ids
        note = "confirmed" if is_confirmed else "candidate"
        if fx.fx_id in unconfirmed_end_fx_ids:
            note = "pre_bi_candidate"

        center_idx = fx.center_bar_idx
        fractal_row = {
            "fx_id": fx.fx_id,
            "fx_type": fx.fx_type.value,
            "ts": fx.ts,
            "price": fx.price,
            "center_bar_idx": fx.center_bar_idx,
            "high": fx.high,
            "low": fx.low,
            "is_confirmed": is_confirmed,
            "note": note,
        }
        fractal_row.update(_bar_context_row(norm_bars, center_idx - 1, "left"))
        fractal_row.update(_bar_context_row(norm_bars, center_idx, "center"))
        fractal_row.update(_bar_context_row(norm_bars, center_idx + 1, "right"))

        fractal_rows.append(fractal_row)
    fractal_df = pd.DataFrame(fractal_rows)

    bi_rows = []
    for bi in bis:
        bi_rows.append(
            {
                "bi_id": bi.bi_id,
                "direction": bi.direction.value,
                "start_fx_id": bi.start_fx_id,
                "end_fx_id": bi.end_fx_id,
                "start_ts": bi.start_ts,
                "end_ts": bi.end_ts,
                "high": bi.high,
                "low": bi.low,
                "start_norm_idx": bi.norm_bar_range[0],
                "end_norm_idx": bi.norm_bar_range[1],
                "is_confirmed": bi.is_confirmed,
                "status": "confirmed" if bi.is_confirmed else "preprocessing",
                "note": "auto_generated",
            }
        )
    bi_df = pd.DataFrame(bi_rows)

    if args.start_ts:
        start_ts = pd.to_datetime(args.start_ts)
        bi_df["start_ts"] = pd.to_datetime(bi_df["start_ts"])
        bi_df = bi_df[bi_df["start_ts"] >= start_ts]

    if args.confirmed_only:
        bi_df = bi_df[bi_df["is_confirmed"] == True]

    if args.fractals_from_bis:
        fx_ids = set(bi_df["start_fx_id"].tolist() + bi_df["end_fx_id"].tolist())
        fractal_df = fractal_df[fractal_df["fx_id"].isin(fx_ids)]

    fractal_path = out_dir / f"{args.prefix}_fractals.csv"
    fractal_df.to_csv(fractal_path, index=False)

    # 额外导出：仅由“已确认笔”端点构成的确认分型
    confirmed_bi_df = pd.DataFrame(bi_rows)
    confirmed_bi_df = confirmed_bi_df[confirmed_bi_df["is_confirmed"] == True]
    confirmed_fractal_df = pd.DataFrame(fractal_rows)
    confirmed_fractal_df = confirmed_fractal_df[confirmed_fractal_df["fx_id"].isin(confirmed_fx_ids)]
    confirmed_fractal_path = out_dir / f"{args.prefix}_confirmed_fractals.csv"
    confirmed_fractal_df.to_csv(confirmed_fractal_path, index=False)

    bi_path = out_dir / f"{args.prefix}_bis.csv"
    bi_df.to_csv(bi_path, index=False)

    print(f"输入K线: {len(bars)} 根")
    print(f"标准化K线: {len(norm_bars)} 根")
    print(f"分型总数: {len(fractals)}")
    print(f"笔总数: {len(bis)}")
    print(f"导出笔数: {len(bi_df)}")
    print(f"导出分型数: {len(fractal_df)}")
    print(f"确认分型数: {len(confirmed_fractal_df)}")
    print(f"分型已保存: {fractal_path}")
    print(f"确认分型已保存: {confirmed_fractal_path}")
    print(f"笔已保存: {bi_path}")


if __name__ == "__main__":
    main()
