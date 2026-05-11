# 基本面代码目录草案 v0.1

这份文档用于把前面的“字段文档、配置文档、Python 数据模型文档”继续往前推进一步，回答一个更工程化的问题：

- 如果正式开始写代码，`src/fundamental/` 应该怎么拆？
- 哪些文件第一版必须有？
- 模型、配置、校验、评分、报告之间的依赖关系如何保持清晰？

这份文档仍然是设计文档，不要求现在就创建目录或文件。

如果阅读过程中需要回到总导航，见 [fundamental-doc-map.md](fundamental-doc-map.md)。

这份文档适合放在“对象、字段、配置和数据源边界都已经冻结”之后阅读。建议前置阅读：

- [fundamental-module-spec.md](fundamental-module-spec.md)
- [fundamental-v1-minimum-fields.md](fundamental-v1-minimum-fields.md)
- [fundamental-data-source.md](fundamental-data-source.md)
- [fundamental-python-model-draft.md](fundamental-python-model-draft.md)
- [fundamental-tech-config-draft.md](fundamental-tech-config-draft.md)

如果从这份文档继续往后走，下一步通常是：

- 对照当前实现检查目录是否一致
- 回到 [fundamental-roadmap.md](fundamental-roadmap.md) 排实现顺序

## 1. 当前判断

当前仓库里的 [src/chanlun](c:/sinba/stock/src/chanlun) 目前只承载技术面逻辑，这和你的建议是一致的：`chanlun` 应该继续保持为技术面模块，而基本面应单独放在 `src/fundamental/`。

这反而是好事，因为可以在真正开工前先把边界定干净，避免一开始就把：

- 数据模型
- 配置对象
- 校验逻辑
- 评分规则
- 报告输出

全部揉进一个脚本里。

## 2. 目录设计原则

建议后续基本面代码目录遵循四条原则：

- 输入输出模型和评分逻辑分离
- 通用评分引擎和子模型配置分离
- 子模型规则优先配置化，不优先写成一堆分叉类
- 第一版只建最小闭环，不提前铺太多占位空文件

另外再补一条架构原则：

- `chanlun` 和 `fundamental` 在 `src/` 下应是平级目录，不应让基本面依附在技术面包内部

## 3. 第一版推荐目录

建议第一版正式实现时，把目录落成这样：

```text
src/
├── chanlun/
│   └── ...
└── fundamental/
    ├── __init__.py
    ├── data/
    │   ├── __init__.py
    │   ├── hk_snapshot_fetcher.py
    │   └── cn_snapshot_fetcher.py
    ├── models/
    │   ├── __init__.py
    │   ├── common.py
    │   ├── snapshot.py
    │   └── scorecard.py
    ├── config/
    │   ├── __init__.py
    │   ├── models.py
    │   ├── registry.py
    │   ├── tech_submodels.py
    │   ├── finance_submodels.py
    │   └── nonfinancial_submodels.py
    ├── validation/
    │   ├── __init__.py
    │   └── snapshot_validator.py
    ├── scoring/
    │   ├── __init__.py
    │   ├── base_engine.py
    │   ├── common_rules.py
    │   ├── risk_rules.py
    ├── reporting/
    │   ├── __init__.py
    │   └── text_report.py
    └── services/
        ├── __init__.py
        ├── analyze_snapshot.py
        ├── fetch_and_analyze_hk_snapshot.py
        └── fetch_and_analyze_cn_snapshot.py
```

按当前仓库实现看，这个目录已经基本落地，和最初草案相比有三个明确变化：

- `data/` 已经同时包含港股和 A 股快照抓取入口，而不再只覆盖 `hk_snapshot_fetcher.py`
- `services/` 已经同时包含 `fetch_and_analyze_hk_snapshot.py` 与 `fetch_and_analyze_cn_snapshot.py`
- `reporting/text_report.py` 已经落地，而原先草案里的 `scoring/explain.py` 暂未单独拆出，解释逻辑当前主要留在评分引擎与报告渲染层

