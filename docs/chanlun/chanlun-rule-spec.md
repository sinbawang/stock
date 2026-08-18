# 缠论规则规格

这份文档现在作为缠论规格主入口，负责定义文档结构、模块边界、阅读顺序和总原则。

详细规则不应长期继续堆在一个总文件里，而应优先下沉到对应模块 spec。

阅读提示：

- 若要看“严格按缠论原文整理的总纲”，先看 [chanlun-strict-theory-spec.md](chanlun-strict-theory-spec.md)。
- 若要看“严格理论落地到了哪一步、还有哪些任务未完成”，看 [chanlun-spec-tasks.md](chanlun-spec-tasks.md)。
- 若要修改某一模块定义，优先改对应模块 spec，不要先改总入口。

## 1. 主入口定位

建议把本文件视为“总 spec 入口页”，而不是继续膨胀成唯一巨型规则正文。

原因：

- `chanlun-rule-spec.md` 和 `chanlun-strict-theory-spec.md` 目前覆盖主题高度重叠。
- `segment`、`zhongshu` 已经证明专题 spec 更适合 review 和持续维护。
- 走势类型、背驰、买卖点、多级别联立这类高层模块，后续变化频率高，更适合单独维护。

## 2. 推荐文档结构

### 2.1 总入口

- [chanlun-rule-spec.md](chanlun-rule-spec.md): 主入口、总原则、模块边界、阅读顺序。
- [chanlun-strict-theory-spec.md](chanlun-strict-theory-spec.md): 严格理论总纲，只保留高层定义，不承接工程细节。
- [chanlun-spec-tasks.md](chanlun-spec-tasks.md): 当前完成度、已完成任务、待完成任务。

### 2.2 基础结构模块

- [base-structure-spec.md](base-structure-spec.md): 原始 K 线、包含关系、标准化 K 线、分型、笔。
- [segment-implementation-guide.md](segment-implementation-guide.md): 线段现行实现专题。
- [segment-doc-map.md](segment-doc-map.md): 线段专题导航。

### 2.3 中枢模块

- [zhongshu-core-spec.md](zhongshu-core-spec.md): 中枢核心理论规格。
- [zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md): 中枢/类中枢主辅规范。
- [zhongshu-original-review-matrix.md](zhongshu-original-review-matrix.md): 原文复核矩阵。
- [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md): 中枢图文化案例。

### 2.4 高层结构模块

- [trend-divergence-spec.md](trend-divergence-spec.md): 走势类型、类背驰、盘整背驰、趋势背驰、背驰后去向。
- [buy-sell-multi-level-spec.md](buy-sell-multi-level-spec.md): 一二三类买卖点、区间套、小转大、多级别联立。

## 3. 当前模块完成度判断

按当前仓库状态，更合理的判断是：

- 基础结构模块：相对成熟，可视为优先冻结口径。
- 线段模块：工程实现和配套文档已较完整，但严格理论仍有继续收敛空间。
- 中枢模块：已有主辅规范和复核矩阵，但标准中枢主实现仍未彻底收敛。
- 高层结构模块：走势类型、背驰、盘整背驰、区间套、小转大、1/2/3 类买卖点，当前仍是最不确定、最需要独立维护的部分。

这和你的判断基本一致：

- 包含关系、标准 K 线、分型、笔、线段，当前更完善。
- 中枢还有待继续补强。
- 其他高层模块现在最不应继续塞进一个大而全的总文档里。

## 4. 修改原则

- 改基础结构：优先改 [base-structure-spec.md](base-structure-spec.md)。
- 改线段：优先改线段专题文档。
- 改中枢：优先改中枢专题文档。
- 改走势类型/背驰：优先改 [trend-divergence-spec.md](trend-divergence-spec.md)。
- 改买卖点/区间套/小转大/多级别联立：优先改 [buy-sell-multi-level-spec.md](buy-sell-multi-level-spec.md)。
- 改总体进度或待办：优先改 [chanlun-spec-tasks.md](chanlun-spec-tasks.md)。

## 5. 现状说明

下方历史正文保留，主要是为了不立刻打断现有阅读和引用路径。

但从现在开始，新增或实质性修订应尽量写入对应模块 spec；等模块文档收敛后，再逐步把本文件中的大段细节下沉或删减，避免继续维护两份重复正文。

## 6. 历史整合正文（待逐步下沉）

以下内容保留为历史整合正文，后续应逐步迁移到对应模块 spec。

