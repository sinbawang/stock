# 基本面文档导航图

这份文档不定义新的业务规则，只负责回答一件事：

- 基本面相关文档现在应该按什么顺序阅读

如果只想快速进入主线，建议按下面四层阅读：

1. 概念与边界
2. 字段与数据源
3. 模型与实现草案
4. 路线图与样例

## 1. 概念与边界

先看这组文档，目的是明确“基本面模块到底要做什么，不做什么”。

- [fundamental-module-spec.md](fundamental-module-spec.md): 模块目标、边界、输入输出和总骨架
- [fundamental-industry-layering.md](fundamental-industry-layering.md): 行业分层方式，以及哪些行业共享主模型
- [fundamental-tech-submodels.md](fundamental-tech-submodels.md): 科技行业子模型的业务差异和关注点
- [fundamental-interim-scoring-design.md](fundamental-interim-scoring-design.md): 年报锚定 + 季报刷新评分的方案边界与总体设计

读完这一层后，应该已经能回答：

- 为什么要有 `FundamentalSnapshot`
- 为什么基本面和缠论技术面是平级模块
- 为什么不同科技子行业不能完全共用同一套字段要求和解释话术

结合当前实现状态，这一层还应帮助你快速确认：

- 金融、科技之外，公用事业与新能源运营、数字基础设施、家电消费制造也已经形成独立行业桶
- 中国电信 H 股、长江电力、太阳能、格力电器、中航科工当前分别落在哪个子模型或扩展观察组

## 2. 字段与数据源

再看这组文档，目的是明确“第一版到底支持哪些字段，以及这些字段从哪里来”。

- [fundamental-v1-minimum-fields.md](fundamental-v1-minimum-fields.md): 第一版字段边界，哪些必需、哪些可放宽、哪些推迟到 v2
- [fundamental-data-source.md](fundamental-data-source.md): 港股 / A 股公开数据源如何映射成标准快照
- [hk-financial-second-source-plan.md](hk-financial-second-source-plan.md): 港股保险 / 券商第二数据源方案，解释当前 public source 缺口和后续接入顺序
- [hk-minute-data-source.md](hk-minute-data-source.md): 技术面侧港股分钟线抓取策略，供联合分析链路参考

读完这一层后，应该已经能回答：

- 第一版评分引擎最小依赖哪些字段
- 港股和 A 股快照分别走哪些公共抓取入口
- 哪些字段来自主源，哪些字段允许 overlay
- 哪些港股金融字段当前来自官方披露 fallback，哪些仍来自 `manual supplement`

## 3. 模型与实现草案

再看这组文档，目的是把规则落成更接近代码的对象与目录设计。

- [fundamental-python-model-draft.md](fundamental-python-model-draft.md): `FundamentalSnapshot` / `FundamentalScoreCard` 等对象如何表达
- [fundamental-tech-config-draft.md](fundamental-tech-config-draft.md): 子模型配置对象如何表达字段策略、维度、风险规则和解释文案
- [fundamental-code-layout-draft.md](fundamental-code-layout-draft.md): `src/fundamental/` 目录应该如何拆分
- [fundamental-interim-scoring-interface.md](fundamental-interim-scoring-interface.md): 跨报告期加权评分需要新增哪些对象、服务接口和输出结构

读完这一层后，应该已经能回答：

- 宽口径快照为什么不直接把所有字段写成必填
- 子模型规则为什么优先配置化
- 数据、校验、评分、报告、服务为什么要分层
- 为什么报告层现在能直接输出“字段来源警告”和“维度得分计算说明”

补充说明：虽然 [fundamental-tech-config-draft.md](fundamental-tech-config-draft.md) 的名字仍保留“tech”，但当前它实际上已经能帮助理解跨行业注册表和配置对象结构。

## 4. 路线图与样例

最后看这组文档，目的是确认落地顺序和具体输入样子。

- [fundamental-roadmap.md](fundamental-roadmap.md): 实现优先级和阶段目标
- [fundamental-snapshot-example.md](fundamental-snapshot-example.md): 标准输入样例
- [combined-analysis-output-spec.md](combined-analysis-output-spec.md): 当前 `plus_60m` 联合文本与微信发送产物的输出规格
- [combined-analysis-service-interface.md](combined-analysis-service-interface.md): 当前联合分析链路应如何从脚本拼装收敛为公共服务接口
- [miniapp-cloud-publish-schema.md](miniapp-cloud-publish-schema.md): 面向微信小程序原生渲染的云存储发布层协议