## 4. 每层职责定义

### 4.1 `models/`

建议职责：

- 定义 `FundamentalSnapshot`
- 定义 `TriggeredRule`
- 定义 `FundamentalDimensionScore`
- 定义 `FundamentalScoreCard`

建议文件：

- `common.py`: `MarketCode`、`GuidanceAttainment`、`DupontDriver` 等基础类型
- `snapshot.py`: 输入快照模型
- `scorecard.py`: 输出结果模型

这一层不应负责：

- 子模型字段是否齐全
- 怎么打分
- 哪条红线命中

### 4.2 `config/`

建议职责：

- 定义 `DimensionConfig`、`FieldPolicy`、`RiskRuleConfig`、`SubmodelConfig`
- 注册各行业第一版子模型
- 维护 `SUBMODEL_REGISTRY`

建议文件：

- `models.py`: 配置对象定义
- `registry.py`: 注册表和查询入口
- `tech_submodels.py`: 平台互联网、半导体、工业自动化、游戏内容等科技子模型
- `finance_submodels.py`: 银行、保险、券商子模型
- `nonfinancial_submodels.py`: 公用事业、数字基础设施、家电消费制造等扩展行业桶

这一层不应负责：

- 真正执行评分
- 解析输入 JSON

### 4.3 `validation/`

建议职责：

- 按 `FieldPolicy` 校验快照是否可进入当前子模型评分
- 输出缺失字段列表
- 明确区分 `required_core`、`optional_manual`、`deferred_v2`

建议文件：

- `snapshot_validator.py`

这一层单独拆出来的原因是：

- 避免把字段校验写死在 `Pydantic` 模型里
- 避免把字段校验散落在评分函数内部

### 4.4 `scoring/`

建议职责：

- 聚合各维度得分
- 执行通用规则
- 执行自动化风险规则
- 生成维度级解释和全局解释材料

建议文件：

- `base_engine.py`: 通用评分主流程
- `common_rules.py`: 通用分维度规则
- `risk_rules.py`: 红线和风险提示逻辑

如果后续解释逻辑继续膨胀，再考虑单独拆出 `explain.py`。按当前实现，解释材料仍主要在
`base_engine.py` 和 `reporting/text_report.py` 中收敛。

这里建议坚持一个原则：

- 评分逻辑尽量调用配置
- 不要让 `base_engine.py` 直接写死“平台互联网就这样算、半导体就那样算”

### 4.5 `reporting/`

建议职责：

- 把 `FundamentalScoreCard` 渲染成文本摘要
- 后续可以扩 CSV、Markdown、微信消息文本

第一版建议先只建：

- `text_report.py`

### 4.6 `services/`

建议职责：

- 提供“从快照到结果”的统一调用入口
- 让 CLI、脚本、后续联合分析只调一个服务函数

建议文件：

- `analyze_snapshot.py`
- `fetch_and_analyze_hk_snapshot.py`
- `fetch_and_analyze_cn_snapshot.py`

建议它负责串起：

1. 读取或接收 `FundamentalSnapshot`
2. 加载 `SubmodelConfig`
3. 运行字段校验
4. 运行评分引擎
5. 返回 `FundamentalScoreCard`

### 4.7 `data/`

建议职责：

- 对接外部财务数据源
- 把原始源字段映射到标准 `FundamentalSnapshot`
- 输出抓取假设、代理字段说明和原始引用标识

建议文件：

- `hk_snapshot_fetcher.py`
- `cn_snapshot_fetcher.py`

这一层不应负责：

- 直接评分
- 直接决定最终评级
- 把数据源规则散落到 CLI 或临时脚本里

## 5. 第一版最小可运行子集

虽然上面给的是完整推荐目录，但第一版不必一次全部落地。

第一版最小闭环建议只先创建以下文件：

