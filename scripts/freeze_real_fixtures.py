"""把 tests 依赖的真实窗口 K 线冻结到 tests/fixtures/real/。

背景：`src/report_retention.py::prune_analyze_csv_families` 只保留每个 symbol/timeframe 的
当前 CSV family，旧的 `*_to_YYYYMMDD.csv` 会被删除；任何钉住 `data/reports/**` 具体文件名的
real-window 回归都会在下一次刷新后集体失败。

冻结策略：
- **K 线**：从本地仓库 `data/cache/kline`（按 retention 保留尾部 N 根，不做 family 裁剪）
  取到固定 cutoff 为止的**全部可用历史**，写成 `tests/fixtures/real/<sym>_<tf>_<start>_to_<end>.csv`。
  用全量历史而不是 pipeline 当前的 analyze 窗口，是为了保住多中枢 / completed→ongoing
  这类结构 gate 的覆盖度（当前 analyze 窗口起点更晚，会丢中枢）。
- **线段表**：`_normalized_segments.csv` 仍从 `data/reports` 复制（pipeline 产物，无法从 K 线重建）。

用法：
    .venv/Scripts/python.exe scripts/freeze_real_fixtures.py
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from chanlun.data.local_bar_store import load_local_rows  # noqa: E402

REPORTS_ROOT = ROOT / "data" / "reports"
FIXTURES_ROOT = ROOT / "tests" / "fixtures" / "real"

# 冻结快照的时间上界（与 2026-09-11 那次数据刷新对齐）。
CUTOFF = "2026-09-11"

# symbol -> 本地 K 线仓库的市场目录名
MARKETS = {
    "000591": "A",
    "000651": "A",
    "300124": "A",
    "600900": "A",
    "00700": "HK",
    "00728": "HK",
    "01024": "HK",
    "03690": "HK",
    "09988": "HK",
}

# 需要冻结 K 线窗口的 (symbol, timeframe)
RAW_FIXTURES: tuple[tuple[str, str], ...] = (
    ("000591", "day"),
    ("000591", "1m"),
    ("000591", "5m"),
    ("000651", "1m"),
    ("00700", "day"),
    ("00700", "1m"),
    ("00700", "5m"),
    ("00700", "30m"),
    ("00728", "day"),
    ("01024", "1m"),
    ("03690", "day"),
    ("03690", "1m"),
    ("03690", "5m"),
    ("03690", "30m"),
    ("300124", "day"),
    ("300124", "1m"),
    ("300124", "5m"),
    ("300124", "30m"),
    ("600900", "1m"),
    ("600900", "5m"),
    ("09988", "1m"),
)

# 需要冻结 `_normalized_segments.csv` 的 (symbol, timeframe)
SEGMENT_FIXTURES: tuple[tuple[str, str], ...] = (
    ("03690", "5m"),
    ("300124", "30m"),
)

# 需要冻结 `tech.json` 产物的 (symbol, timeframe)——消费层样本测试的输入锚点
TECH_FIXTURES: tuple[tuple[str, str], ...] = (
    ("01024", "1m"),
    ("002555", "1m"),
    ("600900", "1m"),
    ("00700", "5m"),
)

TECH_FIXTURES_ROOT = FIXTURES_ROOT / "tech"

# 「practical 停扫」缺陷的回归锚点：必须用**加宽**窗口才能触发，因此单独冻结。
# 300124 30m 1400 根（116 笔）时 practical 曾只产出 2 段（bi 18..114 被丢弃）；
# 收窄到 pipeline 当前的 1200 根则不复现。见 tests/real_fixture_support.py::halt_fixture_csv。
HALT_FIXTURES: tuple[tuple[str, str, str], ...] = (
    # (symbol, timeframe, market)
    ("300124", "30m", "A"),
)
HALT_FIXTURES_ROOT = FIXTURES_ROOT / "segment_practical_halt"

# 消费层 replay 样本用的「早期 1m 窗口」。
#
# 背景：`tests/test_build_miniapp_publish_bundle.py` 的 10 个 sample 要回放到
# 2026-07-30 ~ 2026-08-11 之间的 cutoff，而 `data/reports/**/analyze` 的当前窗口起点已到
# 2026-08-24/28，`data/cache/kline` 也只保留最近 4500 根 1m。这些早期窗口只存在于
# `data/stock-kline-cache/<mkt>/<sym>/<tf>.csv`，因此必须单独冻结，否则测试会退回去
# 读未入版本库的 `data/`（见 tests/real_fixture_support.py 说明）。
#
# 消费方（全部四个模块都靠这些窗口，不能只覆盖其中一个）：
# - `tests/test_build_miniapp_publish_bundle.py`
# - `tests/test_chanlun_analysis.py`
# - `tests/test_zhongshu_structure_text.py`
# - `tests/replay_support.py`（由上述模块共享）
#
# 注意：本组 fixture 放在 `replay/` 子目录，**不能**放在 FIXTURES_ROOT 根下：
# `frozen_csv(symbol, timeframe)` 用 `<sym>_<tf>_*.csv` glob 并取排序最后一项，
# 同一 (symbol, timeframe) 出现两个窗口会让既有闸门静默切到另一个窗口。
REPLAY_FIXTURES: tuple[tuple[str, str, str], ...] = (
    # (symbol, timeframe, market)
    ("000591", "day", "A"),
    ("000651", "1m", "A"),
    ("00175", "1m", "HK"),
    ("002555", "1m", "A"),
    ("00700", "1m", "HK"),
    ("01024", "1m", "HK"),
    ("03690", "1m", "HK"),
    ("09988", "1m", "HK"),
    ("300124", "1m", "A"),
    ("600900", "1m", "A"),
    ("601328", "day", "A"),
)
REPLAY_FIXTURES_ROOT = FIXTURES_ROOT / "replay"

# 早期 1m 窗口所在的本地仓库（与 KLINE_CACHE_DIR 不同：后者只保留尾部 4500 根）。
STOCK_KLINE_CACHE_ROOT = ROOT / "data" / "stock-kline-cache"

_FIELDS = ["ts", "open", "high", "low", "close", "volume"]


def _latest_raw_csv(symbol: str, timeframe: str) -> Path | None:
    analyze_dir = REPORTS_ROOT / symbol / timeframe / "analyze"
    if not analyze_dir.is_dir():
        return None
    candidates = sorted(
        path for path in analyze_dir.glob(f"{symbol}_{timeframe}_*.csv") if "_normalized" not in path.name
    )
    return candidates[-1] if candidates else None


def _write_bars_fixture(symbol: str, timeframe: str) -> Path | None:
    """复制 pipeline 当前的 analyze 窗口。

    注意：**不要**改用本地 K 线仓库的全量历史来「加宽」窗口。实测 `300124 30m` 加宽到
    1400 根（116 个笔）时 `identify_segments` 只产出 2 段（段链在第一个 pending 段处停扫，
    bi 18..115 被丢弃），会把退化结构固化进 gate。详见 tests/real_fixture_support.py 说明。
    """
    source = _latest_raw_csv(symbol, timeframe)
    if source is None:
        return None
    target = FIXTURES_ROOT / source.name
    shutil.copyfile(source, target)
    return target


def _latest_segments_csv(symbol: str, timeframe: str) -> Path | None:
    analyze_dir = REPORTS_ROOT / symbol / timeframe / "analyze"
    if not analyze_dir.is_dir():
        return None
    candidates = sorted(analyze_dir.glob(f"{symbol}_{timeframe}_*_normalized_segments.csv"))
    return candidates[-1] if candidates else None


def _write_replay_fixtures() -> None:
    """冻结消费层 replay 用的早期 1m 窗口（幂等，不影响其它 fixture）。"""
    REPLAY_FIXTURES_ROOT.mkdir(parents=True, exist_ok=True)
    for stale in REPLAY_FIXTURES_ROOT.glob("*.csv"):
        stale.unlink()
    for symbol, timeframe, market in REPLAY_FIXTURES:
        rows = load_local_rows(symbol, market, timeframe, root=STOCK_KLINE_CACHE_ROOT)
        window = [row for row in rows if str(row["ts"])[:10] <= CUTOFF]
        if not window:
            print(f"[replay] {symbol} {timeframe}: NO STORE DATA")
            continue
        start = str(window[0]["ts"])[:10].replace("-", "")
        end = str(window[-1]["ts"])[:10].replace("-", "")
        target = REPLAY_FIXTURES_ROOT / f"{symbol}_{timeframe}_{start}_to_{end}.csv"
        with target.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=_FIELDS)
            writer.writeheader()
            for row in window:
                writer.writerow({field: row[field] for field in _FIELDS})
        print(f"[replay] {symbol} {timeframe}: {target.name} ({len(window)} bars)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只校验冻结 fixture 是否齐全，不重建")
    parser.add_argument(
        "--only",
        choices=("replay",),
        default=None,
        help=(
            "只重建指定分组。注意：无 --only 的完整重建会先清空 FIXTURES_ROOT 根下的全部 CSV "
            "并按当前 data/ 重算，可能改变已提交窗口；只补 replay 窗口时请用 --only replay。"
        ),
    )
    args = parser.parse_args()

    if args.only == "replay":
        FIXTURES_ROOT.mkdir(parents=True, exist_ok=True)
        _write_replay_fixtures()
        return 0

    FIXTURES_ROOT.mkdir(parents=True, exist_ok=True)

    if args.check:
        missing: list[str] = []
        for symbol, timeframe in RAW_FIXTURES:
            if not any(
                path for path in FIXTURES_ROOT.glob(f"{symbol}_{timeframe}_*.csv")
                if "_normalized" not in path.name
            ):
                missing.append(f"{symbol} {timeframe} (bars)")
        for symbol, timeframe in SEGMENT_FIXTURES:
            if not any(FIXTURES_ROOT.glob(f"{symbol}_{timeframe}_*_normalized_segments.csv")):
                missing.append(f"{symbol} {timeframe} (segments)")
        for item in missing:
            print(f"[MISSING] {item}")
        print("ok" if not missing else f"{len(missing)} missing")
        return 1 if missing else 0

    # 清空重建，避免旧窗口文件与新窗口文件同时命中 glob。
    for stale in FIXTURES_ROOT.glob("*.csv"):
        stale.unlink()

    for symbol, timeframe in RAW_FIXTURES:
        target = _write_bars_fixture(symbol, timeframe)
        print(f"[bars] {symbol} {timeframe}: {target.name if target else 'NO STORE DATA'}")

    for symbol, timeframe in SEGMENT_FIXTURES:
        source = _latest_segments_csv(symbol, timeframe)
        if source is None:
            print(f"[segments] {symbol} {timeframe}: NO SOURCE")
            continue
        shutil.copyfile(source, FIXTURES_ROOT / source.name)
        print(f"[segments] {symbol} {timeframe}: {source.name}")

    TECH_FIXTURES_ROOT.mkdir(parents=True, exist_ok=True)
    for stale in TECH_FIXTURES_ROOT.glob("*.json"):
        stale.unlink()
    for symbol, timeframe in TECH_FIXTURES:
        source = REPORTS_ROOT / symbol / timeframe / "tech.json"
        if not source.exists():
            print(f"[tech] {symbol} {timeframe}: NO SOURCE")
            continue
        target = TECH_FIXTURES_ROOT / f"{symbol}_{timeframe}_tech.json"
        shutil.copyfile(source, target)
        print(f"[tech] {symbol} {timeframe}: {target.name}")

    HALT_FIXTURES_ROOT.mkdir(parents=True, exist_ok=True)
    for stale in HALT_FIXTURES_ROOT.glob("*.csv"):
        stale.unlink()
    for symbol, timeframe, market in HALT_FIXTURES:
        rows = load_local_rows(symbol, market, timeframe)
        window = [row for row in rows if str(row["ts"])[:10] <= CUTOFF]
        if not window:
            print(f"[halt] {symbol} {timeframe}: NO STORE DATA")
            continue
        start = str(window[0]["ts"])[:10].replace("-", "")
        end = str(window[-1]["ts"])[:10].replace("-", "")
        target = HALT_FIXTURES_ROOT / f"{symbol}_{timeframe}_{start}_to_{end}.csv"
        with target.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=_FIELDS)
            writer.writeheader()
            for row in window:
                writer.writerow({field: row[field] for field in _FIELDS})
        print(f"[halt] {symbol} {timeframe}: {target.name} ({len(window)} bars)")

    _write_replay_fixtures()

    total = sum(path.stat().st_size for path in FIXTURES_ROOT.rglob("*.csv"))
    total += sum(path.stat().st_size for path in FIXTURES_ROOT.rglob("*.json"))
    print(f"\nfixtures dir: {total / 1024:.0f} KiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
