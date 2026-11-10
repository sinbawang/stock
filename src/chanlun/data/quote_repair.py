"""修复行情中的非正 OHLC 价格。

典型场景：雪球港股分钟线会插入**零成交占位 bar**，其 ``open=0.0``，
而 high/low/close 仍是有效价（high=low=close）。这类 bar 若直接用于画图，
蜡烛实体从 0 画到收盘价，会形成贯穿全图的超长柱子。

修复原则
--------
- 价格必须为正；``open<=0`` 时优先用同一 bar 的 ``close``，
  其次用上一根有效 close，最后才回退到 high/low。
- ``close<=0`` / ``high<=0`` / ``low<=0`` 同理，尽量用同一 bar 的其他有效价。
- 修复后强制 ``high >= max(open, close)`` 且 ``low <= min(open, close)``。
- 无法恢复（全部价格非正）的行原样保留，由上层决定是否丢弃。

该模块只处理价格，不修改时间戳与成交量；对合法数据是幂等的。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OhlcRepair:
    """单个字段的一次修复记录。"""

    field: str
    before: float
    after: float
    reason: str


def _first_positive(candidates: tuple[tuple[float | None, str], ...]) -> tuple[float, str] | None:
    for value, label in candidates:
        if value is not None and value > 0:
            return float(value), label
    return None


def repair_ohlc_values(
    open_: float,
    high: float,
    low: float,
    close: float,
    *,
    prev_close: float | None = None,
) -> tuple[float, float, float, float, list[OhlcRepair]]:
    """修复一组 OHLC 值，返回 ``(open, high, low, close, repairs)``。"""

    o, h, l, c = float(open_), float(high), float(low), float(close)
    repairs: list[OhlcRepair] = []

    if c <= 0:
        picked = _first_positive(
            ((o, "open"), (h, "high"), (l, "low"), (prev_close, "prev_close"))
        )
        if picked is not None:
            c = picked[0]
            repairs.append(OhlcRepair("close", close, c, f"nonpositive_close_filled_{picked[1]}"))

    if o <= 0:
        picked = _first_positive(
            ((c, "close"), (prev_close, "prev_close"), (h, "high"), (l, "low"))
        )
        if picked is not None:
            o = picked[0]
            repairs.append(OhlcRepair("open", open_, o, f"nonpositive_open_filled_{picked[1]}"))

    if h <= 0:
        picked = _first_positive(((o, "open"), (l, "low"), (c, "close"), (prev_close, "prev_close")))
        if picked is not None:
            h = picked[0]
            repairs.append(OhlcRepair("high", high, h, f"nonpositive_high_filled_{picked[1]}"))

    if l <= 0:
        picked = _first_positive(((o, "open"), (h, "high"), (c, "close"), (prev_close, "prev_close")))
        if picked is not None:
            l = picked[0]
            repairs.append(OhlcRepair("low", low, l, f"nonpositive_low_filled_{picked[1]}"))

    # 保证 high/low 包住实体；只对本来就越界的脏 bar 生效。
    if all(value > 0 for value in (o, h, l, c)):
        clamped_high = max(h, o, c)
        if clamped_high != h:
            repairs.append(OhlcRepair("high", h, clamped_high, "high_clamped_to_ohlc"))
            h = clamped_high
        clamped_low = min(l, o, c)
        if clamped_low != l:
            repairs.append(OhlcRepair("low", l, clamped_low, "low_clamped_to_ohlc"))
            l = clamped_low

    return o, h, l, c, repairs


def repair_nonpositive_quotes(rows: list[dict]) -> tuple[list[dict], list[tuple[str, OhlcRepair]]]:
    """修复 rows 中的非正 OHLC；返回 ``(rows, [(ts, repair), ...])``。

    未变化的 bar 原样返回（同一对象），变化的 bar 返回浅拷贝。
    """

    out: list[dict] = []
    repairs: list[tuple[str, OhlcRepair]] = []
    last_valid_close: float | None = None

    for row in rows:
        ts = str(row.get("ts") or "")
        try:
            o = float(row.get("open") or 0.0)
            h = float(row.get("high") or 0.0)
            l = float(row.get("low") or 0.0)
            c = float(row.get("close") or 0.0)
        except (TypeError, ValueError):
            out.append(row)
            continue

        if o > 0 and h > 0 and l > 0 and c > 0:
            out.append(row)
            last_valid_close = c
            continue

        new_o, new_h, new_l, new_c, row_repairs = repair_ohlc_values(
            o, h, l, c, prev_close=last_valid_close
        )
        if row_repairs:
            updated = dict(row)
            updated["open"] = new_o
            updated["high"] = new_h
            updated["low"] = new_l
            updated["close"] = new_c
            out.append(updated)
            repairs.extend((ts, item) for item in row_repairs)
        else:
            out.append(row)

        if new_c > 0:
            last_valid_close = new_c

    return out, repairs


__all__ = ["OhlcRepair", "repair_ohlc_values", "repair_nonpositive_quotes"]
