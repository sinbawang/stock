"""真实窗口回归的冻结 fixture 解析（`tests/fixtures/real/`）。

**为什么需要冻结**：`src/report_retention.py::prune_analyze_csv_families` 会保留每个
symbol/timeframe 的「当前 CSV family」并删除旧 family，因此任何钉住 `data/reports/**` 具体
文件名（如 `*_to_20260904.csv`）的 real-window 回归都会在下一次刷新后集体失效。冻结快照
由 `build/freeze_real_fixtures.py` 生成并随仓库提交，使这些回归与本地数据刷新解耦。

刷新冻结快照（仅在**有意**更新回归基线时执行）：

    python scripts/freeze_real_fixtures.py
    # 然后按需重跑并更新断言中的具体数值
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_ROOT = ROOT / "tests" / "fixtures" / "real"

_FREEZE_HINT = "运行 `python scripts/freeze_real_fixtures.py` 重新冻结 tests/fixtures/real。"

# 案例卡 / 回放的标准 cutoff 口径（与 build/ 探针一致）。
CASE_FRAMES = 12
CASE_MIN_BARS = 60


def analysis_cutoffs(total: int, *, frames: int = CASE_FRAMES, min_bars: int = CASE_MIN_BARS) -> list[int]:
    """冻结窗口上的标准回放 cutoff 序列。

    案例库卡片与自动化锚点必须共用本函数：否则「文档里的样例」与「测试里的锚点」
    会各自挑不同 cutoff，改规则时容易只在一边失效。
    """
    start = min(min_bars, max(20, total // 3))
    if total - start < 5:
        return []
    step = max(1, (total - start) // frames)
    cutoffs = list(range(start, total + 1, step))
    if cutoffs[-1] != total:
        cutoffs.append(total)
    return cutoffs


def frozen_csv(symbol: str, timeframe: str) -> Path:
    """`<symbol>_<timeframe>` 的冻结原始 K 线 CSV（排除 `_normalized` 伴生文件）。"""
    candidates = sorted(
        path for path in FIXTURES_ROOT.glob(f"{symbol}_{timeframe}_*.csv") if "_normalized" not in path.name
    )
    if not candidates:
        raise FileNotFoundError(f"缺少冻结 fixture：{symbol} {timeframe}。{_FREEZE_HINT}")
    return candidates[-1]


def frozen_segments_csv(symbol: str, timeframe: str) -> Path:
    """`<symbol>_<timeframe>` 的冻结 `_normalized_segments.csv`（供直接读取线段表的用例）。

    注意：线段表来自 pipeline 的 analyze 产物，其窗口与 K 线 fixture 可能不同，因此这里独立 glob。
    """
    candidates = sorted(FIXTURES_ROOT.glob(f"{symbol}_{timeframe}_*_normalized_segments.csv"))
    if not candidates:
        raise FileNotFoundError(f"缺少冻结线段 fixture：{symbol} {timeframe}。{_FREEZE_HINT}")
    return candidates[-1]


def frozen_tech_json(symbol: str, timeframe: str) -> Path:
    """`<symbol>_<timeframe>` 的冻结 `tech.json` 产物（消费层样本测试的输入锚点）。"""
    path = FIXTURES_ROOT / "tech" / f"{symbol}_{timeframe}_tech.json"
    if not path.exists():
        raise FileNotFoundError(f"缺少冻结 tech.json fixture：{symbol} {timeframe}。{_FREEZE_HINT}")
    return path


def halt_fixture_csv(symbol: str, timeframe: str) -> Path:
    """`segment_practical_halt/` 下的加宽窗口 fixture。

    这些窗口来自本地 K 线仓库的全量历史，**故意比 pipeline 当前 analyze 窗口更宽**，
    用于复现「practical 模式中段 pending 导致段链提前终止、丢弃其后全部笔」的缺陷
    （见 `tests/test_segment.py::test_practical_recovers_past_pending_segment_to_later_confirmed_anchor`）。
    不要把它们当作常规真实窗口回归锚点。
    """
    candidates = sorted((FIXTURES_ROOT / "segment_practical_halt").glob(f"{symbol}_{timeframe}_*.csv"))
    if not candidates:
        raise FileNotFoundError(f"缺少 practical 停扫 fixture：{symbol} {timeframe}。{_FREEZE_HINT}")
    return candidates[-1]


REPLAY_FIXTURES_ROOT = FIXTURES_ROOT / "replay"


def replay_fixture_csv(symbol: str, timeframe: str) -> Path:
    """`replay/` 下的早期 1m 窗口 fixture（消费层 replay 样本的输入）。

    这些窗口（2026-07-30 ~ 2026-08-11）**故意与 `frozen_csv` 的当前 analyze 窗口错开**：
    它们只存在于 `data/stock-kline-cache/`，若不单独冻结，消费层样本测试就只能去读未入
    版本库的 `data/`，无法在干净机器上复现。

    单独放在子目录而不是 FIXTURES_ROOT 根下，是为了不干扰 `frozen_csv` 的
    `<symbol>_<timeframe>_*.csv` glob（同一 (symbol, timeframe) 出现两个窗口会让既有闸门静默切换窗口）。
    """
    candidates = sorted(REPLAY_FIXTURES_ROOT.glob(f"{symbol}_{timeframe}_*.csv"))
    if not candidates:
        raise FileNotFoundError(
            f"缺少 replay 窗口 fixture：{symbol} {timeframe}。{_FREEZE_HINT}"
            "（可用 `python scripts/freeze_real_fixtures.py --only replay` 只重建该组）"
        )
    return candidates[-1]


PRECISION_FIXTURES_ROOT = FIXTURES_ROOT / "precision"


def precision_fixture_csv(symbol: str, timeframe: str) -> Path:
    """`precision/` 下的区间套高位档 fixture。

    只有 `actionable` 样本需要这一组：该状态要求「上级别消费等级 = confirmed」与「次级别有落在
    窗口内的同向点」同时成立，而已冻结的 5 个多级别标的在 2812 帧上一次都不出现（属语料覆盖
    不足，不是功能缺口）。样本来自 `data/cache/kline`，因此单独分组、单独重建：

        python scripts/freeze_real_fixtures.py --only precision

    同样放在独立子目录，避免与 `frozen_csv` / `replay_fixture_csv` 的 glob 相撞。
    """
    candidates = sorted(PRECISION_FIXTURES_ROOT.glob(f"{symbol}_{timeframe}_*.csv"))
    if not candidates:
        raise FileNotFoundError(
            f"缺少 precision fixture：{symbol} {timeframe}。{_FREEZE_HINT}"
            "（可用 `python scripts/freeze_real_fixtures.py --only precision` 只重建该组）"
        )
    return candidates[-1]
