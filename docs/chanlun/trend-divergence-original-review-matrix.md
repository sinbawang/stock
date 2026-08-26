# 走势类型与背驰原文复核矩阵（第一版）

本页用于回答两个问题：

- 走势类型、趋势背驰、盘整背驰模块与缠论原文是否对齐。
- 哪些条目已经有稳定文档支撑，哪些仍是工程摘要或待补。

当前结论：这是当前仓库里理论最复杂、自动化完成度最低的关键模块之一，适合用“复核矩阵 + 样例库”持续收敛。

## 1. 复核范围（首轮）

首轮聚焦以下课次：

- 第17课：走势终完美总纲。
- 第18课：走势类型、中枢与完成/未完成框架。
- 第24课：MACD 对背驰的辅助判断。
- 第27课：盘整背驰与历史性底部。
- 第29课：背驰-转折与三级去向。
- 第36课：连接结合律的当下重组。
- 第37课：背驰的再分辨。
- 第38课：同级别分解唯一性。
- 第39课：震荡节奏与 `A_i/A_{i+2}` 比较。
- 第43课：有关背驰的补习课（背驰级别与走势级别的两种关系）。

## 2. 逐课对照矩阵

| 课次 | 原文关键点（摘要） | 当前文档映射 | 判定 | 后续动作 |
| --- | --- | --- | --- | --- |
| 17 | 走势终完美；完成与未完成必须并存描述。 | [trend-divergence-spec.md](trend-divergence-spec.md) 已明确走势类型依赖同级别分解。 | 基本一致 | 补“完成边界 vs 当前进行结构”标准案例。 |
| 18 | 趋势、盘整定义必须依附中枢和同级别分解。 | [trend-divergence-spec.md](trend-divergence-spec.md) 已强调脱离中枢定义不完整。 | 基本一致 | 补“只有一个中枢，不得提前确认为趋势”的反例模板。 |
| 24 | MACD 判断背驰需 A/B/C 三段、B 中枢回拉 0 轴附近、C 段柱面积小于 A 段；盘整背驰两种情形：不破中枢必回跌，破中枢但力度弱则先出、回跌不回中枢构成第三类买点。 | [trend-divergence-spec.md](trend-divergence-spec.md) §8 已把指标定位为辅助；`divergence.trend.strength_comparison` 已用 MACD 力度代理。 | 基本一致（指标辅助口径） | 补“A/B/C 三段 + 0 轴回拉”标准图例，显式标注“柱面积乘 2”为工程近似。 |
| 27 | 趋势至少两中枢，背驰至少发生在第二中枢之后；第一中枢背驰只能算盘整背驰；盘整背驰构成二/三类买点；大级别盘整背驰常对应历史大底；精确大转折点寻找程序定理 = 区间套逐级收缩。 | [trend-divergence-spec.md](trend-divergence-spec.md) §5 盘整背驰 + [buy-sell-multi-level-spec.md](buy-sell-multi-level-spec.md) §3 区间套 + `precision_entry`。 | 基本一致 | 补“第一中枢不得判为趋势背驰”反例；补“大级别盘整背驰→历史底”级别标注示例。 |
| 29 | 趋势背驰后去向只允许三级分流。 | [trend-divergence-spec.md](trend-divergence-spec.md) 已明确三级去向。 | 基本一致 | 补“不得发明第四类去向”的案例卡片。 |
| 36 | 允许重组，但不能改写已确认结构事实。 | [trend-ambiguity-combination-law.md](trend-ambiguity-combination-law.md) 已补系统性章节（结合律、允许/禁止重组判据、中枢选择规则）。 | 基本一致 | 补“允许重组/禁止重组”对照图。 |
| 37 | 无趋势无背驰；a+A+b+B+c 中 A、B 必须同级别；c 必为次级别且必含 B 的第三类买卖点；c 必创新高/新低；b 级别 ≤ c。 | [trend-divergence-spec.md](trend-divergence-spec.md) §4 已要求比较对象/最近中枢/离开段；`departure_confirmed` 已表达 c 创新高/新低。 | 基本一致（c 含三买、b≤c 未显式） | 补“A/B 不同级别只能算盘整背驰”反例；补“c 未创新高即按盘整背驰”负例。 |
| 38 | 同级别分解应唯一；多义不等于任意。 | [trend-ambiguity-combination-law.md](trend-ambiguity-combination-law.md) 已补唯一性与多义降级映射（`dual_interpretation_pending`）。 | 基本一致 | 补“双解释待确认”降级模板。 |
| 39 | 震荡节奏比较只应服务监视，不应越级确认买卖点。 | [trend-divergence-spec.md](trend-divergence-spec.md) 已保留节奏与监视定位。 | 基本一致 | 补阈值示例和降级说明。 |
| 43 | 背驰-转折定理；背驰级别 = 当下走势级别（必拉回最后中枢）vs 背驰级别 < 当下走势级别（须先形成更大中枢）两种转折方式；走势类型分解原则（某级别走势不可能出现更大级别中枢）。 | [trend-divergence-spec.md](trend-divergence-spec.md) §7 三级去向 + [buy-sell-multi-level-spec.md](buy-sell-multi-level-spec.md) §4 小转大。 | 基本一致（两种转折方式未显式区分） | 补“背驰级别 =/>/< 当下级别”对照表；补小级别背驰先成大中枢的降级模板。 |

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
- `books/chanzhongshuochan_lessons/articles_md/lesson_024_教你炒股票24：MACD对背弛的辅助判断.md`
- `books/chanzhongshuochan_lessons/articles_md/lesson_027_教你炒股票27： 盘整背驰与历史性底部.md`
- `books/chanzhongshuochan_lessons/articles_md/lesson_037_教你炒股票37：背驰的再分辨.md`
- `books/chanzhongshuochan_lessons/articles_md/lesson_043_教你炒股票43：有关背驰的补习课.md`
