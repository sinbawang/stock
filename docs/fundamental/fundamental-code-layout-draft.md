# 基本面代码目录说明

这份文档用于把前面的“字段文档、配置文档、Python 数据模型文档”进一步收敛到当前仓库已经落地的目录结构，回答一个更工程化的问题：

- 当前 `src/fundamental/` 已经怎么拆？
- 哪些目录和文件已经属于稳定闭环？
- 模型、配置、校验、评分、报告之间的依赖关系当前如何保持清晰？

这份文档现在更适合作为“当前实现结构说明 + 后续扩展边界”，而不再只是开工前的目录草案。

如果阅读过程中需要回到总导航，见 [fundamental-doc-map.md](fundamental-doc-map.md)。

这份文档适合放在“对象、字段、配置和数据源边界都已经冻结”之后阅读。建议前置阅读：

- [fundamental-module-spec.md](fundamental-module-spec.md)
- [fundamental-v1-minimum-fields.md](fundamental-v1-minimum-fields.md)
- [fundamental-data-source.md](fundamental-data-source.md)
- [fundamental-python-model.md](fundamental-python-model.md)
- [fundamental-submodel-config.md](fundamental-submodel-config.md)

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

## 3. 当前目录快照

当前仓库里的 `src/fundamental/` 目录已经大体落成如下结构：

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
    │   ├── blended.py
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
    │   ├── brief_report.py
    │   └── text_report.py
    └── services/
        ├── __init__.py
        ├── analyze_snapshot.py
        ├── fetch_and_analyze_cn_blended.py
        ├── fetch_and_analyze_hk_snapshot.py
        ├── fetch_and_analyze_cn_snapshot.py
        ├── fetch_and_analyze_hk_blended.py
        ├── manual_supplement_helpers.py
        ├── manual_supplement_loader.py
        └── source_warning_helpers.py
