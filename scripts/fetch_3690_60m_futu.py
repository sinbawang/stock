"""使用富途 OpenAPI 获取美团 HK.03690 60 分钟 K 线并可视化。"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import pandas as pd
from futu import (
    AuType,
    KLType,
    OpenQuoteContext,
    RET_OK,
)

from plot_kline import plot_kline


def fetch_history_60m(
    code: str,
    start: str,
    end: str,
    host: str = "127.0.0.1",
    port: int = 11111,
    autype: AuType = AuType.QFQ,
) -> pd.DataFrame:
    """从富途 OpenD 拉取历史 60 分钟 K 线，自动翻页。"""
    quote_ctx = OpenQuoteContext(host=host, port=port)
    try:
        all_rows = []
        page_req_key = None

        while True:
            ret, data, page_req_key = quote_ctx.request_history_kline(
                code=code,
                start=start,
                end=end,
                ktype=KLType.K_60M,
                autype=autype,
                max_count=1000,
                page_req_key=page_req_key,
            )
            if ret != RET_OK:
                raise RuntimeError(f"request_history_kline 失败: {data}")

            if data is not None and not data.empty:
                all_rows.append(data)

            if page_req_key is None:
                break

        if not all_rows:
            raise RuntimeError("未获取到任何 K 线，请检查代码、日期区间或行情权限")

        out = pd.concat(all_rows, ignore_index=True)
        out = out.drop_duplicates(subset=["time_key"]).sort_values("time_key").reset_index(drop=True)
        return out
    finally:
        quote_ctx.close()


def save_standard_csv(df: pd.DataFrame, output_csv: str) -> None:
    """保存为项目统一列格式: ts/open/high/low/close/volume。"""
    out = pd.DataFrame(
        {
            "ts": pd.to_datetime(df["time_key"]),
            "open": pd.to_numeric(df["open"], errors="coerce"),
            "high": pd.to_numeric(df["high"], errors="coerce"),
            "low": pd.to_numeric(df["low"], errors="coerce"),
            "close": pd.to_numeric(df["close"], errors="coerce"),
            "volume": pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype("int64"),
        }
    )

    out = out.dropna(subset=["ts", "open", "high", "low", "close"])
    out = out.sort_values("ts").drop_duplicates(subset=["ts"], keep="last")

    path = Path(output_csv)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="富途 OpenAPI 获取 03690 60m 历史 K 线")
    parser.add_argument("--code", default="HK.03690", help="证券代码，默认 HK.03690")
    parser.add_argument("--start", default="2026-01-05", help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end", default="2026-04-25", help="结束日期 YYYY-MM-DD")
    parser.add_argument("--host", default="127.0.0.1", help="OpenD 主机")
    parser.add_argument("--port", default=11111, type=int, help="OpenD 端口")
    parser.add_argument("--output-csv", default="data/03690_美团/60m/3690_60m_futu.csv", help="输出 CSV")
    parser.add_argument("--output-png", default="data/03690_美团/60m/3690_60m_futu.png", help="输出图像")
    args = parser.parse_args()

    print(f"正在通过富途 OpenAPI 获取 {args.code} 60m: {args.start} ~ {args.end}")
    try:
        df = fetch_history_60m(args.code, args.start, args.end, host=args.host, port=args.port)
        print(f"获取成功: {len(df)} 根")

        save_standard_csv(df, args.output_csv)
        print(f"CSV 已保存: {args.output_csv}")

        title = f"{args.code} 60m Kline ({args.start} ~ {args.end})"
        plot_kline(args.output_csv, args.output_png, title)
        print(f"图像已生成: {args.output_png}")
    except Exception as e:
        msg = str(e)
        print("\n获取失败。")
        print(f"原因: {msg}")
        print("\n请先确认:")
        print("1) 已安装并启动 FutuOpenD 桌面程序")
        print("2) FutuOpenD 已登录 moomoo/富途账号")
        print("3) FutuOpenD 监听端口与脚本参数一致 (默认 11111)")
        print("4) 当前机器防火墙未拦截本地 11111 端口")
        print("5) 若需美团 2026-01-05 以来 60m 图，直接运行脚本默认参数即可")


if __name__ == "__main__":
    main()
