---
spec_id: SPEC.BASE_STRUCTURE.CORE
status: stable
owner: chanlun
applyTo: src/chanlun/normalize.py, src/chanlun/fractal.py, src/chanlun/bi.py
tests: tests/test_normalize.py, tests/test_fractal.py, tests/test_bi.py
---

# 基础结构规格

本文件定义缠论底层结构口径，覆盖：

- 原始 K 线数据约束
- 包含关系处理
- 标准化 K 线
- 分型
- 笔

这部分是整个缠论链路的底层输入层。若底层口径不稳定，上层线段、中枢、走势类型、背驰、买卖点都会漂移。

## 1. 当前定位

> 实然状态（完成度 / 收敛进度）见 [chanlun-spec-tasks.md](chanlun-spec-tasks.md) 与
> [theory-implementation-consumer-diff-matrix.md](theory-implementation-consumer-diff-matrix.md)；
> 本文件只保留理论口径（应然）。

- 理论成熟度：高
- 当前文档完整度：高

## 2. 原始 K 线约束

每根 K 线至少包含：

- `ts`
- `open`
- `high`
- `low`
- `close`

约束：

- 时间必须升序。
- 不允许重复时间戳。
- 不允许 `high < low`。
- 缺失关键字段的数据必须先清洗，再进入结构识别。

## 3. 包含关系处理

相邻两根 K 线 `A`、`B` 满足以下任一条件时，构成包含：

- `A.high >= B.high` 且 `A.low <= B.low`
- `A.high <= B.high` 且 `A.low >= B.low`

严格要求：

- 必须先判定当前处理方向，再做合并。
- 向上时保留更高高点和更高低点。
- 向下时保留更低高点和更低低点。
- 连续包含链在未出现新的非包含方向证据前，不得中途翻转。

## 4. 标准化 K 线

包含关系处理后得到 `normalized_bars`。

后续分型、笔、线段都应基于标准化 K 线，而不是原始 K 线直接计算。

每根标准化 K 线至少应保留：

- 合并后价格区间
- 起止时间范围
- 原始 K 线来源索引

## 5. 分型

### 5.1 顶分型

在连续 3 根标准化 K 线中，中间一根同时满足：

- 高点高于左右两侧
- 低点高于左右两侧

则构成严格顶分型。

### 5.2 底分型

在连续 3 根标准化 K 线中，中间一根同时满足：

- 高点低于左右两侧
- 低点低于左右两侧

则构成严格底分型。

### 5.3 分型约束

- 首尾两根不能构成分型。
- 连续同类分型只保留最强者。
- 不接受“近似分型”替代严格三 K 分型。

## 6. 笔

### 6.1 定义

- 底分型到后续顶分型，形成向上一笔。
- 顶分型到后续底分型，形成向下一笔。

### 6.2 成笔约束

- 两端分型窗口不得重叠。
- 极值 K 线之间必须满足最小间隔。
- 向上笔终点必须高于起点底分型价格。
- 向下笔终点必须低于起点顶分型价格。
- 若后续出现更强同类终点，应替代旧终点。

### 6.3 笔的确认

- 笔允许在尾端延伸。
- 只有后续出现满足确认条件的反向结构，前一笔才确认。
- 分型有效性与笔确认联动，不能把所有三 K 分型直接当成后续走势分解的稳定输入。

## 7. 与其他模块的关系

- 线段以上游的已确认笔为输入。
- 中枢理论上以上游走势类型为输入，当前工程中常通过笔或线段近似。
- 走势类型、背驰、买卖点的所有分歧，最后都要回溯到底层分型和笔是否稳定。

## 8. 维护建议

- 若改动包含关系、分型、笔，优先修改本文件。
- 若改动只影响线段，不要回写本文件的基础定义。
- 若未来底层理论出现争议，先在本文件记录主定义，再在上层模块说明传播影响。

## 9. 关联文档

- [chanlun-rule-spec.md](chanlun-rule-spec.md)
- [chanlun-strict-theory-spec.md](chanlun-strict-theory-spec.md)
- [base-structure-original-review-matrix.md](base-structure-original-review-matrix.md)
- [base-structure-visual-example-library.md](base-structure-visual-example-library.md)
- [segment-implementation-guide.md](segment-implementation-guide.md)
