---
applyTo: "scripts/**/*.py,src/chanlun/**/*.py"
description: "缠论图生成规范：每次生成缠论图表时遵循此要求"
---

# 缠论图生成规范

## 布局要求

- 上方主图：蜡烛图 + 笔 + 分型标记 + 中枢
- 下方副图：**MACD**（DIF/DEA/柱状图），**不使用成交量**

## MACD 规范

- 用全量 close 价格计算 MACD（EMA12/26/9），再按显示区间切片，保证指标连续性
- DIF 线：黄色 `#f0e040`
- DEA 线：橙色 `#ff8c00`
- 柱状图：正值红色 `#e84040`，负值绿色 `#26a69a`
- 零轴：灰色虚线

## 主图规范

- 深色主题，背景 `#0e0e0e` / `#141414`
- 蜡烛：上涨红 `#e84040`，下跌绿 `#26a69a`
- **笔**：黄色 `#f0c040` 折线，linewidth=2；已确认实线，未确认虚线
- **顶分型**：`▼` 红色 `#ff6b6b`，标注在 K 线高点上方
- **底分型**：`▲` 青色 `#4ecdc4`，标注在 K 线低点下方
- **中枢**：带透明填充的彩色矩形 + 虚线边界，右侧标注 `ZSn [low, high]`

## 坐标系映射

- 缠论管道（normalize → fractal → bi → zhongshu）**必须在全量数据上运行**，保证结构完整性
- 分型/笔的索引是归一化 bar 索引，通过 `nbars[ni].ts_end` → `ts2idx` 反查原始 bar 位置
- 过滤显示区间时用 `local_idx = orig_idx - cutoff_idx`，**不能**直接用归一化索引减 offset

## 坐标映射代码模板

```python
ts2idx = {b.ts: i for i, b in enumerate(all_bars)}

def nb_to_orig(ni):
    return ts2idx.get(nbars[ni].ts_end, min(ni, len(all_bars)-1))

cutoff_idx = next(i for i, b in enumerate(all_bars) if b.ts >= cutoff)
bars = all_bars[cutoff_idx:]
offset = cutoff_idx

# 分型定位
local_i = nb_to_orig(fx.center_bar_idx) - offset

# 笔定位
orig_s = nb_to_orig(bi.norm_bar_range[0])
orig_e = nb_to_orig(bi.norm_bar_range[1])
ls, le = orig_s - offset, orig_e - offset
```
