"""港股分钟线幽灵价闸门（首根 / 尾根 / 盘中）。

背景（2026-09 排查结论）
------------------------
雪球港股分钟 feed 会把"陈旧价"写进时段边界 bar：

1. **首根**：open 常被写成上一交易日收盘价（或更早陈旧价，实测 268/411 精确命中前收），
   例如 03690 2026-09-11 首根 open=84.628（≈18 天前的 84.629）；high/low 常随幽灵价越界。
2. **尾根(16:00)**：close 与日线收盘严格相等（实测 3622/3622），但 high/low 偶发越界
   （如 00175 2026-09-04 尾根 low=16.45 vs 日线 low=17.26）。
3. **盘中**：极少（多为 ±几分钱），个别大案如 09988 2026-07-23 11:10 high=118.062。

闸门原则
--------
- 以**腾讯日线**为锚（独立可信源）：分钟 bar 不得越出当日 [low, high]；
  首根 open≈日线 open；尾根 close=日线 close。
- 仅当严重度 ≥``min_repair_pct``（默认 0.5%）才自动修复；轻微越界/漂移只记 soft 事件。
- 修复值优先级：① 用同 store 完整 1m 成分重聚合（最真实）；② 锚定/保守值
  （首根 open←日线 open；越界极值←bar 自身 O/L/C 的保守界）。
- 幂等；仅用于港股（A 股分钟来自腾讯，未见此缺陷）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_MIN_REPAIR_PCT = 0.5
DEFAULT_SOFT_LOG_PCT = 0.1
DEFAULT_TOL_ABS = 0.01
DEFAULT_TOL_RATIO = 0.0002
DEFAULT_CARRY_EPS = 0.011

_FIRST_LABELS = {
    "1m": "09:31",
    "5m": "09:35",
    "15m": "09:45",
    "30m": "10:00",
    "60m": "10:30",
}
_CONSTITUENT_MINUTES = {"5m": 5, "15m": 15, "30m": 30, "60m": 60}
GATE_TIMEFRAMES = ("1m", "5m", "30m")


@dataclass(frozen=True)
class PhantomEvent:
    """一次检测/修复记录；``changed=False`` 表示 soft（只记录不改数据）。"""

    symbol: str
    timeframe: str
    ts: str
    position: str  # first / tail / mid
    field: str  # open / high / low / close
    before: float
    after: float
    changed: bool
    reason: str
    source: str  # from_1m / anchored / carried / soft
    severity_pct: float

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "ts": self.ts,
            "position": self.position,
            "field": self.field,
            "before": self.before,
            "after": self.after,
            "changed": self.changed,
            "reason": self.reason,
            "source": self.source,
            "severity_pct": round(self.severity_pct, 4),
        }


def _tol(limit: float, tol_abs: float, tol_ratio: float) -> float:
    return max(tol_abs, tol_ratio * abs(limit))


def _beyond(value: float, low: float, high: float, tol: float) -> bool:
    return value > high + tol or value < low - tol


def _day_groups(rows: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        day = str(row["ts"])[:10]
        groups.setdefault(day, []).append(row)
    for bars in groups.values():
        bars.sort(key=lambda item: str(item["ts"]))
    return groups


def _aggregate(constituents: list[dict]) -> dict:
    ordered = sorted(constituents, key=lambda item: str(item["ts"]))
    return {
        "open": float(ordered[0]["open"]),
        "high": max(float(item["high"]) for item in ordered),
        "low": min(float(item["low"]) for item in ordered),
        "close": float(ordered[-1]["close"]),
    }


def _constituents_for(
    bar_ts: str,
    timeframe: str,
    one_min_by_day: dict[str, list[dict]],
) -> list[dict] | None:
    """返回覆盖该 bar 的完整 1m 成分 bars；不完整返回 None。"""
    expected = _CONSTITUENT_MINUTES.get(timeframe)
    if expected is None:
        return None
    pool = one_min_by_day.get(bar_ts[:10])
    if not pool:
        return None
    try:
        end = datetime.strptime(bar_ts, "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    start = end - timedelta(minutes=expected)
    picked = [
        item
        for item in pool
        if start < datetime.strptime(str(item["ts"]), "%Y-%m-%d %H:%M") <= end
    ]
    return picked if len(picked) == expected else None


def apply_hk_minute_phantom_gate(
    rows: list[dict],
    *,
    symbol: str,
    timeframe: str,
    day_rows: list[dict],
    one_min_rows: list[dict] | None = None,
    min_repair_pct: float = DEFAULT_MIN_REPAIR_PCT,
    soft_log_pct: float = DEFAULT_SOFT_LOG_PCT,
    tol_abs: float = DEFAULT_TOL_ABS,
    tol_ratio: float = DEFAULT_TOL_RATIO,
    carry_eps: float = DEFAULT_CARRY_EPS,
) -> tuple[list[dict], list[PhantomEvent]]:
    """检测并修复港股分钟线幽灵价（纯函数，无文件 IO）。

    Returns:
        (新 rows, 事件列表)。未变动的 bar 原样返回；被修复的 bar 是新的 dict。
    """
    if not rows or not day_rows:
        return list(rows), []

    day_map = {
        str(item["ts"])[:10]: item
        for item in day_rows
        if str(item.get("ts") or "").strip()
    }
    if not day_map:
        return list(rows), []

    one_min_by_day = (
        _day_groups(one_min_rows)
        if (one_min_rows and timeframe != "1m")
        else {}
    )

    events: list[PhantomEvent] = []
    out: list[dict] = []

    for day, bars in _day_groups(rows).items():
        day_bar = day_map.get(day)
        if day_bar is None:
            out.extend(bars)
            continue
        day_open = float(day_bar["open"])
        day_high = float(day_bar["high"])
        day_low = float(day_bar["low"])
        day_close = float(day_bar["close"])
        last_ts = str(bars[-1]["ts"])
        first_label = _FIRST_LABELS.get(timeframe)

        for bar in bars:
            ts = str(bar["ts"])
            hhmm = ts[11:16] if len(ts) >= 16 else ""
            is_first = first_label is not None and hhmm == first_label
            is_tail = ts == last_ts and hhmm in {"16:00", "12:00"}
            pos = "first" if is_first else ("tail" if is_tail else "mid")

            new = dict(bar)
            changed = False
            o = float(bar["open"])
            c = float(bar["close"])
            high = float(bar["high"])
            low = float(bar["low"])

            def emit(field, before, after, did_change, reason, source, sev):
                events.append(
                    PhantomEvent(
                        symbol=symbol,
                        timeframe=timeframe,
                        ts=ts,
                        position=pos,
                        field=field,
                        before=float(before),
                        after=float(after),
                        changed=did_change,
                        reason=reason,
                        source=source,
                        severity_pct=sev,
                    )
                )

            # ---- 1) 越界判定（基于原始值）----
            high_over = high - day_high
            low_over = day_low - low
            high_sev = (high_over / day_high * 100) if high_over > _tol(day_high, tol_abs, tol_ratio) else 0.0
            low_sev = (low_over / day_low * 100) if low_over > _tol(day_low, tol_abs, tol_ratio) else 0.0
            high_done = False
            low_done = False

            # ---- 2) 首根 open 锚定（陈旧价签名）----
            if is_first:
                drift_pct = abs(o - day_open) / day_open * 100 if day_open else 0.0
                beyond = _beyond(o, day_low, day_high, _tol(day_open, tol_abs, tol_ratio))
                if drift_pct >= min_repair_pct or (beyond and drift_pct >= soft_log_pct):
                    new["open"] = day_open
                    changed = True
                    emit("open", o, day_open, True,
                         "open_beyond_day_range" if beyond else "open_anchor_drift",
                         "anchored", drift_pct)
                    # 幽灵开盘价常同时带跑 low/high（L==O 或 H==O）
                    carry_low = abs(low - o) <= carry_eps and low_sev < min_repair_pct
                    carry_high = abs(high - o) <= carry_eps and high_sev < min_repair_pct
                    agg = None
                    if carry_low or carry_high:
                        constituents = _constituents_for(ts, timeframe, one_min_by_day)
                        if constituents is not None:
                            clean, _ = apply_hk_minute_phantom_gate(
                                constituents,
                                symbol=symbol,
                                timeframe="1m",
                                day_rows=day_rows,
                                one_min_rows=None,
                                min_repair_pct=min_repair_pct,
                                soft_log_pct=soft_log_pct,
                                tol_abs=tol_abs,
                                tol_ratio=tol_ratio,
                            )
                            agg = _aggregate(clean)
                    if carry_low:
                        new_low = agg["low"] if agg is not None else min(day_open, c)
                        if abs(new_low - low) > 1e-9:
                            emit("low", low, new_low, True, "carried_from_open", "carried", drift_pct)
                            new["low"] = new_low
                            changed = True
                        low_done = True
                    if carry_high:
                        base_low = float(new["low"])
                        new_high = agg["high"] if agg is not None else max(day_open, base_low, c)
                        if abs(new_high - high) > 1e-9:
                            emit("high", high, new_high, True, "carried_from_open", "carried", drift_pct)
                            new["high"] = new_high
                            changed = True
                        high_done = True
                elif drift_pct >= soft_log_pct:
                    emit("open", o, o, False, "open_anchor_drift_soft", "soft", drift_pct)

            # ---- 3) 尾根 close 锚定 ----
            if is_tail:
                drift_pct = abs(c - day_close) / day_close * 100 if day_close else 0.0
                beyond = _beyond(c, day_low, day_high, _tol(day_close, tol_abs, tol_ratio))
                if drift_pct >= min_repair_pct or beyond:
                    new["close"] = day_close
                    changed = True
                    emit("close", c, day_close, True, "close_anchor_drift", "anchored", drift_pct)
                elif drift_pct >= soft_log_pct:
                    emit("close", c, c, False, "close_anchor_drift_soft", "soft", drift_pct)

            # ---- 4) 越界极值修复 ----
            if (high_sev >= min_repair_pct and not high_done) or (low_sev >= min_repair_pct and not low_done):
                agg = None
                constituents = _constituents_for(ts, timeframe, one_min_by_day)
                if constituents is not None:
                    clean, _ = apply_hk_minute_phantom_gate(
                        constituents,
                        symbol=symbol,
                        timeframe="1m",
                        day_rows=day_rows,
                        one_min_rows=None,
                        min_repair_pct=min_repair_pct,
                        soft_log_pct=soft_log_pct,
                        tol_abs=tol_abs,
                        tol_ratio=tol_ratio,
                    )
                    agg = _aggregate(clean)
                if high_sev >= min_repair_pct and not high_done:
                    after = agg["high"] if agg is not None else max(float(new["open"]), float(new["low"]), c)
                    if abs(after - high) > 1e-9:
                        emit("high", high, after, True, "beyond_day_range",
                             "from_1m" if agg is not None else "anchored", high_sev)
                        new["high"] = after
                        changed = True
                    high_done = True
                if low_sev >= min_repair_pct and not low_done:
                    after = agg["low"] if agg is not None else min(float(new["open"]), c)
                    if abs(after - low) > 1e-9:
                        emit("low", low, after, True, "beyond_day_range",
                             "from_1m" if agg is not None else "anchored", low_sev)
                        new["low"] = after
                        changed = True
                    low_done = True

            # ---- 5) soft 记录（未被修复的轻微越界）----
            if high_sev and not high_done:
                emit("high", high, high, False, "beyond_day_range_soft", "soft", high_sev)
            if low_sev and not low_done:
                emit("low", low, low, False, "beyond_day_range_soft", "soft", low_sev)

            if changed:
                new["close"] = c
                new["high"] = max(float(new["high"]), float(new["open"]), float(new["low"]), c)
                new["low"] = min(float(new["low"]), float(new["open"]), float(new["high"]), c)
                out.append(new)
            else:
                out.append(bar)

    return out, events


# --------------------------------------------------------------------------
# 与本地仓库对接的便捷入口
# --------------------------------------------------------------------------


def run_hk_phantom_gate(
    symbol: str,
    timeframe: str,
    rows: list[dict],
    *,
    store_root: Path | None = None,
    min_repair_pct: float = DEFAULT_MIN_REPAIR_PCT,
) -> tuple[list[dict], dict]:
    """读取本地仓库中的日线锚 / 1m 成分后执行闸门，返回 (rows, 摘要)。"""
    from chanlun.data.local_bar_store import load_local_rows

    day_rows = load_local_rows(symbol, "HK", "day", root=store_root)
    if not day_rows:
        return list(rows), {
            "applied": False,
            "skipped": "no_day_anchor",
            "repaired": 0,
            "soft": 0,
            "events": [],
        }
    one_min_rows = (
        load_local_rows(symbol, "HK", "1m", root=store_root)
        if timeframe != "1m"
        else None
    )
    gated, events = apply_hk_minute_phantom_gate(
        rows,
        symbol=symbol,
        timeframe=timeframe,
        day_rows=day_rows,
        one_min_rows=one_min_rows,
        min_repair_pct=min_repair_pct,
    )
    repaired = sum(1 for event in events if event.changed)
    summary = {
        "applied": True,
        "skipped": None,
        "repaired": repaired,
        "soft": len(events) - repaired,
        "events": [event.to_dict() for event in events if event.changed],
    }
    return gated, summary


__all__ = [
    "DEFAULT_MIN_REPAIR_PCT",
    "GATE_TIMEFRAMES",
    "PhantomEvent",
    "apply_hk_minute_phantom_gate",
    "run_hk_phantom_gate",
]
