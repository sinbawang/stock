# 缠论严格理论规格

本文件现在只保留“严格理论总纲”，用于统一 review、后续实现和人工核图标准。

它不再重复维护基础结构、中枢、走势类型、背驰、买卖点等模块细节正文；这些内容应收敛到各自模块 spec。

它与 [chanlun-rule-spec.md](chanlun-rule-spec.md) 的分工如下：

- 本文件：严格理论总纲，只保留总原则、模块边界、跨模块红线和总 review 路径。
- [chanlun-rule-spec.md](chanlun-rule-spec.md)：规格主入口、阅读顺序、模块边界与历史整合正文。
- 模块 spec：分别承接基础结构、中枢、走势类型/背驰、买卖点/多级别联立等具体定义。
- [chanlun-spec-tasks.md](chanlun-spec-tasks.md)：严格理论落地进度、已完成任务和待完成任务。

阅读约定：

- 若问题是“缠论严格定义的总纲和红线是什么”，以本文件为准。
- 若问题是“某个模块的严格定义细则是什么”，以对应模块 spec 为准。
- 若问题是“当前代码做成了什么样”，以 [chanlun-rule-spec.md](chanlun-rule-spec.md) 和实现代码为准。
- 若两者不一致，应视为“实现尚未完全收敛到严格口径”，而不是反向改写理论定义。

## 1. 适用范围

本文件覆盖以下内容：

- 理论总原则
- 模块边界
- 跨模块约束
- review 主清单
- 与当前仓库的关系

本文件不讨论：

- 各模块的完整细节正文
- 指标调参
- 自动交易执行
- 某一市场的经验阈值
- 为了图表稳定性引入的工程折中

## 2. 基本原则

### 2.1 理论优先

- 缠论定义先于任何工程实现。
- 不允许因为当前代码、图表或发布层的既有结构，回头改写理论术语。

### 2.2 级别内闭环

- 任一结论必须先在本级别结构内闭环，再谈跨级别联立。
- 不允许用低级别局部信号直接覆盖本级别尚未完成的结构判断。

### 2.3 先结构，后指标

- 走势类型、中枢、背驰、买卖点属于结构结论。
- MACD、均线、量能等只能辅助解释，不能替代结构定义本身。

### 2.4 先分解，后结论

- 背驰、买卖点都必须依附于已完成的同级别分解和最近中枢语义。
- 不允许只看最后几笔的形状，绕过走势分解直接判点。

## 3. 模块结构图

### 3.1 主入口与任务页

- [chanlun-rule-spec.md](chanlun-rule-spec.md): 规格主入口与文档结构。
- [chanlun-spec-tasks.md](chanlun-spec-tasks.md): 完成度、已完成任务、待完成任务。

### 3.2 基础结构模块

- [base-structure-spec.md](base-structure-spec.md): 原始 K 线、包含关系、标准化 K 线、分型、笔。
- [segment-implementation-guide.md](segment-implementation-guide.md): 线段现行实现专题。
- [segment-doc-map.md](segment-doc-map.md): 线段专题导航。

### 3.3 中枢模块

- [zhongshu-core-spec.md](zhongshu-core-spec.md): 中枢核心理论定义。
- [zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md): 中枢/类中枢主辅消费与命名规范。
- [zhongshu-original-review-matrix.md](zhongshu-original-review-matrix.md): 原文复核矩阵。
- [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md): 图文化样例库。

### 3.4 高层结构模块

- [trend-divergence-spec.md](trend-divergence-spec.md): 走势类型、类背驰、盘整背驰、趋势背驰、背驰后去向。
- [buy-sell-multi-level-spec.md](buy-sell-multi-level-spec.md): 一二三类买卖点、区间套、小转大、多级别联立。

## 4. 各模块严格理论摘要

### 4.1 基础结构

- 基础结构是全链路的输入层。
- 先有原始 K 线清洗、包含关系处理、标准化 K 线，才有严格分型。
- 先有严格分型和成笔确认，才有稳定线段和上层结构。
- 细节定义看 [base-structure-spec.md](base-structure-spec.md)。

### 4.2 线段

- 线段是笔级结构对象，不是 K 线级对象。
- 线段终结必须服从特征序列和再分辨逻辑，不能只看单笔形状。
- 细节定义与实现边界看 [segment-implementation-guide.md](segment-implementation-guide.md)。