读完这一层后，应该已经能回答：

- 当前应该先写什么，后写什么
- 一份标准化快照输入大致长什么样
- 当前联合分析文本为什么这样组织，以及哪些口径信息必须保留
- 当前联合分析为什么还没有完全沉到公共层，以及后续服务入口应该怎样拆

## 当前推荐阅读路径

如果只走一条最短主线，建议按这个顺序：

1. [fundamental-module-spec.md](fundamental-module-spec.md)
2. [fundamental-v1-minimum-fields.md](fundamental-v1-minimum-fields.md)
3. [fundamental-data-source.md](fundamental-data-source.md)
4. [fundamental-python-model-draft.md](fundamental-python-model-draft.md)
5. [fundamental-tech-config-draft.md](fundamental-tech-config-draft.md)
6. [fundamental-code-layout-draft.md](fundamental-code-layout-draft.md)
7. [fundamental-roadmap.md](fundamental-roadmap.md)
8. [fundamental-interim-scoring-design.md](fundamental-interim-scoring-design.md)
9. [fundamental-interim-scoring-interface.md](fundamental-interim-scoring-interface.md)
10. [combined-analysis-output-spec.md](combined-analysis-output-spec.md)
11. [combined-analysis-service-interface.md](combined-analysis-service-interface.md)
12. [miniapp-cloud-publish-schema.md](miniapp-cloud-publish-schema.md)

## 当前实现快照

如果只想先知道“现在已经做到哪里”，先看这几条：

- 行业桶已经覆盖：金融、科技、公用事业与新能源运营、数字基础设施、家电消费制造
- 行业桶已经覆盖：金融、科技、公用事业与新能源运营、数字基础设施、家电消费制造、能源资源
- 科技子模型已经覆盖：平台互联网、半导体与电子硬科技、工业自动化与智能装备、游戏与数字内容
- 金融子模型已经覆盖：银行、保险、券商
- 当前持仓相关映射里：长江电力与太阳能归入 `utility_operator_v1`，中国电信 H 股归入 `digital_infra_v1`，格力电器归入 `home_appliance_v1`，中航科工暂复用 `industrial_automation_v1`
- 当前代表标的映射里：长江电力与太阳能归入 `utility_operator_v1`，中国电信 H 股归入 `digital_infra_v1`，格力电器归入 `home_appliance_v1`，中航科工暂复用 `industrial_automation_v1`，中国神华挂接到 `energy_resource_v1`
- 港股与 A 股都已有公共快照抓取入口，并能进入统一评分与报告链路
- 港股金融 live 已有第一版 fallback 闭环，但仍保留部分 `manual supplement`
- 当前评分口径仍是“优先年报，缺年报才回退最新报告期”；季报加权评分目前仍处于文档规划阶段，见 [fundamental-interim-scoring-design.md](fundamental-interim-scoring-design.md)

如果想看更细的展开：

- 行业与标的归类看 [fundamental-industry-layering.md](fundamental-industry-layering.md)
- 当前进度与下一步优先级看 [fundamental-roadmap.md](fundamental-roadmap.md)
- 港股金融 live 细节看 [hk-financial-second-source-plan.md](hk-financial-second-source-plan.md)

## 对照当前代码

如果阅读文档后要回到现有实现，可以优先对照这些目录：

- [src/fundamental/data](c:/sinba/stock/src/fundamental/data): 公共数据源抓取与快照映射
- [src/fundamental/models](c:/sinba/stock/src/fundamental/models): 输入输出模型
- [src/fundamental/config](c:/sinba/stock/src/fundamental/config): 子模型配置与注册表
- [src/fundamental/scoring](c:/sinba/stock/src/fundamental/scoring): 评分规则与风险规则
- [src/fundamental/reporting](c:/sinba/stock/src/fundamental/reporting): 文本报告渲染
- [src/fundamental/services](c:/sinba/stock/src/fundamental/services): 抓取并分析的服务入口

结合 2026-05-11 之前后的实现状态，当前推荐额外关注两点：

- 如果想理解港股金融 live 是如何“部分闭环”的，优先看 [hk-financial-second-source-plan.md](hk-financial-second-source-plan.md)
- 如果想理解为什么报告里会出现字段来源警告和维度得分计算说明，优先对照 `services/fetch_and_analyze_hk_snapshot.py`、`scoring/base_engine.py` 与 `reporting/text_report.py`

当前如果只想快速确认最新行业桶落地状态，优先看上面的“当前实现快照”，再按需要跳转到对应专题文档。