```text
src/fundamental/
├── __init__.py
├── data/
│   ├── __init__.py
│   ├── hk_snapshot_fetcher.py
│   └── cn_snapshot_fetcher.py
├── models/
│   ├── __init__.py
│   ├── common.py
│   ├── snapshot.py
│   └── scorecard.py
├── config/
│   ├── __init__.py
│   ├── models.py
│   ├── registry.py
│   └── tech_submodels.py
├── validation/
│   ├── __init__.py
│   └── snapshot_validator.py
├── scoring/
│   ├── __init__.py
│   ├── base_engine.py
│   ├── common_rules.py
│   └── risk_rules.py
├── reporting/
│   ├── __init__.py
│   └── text_report.py
└── services/
    ├── __init__.py
    ├── analyze_snapshot.py
    ├── fetch_and_analyze_hk_snapshot.py
    └── fetch_and_analyze_cn_snapshot.py
```

这意味着如果按“当前仓库已经落地的最小闭环”来描述，更准确的说法是：

- `reporting/text_report.py` 已经属于第一版闭环的一部分
- `scoring/explain.py` 仍然可以继续延后，等解释逻辑复杂到需要独立拆层时再新增

如果时间紧，解释逻辑继续放在 `base_engine.py` 和 `reporting/text_report.py` 也是合理的；是否单独拆出
`explain.py` 应由后续复杂度而不是先验目录洁癖来决定。

## 6. 推荐依赖方向

为了避免循环依赖，建议依赖方向固定为：

```text
models <- config <- validation <- services
models <- scoring <- services
models <- reporting <- services
```

更具体地说：

- `models/` 不依赖 `config/` 和 `scoring/`
- `config/` 可以依赖 `models/common.py` 中的公共类型，但不要反向依赖快照对象
- `validation/` 依赖 `models/` 和 `config/`
- `scoring/` 依赖 `models/` 和 `config/`
- `services/` 负责把它们串起来

最不建议出现的情况是：

- `snapshot.py` 里直接 import 某个科技子模型配置
- `tech_submodels.py` 里直接调用评分函数
- `base_engine.py` 反过来 import `services/`

## 7. 与现有文档的对应关系

为了后面真正实现时不迷路，建议把文档到代码的映射固定为：

- [fundamental-v1-minimum-fields.md](fundamental-v1-minimum-fields.md) -> `src/fundamental/validation/` 和 `src/fundamental/config/`
- [fundamental-python-model-draft.md](fundamental-python-model-draft.md) -> `src/fundamental/models/`
- [fundamental-tech-config-draft.md](fundamental-tech-config-draft.md) -> `src/fundamental/config/`
- [fundamental-tech-submodels.md](fundamental-tech-submodels.md) -> `src/fundamental/config/tech_submodels.py`
- [fundamental-module-spec.md](fundamental-module-spec.md) -> `src/fundamental/scoring/`、`src/fundamental/models/`、`src/fundamental/services/` 的总边界

## 8. 第一版建议实现顺序

如果后面下一步真的开始写代码，建议顺序是：

1. `models/common.py`
2. `models/snapshot.py`
3. `models/scorecard.py`
4. `config/models.py`
5. `config/tech_submodels.py`
6. `config/registry.py`
7. `validation/snapshot_validator.py`
8. `scoring/common_rules.py`
9. `scoring/risk_rules.py`
10. `scoring/base_engine.py`
11. `services/analyze_snapshot.py`

这样安排的原因是：

- 先固定输入输出对象
- 再固定配置对象
- 再做校验
- 最后实现引擎和总入口

## 9. 当前建议结论

如果只说结论：

- `src/fundamental/` 已经作为与 `src/chanlun/` 平级的包落地
- 第一版核心分层已经形成：`models`、`config`、`validation`、`scoring`、`reporting`、`services`
- `reporting/` 已经属于当前闭环的一部分，不再只是第二步候选层
- 后续继续扩展时，仍应坚持“宽口径快照 + 配置化校验 + 通用引擎”的结构