### 4.3 中枢

- 中枢是走势类型的核心组织单元。
- 严格中枢必须区分进入段、中枢本体、离开段。
- 标准中枢与类中枢必须严格分层，不能混名混义。
- 细节定义看 [zhongshu-core-spec.md](zhongshu-core-spec.md)。
- 主辅消费边界看 [zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md)。

### 4.4 走势类型与背驰

- 走势类型必须建立在同级别分解之上。
- 背驰必须依附最近中枢和同级别离开动作，不能退化成“指标钝化”。
- 盘整背驰和趋势背驰都必须回到中枢语义中解释。
- 细节定义看 [trend-divergence-spec.md](trend-divergence-spec.md)。

### 4.5 买卖点与多级别联立

- 一二三类买卖点都依附最近中枢和走势类型。
- 区间套只负责时机精度，不负责推翻高级别主结论。
- 小转大必须先有低级别转折，再有高级别结构吸收确认。
- 细节定义看 [buy-sell-multi-level-spec.md](buy-sell-multi-level-spec.md)。

## 5. 跨模块红线

1. 不允许因当前实现限制，回写或削弱理论定义。
2. 不允许脱离中枢定义走势类型、背驰和买卖点。
3. 不允许用类中枢单独升级为严格确认买卖点。
4. 不允许让指标信号覆盖结构主结论。
5. 不允许让低级别区间套信号推翻高级别未完成结构。
6. 不允许把未完成同级别分解直接包装成严格确认结论。
7. 不允许把工程观察态、辅助态、待确认态混写为 confirmed。

## 6. review 主清单

review 任一结构结论时，至少逐项检查：

1. 是否先定位到正确模块，而不是在总纲中补细节。
2. 基础结构是否已完成包含处理、标准化、分型、成笔确认。
3. 线段是否有明确起点、终点和终结依据。
4. 中枢是否区分进入段、本体、离开段。
5. 走势类型是否建立在同级别分解之上。
6. 背驰是否明确比较对象、最近中枢和离开方向。
7. 买卖点是否绑定最近中枢与阶段语义。
8. 多级别联立是否遵守“高级别定方向、低级别提精度”的分工。
9. 指标是否只做辅助而未覆盖结构主结论。
10. 若当前代码与严格定义不一致，是否已记录为实现差异或待办。

## 7. 与当前仓库的关系

当前仓库已经相对成熟的，主要是：

- 基础结构模块
- 线段工程实现和配套说明
- 中枢主辅术语边界
- 原文复核矩阵和案例库骨架

当前仍未严格落地完成的，主要是：

- 标准线段级中枢主实现
- 严格同级别走势类型自动分解
- 趋势背驰与盘整背驰严格自动判定
- 一二三类买卖点的严格主口径自动确认
- 多级别联立下的严格确认/降级规则

这些任务的进度跟踪见 [chanlun-spec-tasks.md](chanlun-spec-tasks.md)。

## 8. 使用建议

若你要改文档，按以下顺序判断：

1. 改总原则、跨模块红线、阅读路径：改本文件。
2. 改基础结构：改 [base-structure-spec.md](base-structure-spec.md)。
3. 改中枢理论：改 [zhongshu-core-spec.md](zhongshu-core-spec.md)。
4. 改中枢主辅消费：改 [zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md)。
5. 改走势类型/背驰：改 [trend-divergence-spec.md](trend-divergence-spec.md)。
6. 改买卖点/区间套/小转大/多级别联立：改 [buy-sell-multi-level-spec.md](buy-sell-multi-level-spec.md)。
7. 改完成度与待办：改 [chanlun-spec-tasks.md](chanlun-spec-tasks.md)。

总原则不应该替代模块 spec；模块 spec 也不应该反向覆盖总原则。

## 9. 关联文档

- [chanlun-rule-spec.md](chanlun-rule-spec.md)
- [chanlun-spec-tasks.md](chanlun-spec-tasks.md)
- [base-structure-spec.md](base-structure-spec.md)
- [segment-implementation-guide.md](segment-implementation-guide.md)
- [zhongshu-core-spec.md](zhongshu-core-spec.md)
- [zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md)
- [trend-divergence-spec.md](trend-divergence-spec.md)
- [buy-sell-multi-level-spec.md](buy-sell-multi-level-spec.md)
