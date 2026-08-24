# 走势类型与背驰原文复核矩阵（第一版）

本页用于回答两个问题：

- 走势类型、趋势背驰、盘整背驰模块与缠论原文是否对齐。
- 哪些条目已经有稳定文档支撑，哪些仍是工程摘要或待补。

当前结论：这是当前仓库里理论最复杂、自动化完成度最低的关键模块之一，适合用“复核矩阵 + 样例库”持续收敛。

## 1. 复核范围（首轮）

首轮聚焦以下课次：

- 第17课：走势终完美总纲。
- 第18课：走势类型、中枢与完成/未完成框架。
- 第29课：背驰-转折与三级去向。
- 第36课：连接结合律的当下重组。
- 第38课：同级别分解唯一性。
- 第39课：震荡节奏与 `A_i/A_{i+2}` 比较。

## 2. 逐课对照矩阵

| 课次 | 原文关键点（摘要） | 当前文档映射 | 判定 | 后续动作 |
| --- | --- | --- | --- | --- |
| 17 | 走势终完美；完成与未完成必须并存描述。 | [trend-divergence-spec.md](trend-divergence-spec.md) 已明确走势类型依赖同级别分解。 | 基本一致 | 补“完成边界 vs 当前进行结构”标准案例。 |
| 18 | 趋势、盘整定义必须依附中枢和同级别分解。 | [trend-divergence-spec.md](trend-divergence-spec.md) 已强调脱离中枢定义不完整。 | 基本一致 | 补“只有一个中枢，不得提前确认为趋势”的反例模板。 |
| 29 | 趋势背驰后去向只允许三级分流。 | [trend-divergence-spec.md](trend-divergence-spec.md) 已明确三级去向。 | 基本一致 | 补“不得发明第四类去向”的案例卡片。 |
| 36 | 允许重组，但不能改写已确认结构事实。 | [trend-ambiguity-combination-law.md](trend-ambiguity-combination-law.md) 已补系统性章节（结合律、允许/禁止重组判据、中枢选择规则）。 | 基本一致 | 补“允许重组/禁止重组”对照图。 |
| 38 | 同级别分解应唯一；多义不等于任意。 | [trend-ambiguity-combination-law.md](trend-ambiguity-combination-law.md) 已补唯一性与多义降级映射（`dual_interpretation_pending`）。 | 基本一致 | 补“双解释待确认”降级模板。 |
| 39 | 震荡节奏比较只应服务监视，不应越级确认买卖点。 | [trend-divergence-spec.md](trend-divergence-spec.md) 已保留节奏与监视定位。 | 基本一致 | 补阈值示例和降级说明。 |

## 3. 当前偏差与边界

1. 当前工程输出主要还是“结构状态摘要”，不是完整严格递归分解。
2. 趋势背驰与盘整背驰虽有文档定义，但自动判定链路仍不闭环。
3. 同级别分解唯一性与重组边界，仍需更多正反例支撑 review。

## 4. 下一轮文档任务

1. 补“趋势完成 vs 尾中枢扩展”对照图。
2. 补“趋势背驰 vs 盘整背驰”正反例对照卡。
3. 补“三级去向”标准样例和误判负例。
4. 补“允许重组/禁止重组”的复核图库。

## 5. 参考课文文件

- `books/chanzhongshuochan_lessons/articles_md/lesson_017_教你炒股票17：走势终完美.md`
- `books/chanzhongshuochan_lessons/articles_md/lesson_018_教你炒股票18：不被面首的雏男是不完美的。.md`
- `books/chanzhongshuochan_lessons/articles_md/lesson_029_教你炒股票29：转折的力度与级别.md`
- `books/chanzhongshuochan_lessons/articles_md/lesson_036_教你炒股票36：走势类型连接结合性的简单运用.md`
- `books/chanzhongshuochan_lessons/articles_md/lesson_038_教你炒股票38：走势类型连接的同级别分解.md`
- `books/chanzhongshuochan_lessons/articles_md/lesson_039_教你炒股票39：同级别分解再研究.md`