## 7. 范围

本节保留为历史范围摘要。

当前主入口覆盖的模块是：

- 基础结构：K 线、包含关系、标准化 K 线、分型、笔
- 线段
- 中枢
- 走势类型与背驰
- 买卖点与多级别联立

详细规则已经下沉到对应模块 spec；本文件不再承接完整模块正文。

## 8. 统一数据约定

本节已下沉到 [base-structure-spec.md](base-structure-spec.md)。

历史摘要：

- K 线数据必须满足时间升序、无重复时间、`high >= low`。
- 结构识别前必须先完成基础清洗和字段标准化。
- 不同分析级别不应在同一次主流程中混用主结构定义。

## 9. 预处理规则

本节已下沉到 [base-structure-spec.md](base-structure-spec.md)。

历史摘要：

- 先去包含，再识别分型。
- 包含关系处理必须先确定方向，不能在方向未知时强行合并。
- 标准化 K 线是后续分型、笔、线段的共同基础输入。

若后续需要改包含关系、标准化 K 线或基础清洗规则，优先修改 [base-structure-spec.md](base-structure-spec.md)。

## 10. 分型定义

本节已下沉到 [base-structure-spec.md](base-structure-spec.md)。

历史摘要：

- 分型基于连续 3 根标准化 K 线判断。
- 顶分型和底分型都采用严格三 K 口径，不接受近似替代。
- 连续同类分型应去重，只保留最强者。

## 11. 笔定义

本节已下沉到 [base-structure-spec.md](base-structure-spec.md)。

历史摘要：

- 笔由类型相反的有效分型构成，必须满足端点价格约束和最小间隔约束。
- 笔允许尾端延伸，但确认后应冻结。
- 分型确认与笔确认联动，不能把所有三 K 分型直接视为稳定输入。
- 当前工程仍保留若干 `pending_reverse_mode` 口径差异，这属于实现层边界，不再在主入口展开。

若后续需要改分型、成笔条件、笔确认或底层实现边界，优先修改 [base-structure-spec.md](base-structure-spec.md)。

## 12. 线段定义

本节已下沉到线段专题文档，主入口只保留摘要和跳转。

对应专题：

- [segment-implementation-guide.md](segment-implementation-guide.md): 当前线段实现专题。
- [segment-doc-map.md](segment-doc-map.md): 线段文档导航。
- [segment-stop-reason-contract.md](segment-stop-reason-contract.md): `stop_reason` 稳定接口契约。
- [segment-to-zhongshu-mode-protocol-draft.md](segment-to-zhongshu-mode-protocol-draft.md): 线段到中枢模式传递协议。

本节仅保留以下历史摘要：

- 线段基于已确认笔，不直接从 K 线生成。
- 当前实现采用工程化简化线段口径，已形成稳定图表和测试闭环。
- 严格理论层仍有进一步收敛空间，但不应再把实现细节堆回主入口。
- 线段层的 `termination_mode`、`stop_reason` 和中枢传递语义应由专题文档维护。

若后续需要改线段起段、终结、再分辨、双模式消费或安全闸门，优先修改对应线段专题文档。

## 13. 中枢定义

本节已下沉到中枢专题文档，主入口只保留摘要和跳转。

当前中枢模块应按 4 层阅读：

- [zhongshu-core-spec.md](zhongshu-core-spec.md): 中枢核心理论定义。
- [zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md): 中枢/类中枢主辅消费与命名规范。
- [zhongshu-original-review-matrix.md](zhongshu-original-review-matrix.md): 原文复核矩阵与逐课对照。
- [zhongshu-visual-example-library.md](zhongshu-visual-example-library.md): 图文化样例与发布层表达。

本节仅保留以下历史摘要：

- 严格中枢必须区分进入段、中枢本体和离开段。
- 标准中枢是主口径，类中枢是辅助口径，二者不得混名混义。
- 尾中枢完成不等于走势类型已经最终结束；必须等待右侧结构证明边界稳定。
- 中枢相关结论必须能回溯到可复核的区间、离开段和级别语义。

若后续需要改中枢理论本身，优先修改 [zhongshu-core-spec.md](zhongshu-core-spec.md)。
若需要改主辅消费、命名、降级与冲突处理，优先修改 [zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md)。

## 14. 走势类型与背驰定义

本节已下沉到高层结构专题文档，主入口只保留摘要和跳转。

对应专题：

