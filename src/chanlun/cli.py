"""
命令行入口。
"""

import typer
from pathlib import Path
from typing import Optional
from .models import Bar
from .normalize import normalize_bars
from .fractal import identify_fractals, filter_consecutive_fractals
from .bi import identify_bis
from .zhongshu import identify_zhongshu
from .data import read_bars_from_csv
from .data.cleaner import clean_bars
from .visualization import Plotter

app = typer.Typer()


@app.command()
def analyze(
    filepath: str = typer.Argument(..., help="CSV 文件路径"),
    output_dir: Optional[str] = typer.Option(None, help="输出目录")
):
    """
    完整分析流程：读取 -> 清洗 -> 去包含 -> 识别分型/笔/中枢 -> 输出结果
    """
    typer.echo(f"读取 {filepath}...")
    
    try:
        bars = read_bars_from_csv(filepath)
        typer.echo(f"读取 {len(bars)} 根 K 线")
    except Exception as e:
        typer.echo(f"读取失败: {e}", err=True)
        return

    # 清洗
    typer.echo("清洗数据...")
    bars = clean_bars(bars)
    typer.echo(f"清洗后 {len(bars)} 根 K 线")

    # 去包含
    typer.echo("去包含处理...")
    normalized_bars = normalize_bars(bars)
    typer.echo(f"标准化后 {len(normalized_bars)} 根 K 线")

    # 分型识别
    typer.echo("识别分型...")
    fractals = identify_fractals(normalized_bars)
    typer.echo(f"识别 {len(fractals)} 个分型候选")

    # 分型去重
    fractals = filter_consecutive_fractals(fractals)
    typer.echo(f"去重后 {len(fractals)} 个分型")

    # 笔识别
    typer.echo("识别笔...")
    bis = identify_bis(fractals, normalized_bars)
    typer.echo(f"识别 {len(bis)} 笔")

    # 中枢识别
    typer.echo("识别中枢...")
    zhongshus = identify_zhongshu(bis)
    typer.echo(f"识别 {len(zhongshus)} 个中枢")

    # 输出结果摘要
    typer.echo("\n=== 分析结果 ===")
    typer.echo(f"分型: {len(fractals)}")
    for fx in fractals:
        typer.echo(f"  {fx.fx_type.value} @ {fx.ts} 价格={fx.price}")

    typer.echo(f"\n笔: {len(bis)}")
    for bi in bis:
        typer.echo(f"  {bi.direction.value} #{bi.bi_id} {bi.start_ts} ~ {bi.end_ts}")

    typer.echo(f"\n中枢: {len(zhongshus)}")
    for zs in zhongshus:
        typer.echo(f"  #{zs.zs_id} [{zs.zs_low:.2f}, {zs.zs_high:.2f}] {zs.start_ts} ~ {zs.end_ts}")

    # 可视化
    if output_dir:
        typer.echo(f"\n生成可视化到 {output_dir}...")
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        plotter = Plotter()

        # 绘制分型
        fig = plotter.plot_klines_with_fractals(bars, fractals)
        fig.savefig(output_path / "fractals.png", dpi=100)
        typer.echo("已保存 fractals.png")

        # 绘制笔
        fig = plotter.plot_bis(bars, bis)
        fig.savefig(output_path / "bis.png", dpi=100)
        typer.echo("已保存 bis.png")


def main():
    """CLI 主入口"""
    app()


if __name__ == "__main__":
    main()
