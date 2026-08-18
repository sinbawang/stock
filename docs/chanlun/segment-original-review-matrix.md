# 线段原文复核矩阵（第一版）

本页用于回答两个问题：

- 当前线段模块与缠论原文线段定义的对应关系是否已经拆清。
- 哪些部分属于现行工程闭环，哪些部分仍是严格理论待补项。

当前结论：线段模块是本仓库里“工程闭环最完整、但理论与工程边界也最需要显式标注”的关键模块，因此非常适合单独维护原文复核矩阵。

## 1. 复核范围（首轮）

首轮聚焦线段最关键的原文与复盘材料：

- 第62课：分型、笔、线段的关系。
- 第63课：替代与确认边界对线段起止的影响。
- 第67课：线段划分标准与第一/第二种情况。
- 第71课：线段划分标准的再分辨。

说明：

- 本页只负责“原文定义与当前口径”的对照，不代替当前工程实现说明。
- 当前工程实现口径仍以 [segment-implementation-guide.md](segment-implementation-guide.md) 为准。

## 2. 逐课对照矩阵

| 课次 | 原文关键点（摘要） | 当前文档映射 | 判定 | 后续动作 |
| --- | --- | --- | --- | --- |
| 62 | 线段必须建立在笔的结构稳定性之上，不能脱离分型、笔的确认链。 | [segment-implementation-guide.md](segment-implementation-guide.md) 已明确线段仅基于确认笔生成。 | 基本一致 | 补“未确认尾笔不入段”的标准负例图。 |
| 63 | 替代与确认会影响线段起段、延伸和终结，不能把候选状态误写成已确认结构。 | [segment-implementation-guide.md](segment-implementation-guide.md) 已区分确认线段与未确认尾段。 | 基本一致 | 补“候选终结 vs 已确认终结”的对照卡片。 |
| 67 | 起段三笔必须满足公共重叠；反向特征序列分型和第一/第二种情况是线段确认核心。 | [segment-implementation-guide.md](segment-implementation-guide.md) 已覆盖起段三笔公共重叠、直接分型终结、缺口第二种情况。 | 基本一致 | 补“第一种情况/第二种情况”并列图。 |
| 71 | 第一二元素存在缺口时，需通过再分辨决定旧段终结还是延续。 | [segment-implementation-guide.md](segment-implementation-guide.md) 已实现最小再分辨闭环，并在 [../analysis/chanlun-line-segment-original-and-comparison.md](../analysis/chanlun-line-segment-original-and-comparison.md) 留有背景分析。 | 工程近似但主路径已闭环 | 继续补 R1-R6 正反例，并标清“已实现”与“待补”分支。 |

## 3. 当前偏差与边界

1. 当前实现已经稳定覆盖 67 课主路径和 71 课最小闭环，但并不等于 71 课完整严格实现。
2. `bootstrap_mode`、窗口截断和工程评分属于实现层稳定性策略，不属于原文线段定义本身。
3. `stop_reason` 是工程消费契约，不应反向当作理论定义。

## 4. 现有文档职责分工

- 理论/原文复核：本页 [segment-original-review-matrix.md](segment-original-review-matrix.md)
- 当前实现主口径：[segment-implementation-guide.md](segment-implementation-guide.md)
- 契约与消费层：[segment-stop-reason-contract.md](segment-stop-reason-contract.md)
- 背景分析与偏差来源：[../analysis/chanlun-line-segment-original-and-comparison.md](../analysis/chanlun-line-segment-original-and-comparison.md)
- 图文化案例库：[segment-visual-example-library.md](segment-visual-example-library.md)

## 5. 下一轮文档任务

1. 补“起段三笔公共重叠成立/不成立”成套图例。
2. 补“直接特征序列分型终结”正例与伪分型负例。
3. 补“67 课第二种情况”标准时序卡片。
4. 补“71 课再分辨 R1-R6”案例映射表。
5. 增加“理论定义 / 工程启发式 / 消费契约”三层边界示意图。

## 6. 参考课文文件

- `books/chanzhongshuochan_lessons/articles_md/lesson_062_教你炒股票62：分型、笔与线段的关系.md`
- `books/chanzhongshuochan_lessons/articles_md/lesson_063_教你炒股票63：替代与确认的边界.md`
- `books/chanzhongshuochan_lessons/articles_md/lesson_067_教你炒股票67：线段划分标准的再研究.md`
- `books/chanzhongshuochan_lessons/articles_md/lesson_071_教你炒股票71：线段划分标准的再分辨.md`
