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

- [docs/fundamental-module-spec.md](docs/fundamental-module-spec.md): 模块目标、边界、输入输出和总骨架
- [docs/fundamental-industry-layering.md](docs/fundamental-industry-layering.md): 行业分层方式，以及哪些行业共享主模型
- [docs/fundamental-tech-submodels.md](docs/fundamental-tech-submodels.md): 科技行业子模型的业务差异和关注点

读完这一层后，应该已经能回答：

- 为什么要有 `FundamentalSnapshot`
- 为什么基本面和缠论技术面是平级模块
- 为什么不同科技子行业不能完全共用同一套字段要求和解释话术

## 2. 字段与数据源

再看这组文档，目的是明确“第一版到底支持哪些字段，以及这些字段从哪里来”。

- [docs/fundamental-v1-minimum-fields.md](docs/fundamental-v1-minimum-fields.md): 第一版字段边界，哪些必需、哪些可放宽、哪些推迟到 v2
- [docs/fundamental-data-source.md](docs/fundamental-data-source.md): 港股 / A 股公开数据源如何映射成标准快照
- [docs/hk-minute-data-source.md](docs/hk-minute-data-source.md): 技术面侧港股分钟线抓取策略，供联合分析链路参考

读完这一层后，应该已经能回答：

- 第一版评分引擎最小依赖哪些字段
- 港股和 A 股快照分别走哪些公共抓取入口
- 哪些字段来自主源，哪些字段允许 overlay

## 3. 模型与实现草案

再看这组文档，目的是把规则落成更接近代码的对象与目录设计。

- [docs/fundamental-python-model-draft.md](docs/fundamental-python-model-draft.md): `FundamentalSnapshot` / `FundamentalScoreCard` 等对象如何表达
- [docs/fundamental-tech-config-draft.md](docs/fundamental-tech-config-draft.md): 子模型配置对象如何表达字段策略、维度、风险规则和解释文案
- [docs/fundamental-code-layout-draft.md](docs/fundamental-code-layout-draft.md): `src/fundamental/` 目录应该如何拆分

读完这一层后，应该已经能回答：

- 宽口径快照为什么不直接把所有字段写成必填
- 子模型规则为什么优先配置化
- 数据、校验、评分、报告、服务为什么要分层

## 4. 路线图与样例

最后看这组文档，目的是确认落地顺序和具体输入样子。

- [docs/fundamental-roadmap.md](docs/fundamental-roadmap.md): 实现优先级和阶段目标
- [docs/fundamental-snapshot-example.md](docs/fundamental-snapshot-example.md): 标准输入样例

读完这一层后，应该已经能回答：

- 当前应该先写什么，后写什么
- 一份标准化快照输入大致长什么样

## 当前推荐阅读路径

如果只走一条最短主线，建议按这个顺序：

1. [docs/fundamental-module-spec.md](docs/fundamental-module-spec.md)
2. [docs/fundamental-v1-minimum-fields.md](docs/fundamental-v1-minimum-fields.md)
3. [docs/fundamental-data-source.md](docs/fundamental-data-source.md)
4. [docs/fundamental-python-model-draft.md](docs/fundamental-python-model-draft.md)
5. [docs/fundamental-tech-config-draft.md](docs/fundamental-tech-config-draft.md)
6. [docs/fundamental-code-layout-draft.md](docs/fundamental-code-layout-draft.md)
7. [docs/fundamental-roadmap.md](docs/fundamental-roadmap.md)

## 对照当前代码

如果阅读文档后要回到现有实现，可以优先对照这些目录：

- [src/fundamental/data](c:/sinba/stock/src/fundamental/data): 公共数据源抓取与快照映射
- [src/fundamental/models](c:/sinba/stock/src/fundamental/models): 输入输出模型
- [src/fundamental/config](c:/sinba/stock/src/fundamental/config): 子模型配置与注册表
- [src/fundamental/scoring](c:/sinba/stock/src/fundamental/scoring): 评分规则与风险规则
- [src/fundamental/reporting](c:/sinba/stock/src/fundamental/reporting): 文本报告渲染
- [src/fundamental/services](c:/sinba/stock/src/fundamental/services): 抓取并分析的服务入口