```

和最初草案相比，当前实现有几处已经明确固定下来：

- `models/` 已不只包含单期输入输出对象，也已经包含 blended 跨期对象 `blended.py`
- `services/` 已不只包含单期 HK/CN 入口，也已经包含 HK/CN blended 服务、manual supplement helper 和 source warning helper
- `reporting/` 已不只包含 `text_report.py`，还已经拆出 `brief_report.py` 承接 brief 文本与 blended brief 落盘
- `config/registry.py` 当前已经统一注册科技、金融和非金融扩展行业桶，而不再只是科技子模型注册表
- 原先草案里的 `scoring/explain.py` 仍未单独拆出，解释逻辑当前主要收敛在评分引擎与报告渲染层

## 4. 每层职责定义

### 4.1 `models/`

当前职责：

- 定义 `FundamentalSnapshot`
- 定义 `TriggeredRule`
- 定义 `FundamentalDimensionScore`
- 定义 `FundamentalScoreCard`
- 定义 `AnnualAnchorScore`、`InterimOverlayScore`、`BlendedFundamentalScoreCard`

当前文件：

- `blended.py`: 跨报告期 blended 评分对象
- `common.py`: `MarketCode`、`GuidanceAttainment`、`DupontDriver` 等基础类型
- `snapshot.py`: 输入快照模型
- `scorecard.py`: 输出结果模型

这一层不应负责：

- 子模型字段是否齐全
- 怎么打分
- 哪条红线命中

### 4.2 `config/`

当前职责：

- 定义 `DimensionConfig`、`FieldPolicy`、`RiskRuleConfig`、`SubmodelConfig`
- 注册各行业子模型
- 维护 `SUBMODEL_REGISTRY`

当前文件：

- `models.py`: 配置对象定义
- `registry.py`: 注册表和查询入口
- `tech_submodels.py`: 平台互联网、半导体、工业自动化、游戏内容等科技子模型
- `finance_submodels.py`: 银行、保险、券商子模型
- `nonfinancial_submodels.py`: 公用事业、数字基础设施、家电消费制造、汽车制造、能源资源等扩展行业桶

这一层不应负责：

- 真正执行评分
- 解析输入 JSON

### 4.3 `validation/`

当前职责：

- 按 `FieldPolicy` 校验快照是否可进入当前子模型评分
- 输出缺失字段列表
- 明确区分 `required_core`、`optional_manual`、`deferred_v2`

建议文件：

- `snapshot_validator.py`

这一层单独拆出来的原因是：

- 避免把字段校验写死在 `Pydantic` 模型里
- 避免把字段校验散落在评分函数内部

### 4.4 `scoring/`

当前职责：

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

当前职责：

- 把 `FundamentalScoreCard` 渲染成文本摘要
- 把 `BlendedFundamentalScoreCard` 渲染成 blended 评分卡和 brief
- 后续可以继续扩 CSV、Markdown、微信消息文本

当前关键文件：

- `text_report.py`
- `brief_report.py`

### 4.6 `services/`

当前职责：

- 提供“从快照到结果”的统一调用入口
- 让 CLI、脚本、后续联合分析优先调服务层，而不是直接拼散落脚本逻辑
- 承接 manual supplement、字段来源警告和 blended 调度逻辑

当前关键文件：

- `analyze_snapshot.py`
- `fetch_and_analyze_hk_snapshot.py`
- `fetch_and_analyze_cn_snapshot.py`
- `fetch_and_analyze_hk_blended.py`
- `fetch_and_analyze_cn_blended.py`
- `manual_supplement_helpers.py`
- `manual_supplement_loader.py`
- `source_warning_helpers.py`

建议它负责串起：

1. 读取或接收 `FundamentalSnapshot`
2. 加载 `SubmodelConfig`
3. 运行字段校验
4. 运行评分引擎
5. 返回 `FundamentalScoreCard`

### 4.7 `data/`

当前职责：

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

## 5. 当前最小可运行闭环

虽然最初是按“第一版最小闭环”来设计，但按当前仓库状态，下面这些层已经属于稳定可运行闭环：

- `data/`: HK/CN 快照抓取与 period snapshot 抓取
- `models/`: 单期与 blended 输入输出对象
- `config/`: 子模型配置与注册表
- `validation/`: 字段完整性校验
- `scoring/`: 通用评分与风险规则
- `reporting/`: 单期 / blended 文本报告与 brief 落盘
- `services/`: 单期 / blended 统一服务入口

如果按“当前仓库已经落地的最小闭环”来描述，更准确的说法是：

- `reporting/text_report.py` 已经属于第一版闭环的一部分
- `reporting/brief_report.py` 与 `models/blended.py` 也已经进入当前闭环，而不再是后续候选层
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
- [fundamental-python-model.md](fundamental-python-model.md) -> `src/fundamental/models/`
- [fundamental-submodel-config.md](fundamental-submodel-config.md) -> `src/fundamental/config/`
- [fundamental-tech-submodels.md](fundamental-tech-submodels.md) -> `src/fundamental/config/tech_submodels.py`
- [fundamental-module-spec.md](fundamental-module-spec.md) -> `src/fundamental/scoring/`、`src/fundamental/models/`、`src/fundamental/services/` 的总边界

## 8. 后续扩展顺序建议

当前最小闭环已经落地，因此后续更值得推进的顺序是：

1. 扩展更多行业桶与更多 live 字段到现有 `config/` 和 `data/`
2. 继续完善 blended 服务与报告链路
3. 视复杂度决定是否把解释逻辑从 `scoring/` 与 `reporting/` 里再拆层
4. 再考虑更细的 CLI / 批量导出接口沉淀

这样做的原因是：基础骨架已经成型，当前更重要的是在既有分层内扩能力，而不是再改目录骨架。

## 9. 当前结论

如果只说结论：

- `src/fundamental/` 已经作为与 `src/chanlun/` 平级的包落地
- 第一版核心分层已经形成：`models`、`config`、`validation`、`scoring`、`reporting`、`services`
- `reporting/` 已经属于当前闭环的一部分，不再只是第二步候选层
- 后续继续扩展时，仍应坚持“宽口径快照 + 配置化校验 + 通用引擎”的结构