- [trend-divergence-spec.md](trend-divergence-spec.md): 走势类型、类背驰、盘整背驰、趋势背驰、背驰后去向。
- [zhongshu-core-spec.md](zhongshu-core-spec.md): 与中枢强绑定的理论前提。
- [zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md): 主辅消费和降级边界。

本节仅保留以下历史摘要：

- 走势类型必须建立在同级别分解之上，不能把局部波动直接当成完整走势类型。
- 趋势与盘整必须通过中枢关系解释，不能退化为“价格新高新低”或“指标强弱”判断。
- 背驰必须明确比较对象、最近中枢、离开方向和所属级别。
- 背驰后的去向只允许回到有限结构分支，不允许发明第四类解释。
- 当前工程输出仍主要是结构状态摘要，不应误读为严格递归分解已全部完成。

若后续需要改走势类型、盘整背驰、趋势背驰、节奏监视、背驰后去向等定义，优先修改 [trend-divergence-spec.md](trend-divergence-spec.md)。

## 15. 买卖点口径

本节已下沉到买卖点与多级别联立专题文档，主入口只保留摘要和跳转。

对应专题：

- [buy-sell-multi-level-spec.md](buy-sell-multi-level-spec.md): 一二三类买卖点、区间套、小转大、多级别联立。
- [zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md): 买卖点主辅消费红线。

本节仅保留以下历史摘要：

- 一二三类买卖点都必须依附最近中枢和走势类型，不能脱离结构孤立定义。
- 一类点强调背驰导致的转折，二类点强调转折后的第一次确认性回抽，三类点强调离开中枢后的首次不回归确认。
- 所有买卖点都必须显式声明所属级别与最近中枢关系。
- 区间套只负责时机精度，小转大必须先有低级别转折，再有高级别结构吸收确认。
- `lei_zhongshus` 只能给辅助提示，不得单独升级为确认买卖点。

若后续需要改 1/2/3 类买卖点、区间套、小转大或多级别联立定义，优先修改 [buy-sell-multi-level-spec.md](buy-sell-multi-level-spec.md)。

补充边界：

- 判定级别与执行级别必须区分；执行级别可低于判定级别，但不得高于判定级别。
- 若执行级别低于判定级别，输出中应显式说明这是低一级执行信号。
- 买卖点主辅消费红线和 3B/3S 首次回抽硬约束，统一由专题文档维护，不再在主入口重复展开。

## 16. 输出与解释要求

所有识别结果都必须支持解释性输出，但字段细节不再在主入口展开。

历史摘要：

- 分型、笔、中枢、走势类型、买卖点都应具备可追溯的结构证据字段。
- 标准中枢与类中枢必须拆分输出，不得混在同一列表中。
- 图表与报告必须显式区分中枢主结论和类中枢辅助结论。
- 对外结论默认引用主口径；若引用辅助口径，必须显式标为辅助。

输出字段和消费契约的详细定义，优先参考：

- [../analysis/combined-analysis-output-spec.md](../analysis/combined-analysis-output-spec.md)
- [zhongshu-dual-track-spec.md](zhongshu-dual-track-spec.md)

## 17. 测试口径

实现时必须为每个核心层级准备可复现样例。

历史摘要：

- 基础结构层至少覆盖包含关系、分型、成笔与替换。
- 上层结构至少覆盖线段、中枢、走势类型边界和买卖点高风险样例。
- 新口径进入主链路前，必须先有回归样例，再谈默认化。

## 18. 第一阶段不做的事情

为了控制复杂度，以下内容暂不进入 v0.1：

- 实盘交易接口
- 自动下单
- 多市场统一抽象
- 机器学习打分
- 复杂择时组合

## 19. 下一步实现顺序

本节保留为历史路线摘要。

建议顺序仍然是：

1. 先稳定基础结构。
2. 再稳定线段和中枢主路径。
3. 再推进走势类型、背驰、买卖点、多级别联立。
4. 最后统一输出字段和消费端展示。

具体待办与完成度看 [chanlun-spec-tasks.md](chanlun-spec-tasks.md)。

## 20. 当前版本结论

这份主入口的当前角色已经从“第一版工程总规则正文”收敛为“规格目录页 + 历史摘要页”。

当前核心目标是：

- 先统一标准
- 先跑通主链路
- 先让结果可解释
- 再逐步逼近更复杂的缠论流派细节

后续如果要提高精度，应优先通过模块 spec、测试样例和对比图复盘来修正规则，而不是再把细节堆回主入口。