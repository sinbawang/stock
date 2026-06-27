# 联合分析输出规格

这份文档只定义一件事：

- 当前“技术面 + 基本面”联合分析文本与产物，应该长什么样

如果要看这条链路后续应该暴露成什么公共服务入口、脚本层还应保留哪些职责，看 [combined-analysis-service-interface.md](combined-analysis-service-interface.md)。

它不重复定义基本面评分规则，也不重复定义缠论结构识别规则；这些分别看：

- [fundamental-module-spec.md](fundamental-module-spec.md)
- [chanlun-rule-spec.md](chanlun-rule-spec.md)

## 1. 当前适用范围

当前规格对应的是仓库里已经落地的 `plus_60m` 联合输出链路，主要由这些入口产出：

- [scripts/run_hk_60m_chanlun_report.py](c:/sinba/stock/scripts/run_hk_60m_chanlun_report.py)
- [scripts/run_cn_60m_chanlun_report.py](c:/sinba/stock/scripts/run_cn_60m_chanlun_report.py)

当前覆盖场景：

- 先生成 60M 缠论结构图与技术面观察文本
- 再拼接基本面评分文本
- 最终产出可直接发送到微信的联合文本与配图

当前不在这份规格里的内容：

- 交易执行
- 自动仓位管理
- 图形化 dashboard

当前新增的批量三轴总览由 [scripts/generate_a_share_combined_overview.py](../scripts/generate_a_share_combined_overview.py) 生成，负责把已有基本面简报、60M 技术面组合建议、资金面批量概览汇总为 A 股持仓三轴对照表；它不重新计算下层模型，只做组合层组织和口径提示。

批量三轴总览的分组口径：

- `confirming`: 至少两个维度支持，且没有明确弱项；若基本面和技术面同向但资金面中性，也归为可跟踪试仓。
- `watch`: 只有一个维度支持，其他维度暂未形成明确反向证据。
- `mixed`: 同时存在支持项和单一弱项，需要等待冲突缓解。
- `cautious`: 至少两个维度偏弱，或技术面与资金面同时偏弱；即便基本面较好，也优先按谨慎处理。
- `neutral`: 三轴都没有明确支持或弱项。

批量三轴总览优先输出“持仓管理清单”，在每行前置两个派生字段：

- `priority`: `P1-P5`，按 `confirming -> watch -> mixed -> neutral -> cautious` 排序，用于先看最值得跟踪和最需要控制的标的。
- `action`: 组合层动作标签，例如 `优先跟踪`、`跟踪试仓`、`等待触发`、`等待冲突缓解`、`暂停加仓`、`补齐数据`。

这两个字段只负责清单排序和阅读提示，不改变底层基本面、技术面、资金面的评分。

为方便每天扫读，`持仓管理清单` 再按 `priority` 拆成三个段落：

- `今日动作`: `P1`，三轴至少形成可跟踪试仓或更强确认，优先复核技术面触发位与风险线。
- `观察池`: `P2-P4`，包含等待触发、等待冲突缓解、数据尚不充分的标的。
- `风险池`: `P5`，至少两条轴偏弱或技术面与资金面双弱，默认暂停加仓，先等弱项缓解。

如果某个段落没有标的，保留段落标题并显示 `暂无`，避免日报结构随着样本变化而跳动。

港股持仓三段式概览由 [scripts/generate_h_share_combined_overview.py](../scripts/generate_h_share_combined_overview.py) 生成，默认读取 `data/stock_holdings.json`。它会优先读取最新 `group_h_share_capital_flow_overview_*.txt`；没有资金面概览时，`capital_flow` 必须显示 `missing/HK pending`；远端抓取失败时显示 `failed/primary` 或对应来源桶。当前 HK V1 资金面使用港股通成份行情的成交额/换手率、东方财富港股通个股成交榜历史中的个股南向净买额、沪深港通持股统计的 1 日南向持股市值变化，以及 HKEX 日终沽空成交额；沽空比例在成交额可用时用 `沽空成交额 / 成交额` 计算。个股南向净买额仅在标的进入成交榜的交易日可用，因此组合层可以把资金分真正用于 `confirming/mixed/cautious` 分组，但仍不能把单一公开资金源当作绝对真值。

## 2. 联合输出的目标

联合分析的目标不是把两份报告硬拼在一起，而是让用户一眼回答这几个问题：

- 当前标的基本面属于什么质量档位
- 当前 60M 结构处于什么位置
- 技术面和基本面是否互相支持
- 哪些地方需要特别注意口径风险或等待确认

因此当前输出设计遵循三个原则：

- 先给完整基本面判断，再给当前技术结构观察
- 保留基本面里的缺失项、警告、维度计算依据，不为“简洁”牺牲可解释性
- 技术面结论保持观察口径，不伪装成交易系统指令

## 3. 当前产物清单

一次完整的 `plus_60m` 联合分析，当前通常会产出两类东西。

当前仓库的统一报告目录约定为：

- 持仓清单：`data/stock_holdings.json`
- 单股报告：`data/reports/<symbol>/base.json`、`data/reports/<symbol>/fund.json`、`data/reports/<symbol>/overview.txt`
- 技术级别目录：`data/reports/<symbol>/day/`、`data/reports/<symbol>/60m/`、`data/reports/<symbol>/15m/`
- 级别分析 CSV：`data/reports/<symbol>/<timeframe>/analyze/*.csv`
- 级别结构图与技术报告：`data/reports/<symbol>/<timeframe>/structure.svg`、`data/reports/<symbol>/<timeframe>/tech.json`
- 组合级概览与 manifest：`data/reports/_meta/*.txt|*.json`

### 3.1 文本产物

- 一份联合分析 `.txt`
- 单股综合文本固定落在 `data/reports/<symbol>/overview.txt`
- 组合级概览文本通常落在 `data/reports/_meta`
- 文件名当前约定示例：
  - `01339_中国人保_insurance_v1_plus_60m_20260511_000149.txt`
  - `06886_华泰证券_broker_v1_plus_60m_20260511_000149.txt`

命名语义：

- `symbol`
- `name`
- `submodel`
- `plus_60m`
- 生成时间戳

### 3.2 图片产物

- 一张适合移动端阅读和发布层消费的 JPG 结构图
- 上游还会保留原始 CSV、标准化 CSV、SVG、PNG、中枢/笔/MACD 导出等中间文件
- 技术面图片和 `tech.json` 当前通常落在各标的自己的 `data/reports/<symbol>/<timeframe>/` 目录，分析 CSV 在其下的 `analyze/` 子目录

### 3.3 `tech.json` 当前字段协议

`tech.json` 当前是技术面产物的主 JSON 载体，但不同入口生成的字段并不完全一致。

因此当前应区分两层：

- 当前必备字段：各常用入口都应尽量保持一致，允许下游直接依赖
- 当前可选字段：只在部分入口存在，下游读取时必须按 optional 处理

当前建议视为必备的顶层字段：

- `report_type`: 固定为 `technical`
- `symbol`
- `name`
- `timeframe`
- `generated_at`
- `summary`
- `analysis_text`
- `advice_text`

当前常见但不能假定所有入口都存在的字段：

- `source`
- `artifacts`
- `stats`
- `precision_entry`
- `precision_window_display`

其中 `summary` 当前至少可能包含：

- `conclusion`
- `suggestion`

在较完整的生成入口中，`summary` 还可能包含：

- `operation_level`
- `buy_points`
- `sell_points`
- `signal_points`
- `signal_catalog`
- `precision_entry`
- `precision_window_display`

当前三轴 mixed 报告主链路里，`30m/tech.json` 已经稳定带出一组次级别区间套字段，用于表达“30M 主操作级别下的 5M 精确执行层”：

- 顶层 `precision_entry`
- 顶层 `precision_window_display`
- `summary.precision_entry`
- `summary.precision_window_display`

其中：

- `precision_entry` 表达 5M 执行层的状态、信号、背驰与绑定来源
- `precision_window_display` 是面向消费层的展示块，当前结构为 `{title, label, description, lines}`

当前 `precision_entry` 常见字段包括：

- `operation_level`: 当前为 `5M`
- `timeframe`: 当前为 `5m`
- `pending_reverse_mode`: 当前默认 `effective_only`
- `status`: `standby`、`watch`、`actionable`
- `note`
- `signal_descriptions`
- `window_basis_label`
- `window_basis_description`
- `nested_from`

当前 `nested_from` 常见字段包括：

- `side`
- `window_start_time`
- `window_end_time`
- `window_basis`
- `window_basis_label`
- `window_basis_description`
- `anchor_time`
- `related_zs_id`
- `exit_bi_id`
- `zs_is_terminated`
- `trigger`

因此当前读取规则应是：

- 联合文本和小程序发布层可以稳定依赖 `summary.conclusion`、`summary.suggestion`、`analysis_text`、`advice_text`
- 对 `source`、`artifacts`、`stats` 与更细的 `summary` 字段，必须按“有则用、无则降级”处理
- 对 `precision_entry` 与 `precision_window_display`，当前可在 mixed 报告主链路中稳定依赖，但在其他旧入口仍应按 optional 处理

### 3.4 `tech.json` 建议新增的走势结构状态字段

根据 [chanlun-rule-spec.md](chanlun-rule-spec.md) 中新增的走势类型口径，后续 `tech.json` 建议补一组结构化字段，用来表达“上一个已完成走势类型”和“当前正在进行走势类型”。

这组字段当前还不是已落地事实，因此本节只定义推荐协议，不应在文档或代码里假装它已经普遍存在。

建议新增：

- `structure_state.last_completed`
- `structure_state.current_ongoing`
- `structure_state.relationship`

建议 `structure_state.last_completed` 至少包含：

- `type`: `up`、`down`、`range`
- `zs_count`: 已完成走势类型包含的中枢数量
- `start_ts`
- `end_ts`
- `confirmation_basis`: 例如 `confirmed_by_same_level_completion`

建议 `structure_state.current_ongoing` 至少包含：

- `type`: `up`、`down`、`range`、`unknown`
- `status`: `ongoing`、`extending`、`candidate_completion`
- `start_ts`
- `latest_ts`
- `zs_count_so_far`
- `confirmation_basis`: 例如 `still_inside_last_zs_extension`、`forming_next_same_level_zs`

建议 `structure_state.relationship` 至少包含：

- `kind`: `same_type_extension`、`completed_then_new_type_ongoing`、`undetermined`
- `note`: 面向解释层的短句说明

兼容性要求：

- 这组新增字段只能做增量扩展，不能替代现有 `analysis_text`
- 现有依赖 `analysis_text` 分段抽取的下游入口，必须继续可用
- 在所有主入口统一补齐前，不要把这些字段提升为“读取必需项”

## 4. 文本结构规格

当前联合文本按下面顺序组织：

1. 联合标题与元信息
2. 基本面区块
3. 技术面区块
4. 技术面操作建议区块

### 4.1 联合标题与元信息

当前建议至少包含：

- 标的名称
- 代码
- 联合分析标识
- 子模型信息或版本标识
- 生成时间
- 技术面分钟级别
- 技术面数据源

当前实盘样式示例：

```text
【中国人保 01339 最新联合分析（insurance_v1 手工补充版）】
生成时间：2026-05-11 00:01
技术面数据源：xueqiu
```

如果当前报告包含明显的人工补充成分，标题里可以直接暴露“手工补充版”；不要把口径风险藏进正文深处。

### 4.2 基本面区块

基本面区块当前直接复用 `render_scorecard_text(...)` 的输出风格，建议至少包含：

- 公司名、代码、行业层、子模型、报告期
- 总分、评级、红线状态
- 关注问题
- 维度得分
- 优势
- 风险或警告
- 综合说明

如果当前实现能拿到这些附加信息，也应保留：

- 缺失指标
- 关键假设
- 来源相关警告

当前有两条必须保留的可解释信息：

- `警告`：用于解释 `official.solvency_report`、`official.annual_report_proxy`、`manual.supplement` 等字段来源口径
- `计算:`：用于解释维度得分是如何由字段值映射到规则分，再汇总到维度分

当前维度得分说明格式示例：

```text
- 资本安全与资产质量: 28.80/30.00
  计算: 平均[综合偿付能力充足率 249.90->100.0, 综合成本率 97.60->92.0]=96.0; ×30/100=28.80
```

设计要求：

- 说明必须短，优先可扫读
- 但必须能让用户看出“字段值 -> 规则分 -> 维度分”这条链路
- 不要为了精简而删掉口径警告

### 4.3 技术面区块

技术面区块当前由 60M 缠论观察文本构成，建议至少包含：

- 观察标题
- 概览
- 结构
- 信号
- 观察重点

其中“结构”段在后续应向 [chanlun-rule-spec.md](chanlun-rule-spec.md) 的走势类型输出要求对齐，至少逐步补齐：

- 上一个已经完成的同级别走势类型
- 当前正在进行的同级别走势类型
- 当前结构更接近“同一走势类型内部延伸”还是“前一走势完成后的新类型进行中”

当前实盘结构示例：

```text
【中国人保 60M 缠论观察】

概览：
- 时间区间：2026-01-02 10:30 到 2026-05-08 16:00
- K线数量：共 501 根 60M K线
- 中枢数量：当前识别到 3 个中枢

结构：
- 最新确认向上笔：...
- 最新确认向下笔：...

信号：
- 顶背驰：无
- 底背驰：无
- 买点：当前无确认一二三类买点
- 卖点：当前无确认一二三类卖点
```

上述示例代表当前已落地文本，不代表目标上限。后续推荐把“结构”段扩成类似：

```text
结构：
- 上一个已完成走势类型：下跌，含 2 个同级别中枢，结束于 05-29 16:00
- 当前正在进行走势类型：盘整进行中，当前仍围绕最新中枢延伸
- 当前阶段判断：更接近同一走势类型内部扩展，尚未确认新趋势完成
- 最新确认向上笔：...
- 未确认向下笔：...
```

这样做的目的不是增加术语密度，而是让文本和结构图能明确回答两个问题：

- 已完成的同级别走势类型到底是哪一段
- 当前用户面对的，到底是“已完成结构后的新连接”，还是“原走势尚未完成的延续”

当前技术面文本强调的是“结构观察”，不是“强制买卖指令”。

### 4.4 技术面操作建议区块

当前联合文本通常还会追加一个更短的收束段，建议包含：

- 结论
- 理由
- 建议
- 风险说明

当前实盘样式示例：

```text
【中国人保 60M 操作建议】
结论：偏弱，先观望。
理由：价格仍在最新中枢下沿 5.33 下方。
建议：等待重新站回 5.33-5.67 再考虑参与，未站回前不追。
说明：以上仅基于缠论结构与 MACD 强弱，不构成投资建议。
```

## 5. 当前字段边界

当前联合分析文本不是新的领域模型，而是把两个已有输出按可读顺序组合起来：

- 基本面部分依赖 `FundamentalScoreCard`
- 技术面部分依赖 60M 缠论结构分析结果

因此当前最关键的边界是：

- 不要在联合层重新计算基本面总分
- 不要在联合层重新发明技术面信号命名
- 联合层负责的是“组织、解释、提示冲突”，不是重做下层分析
- 在技术面 JSON 还未统一补齐结构状态字段前，不要让联合层自行猜测“已完成走势类型 / 正在进行走势类型”

## 6. 当前口径要求

联合分析当前必须显式保留以下口径信息：

- 基本面报告期，例如 `2025-12-31`
- 技术面观察时间区间
- 技术面数据源，例如 `xueqiu`
- 若使用官方披露 fallback 或手工补充，必须在 `警告` 段说明

原因很直接：

- 基本面和技术面本来就不是同一时间尺度
- 港股金融当前还存在官方披露与手工补充混用的情况
- 如果不把时间和来源写明，联合文本会制造虚假的“完全同口径”错觉

## 7. 当前推荐组合规则

当前联合文本层面，建议按下面方式组合：

- 先完整输出基本面，再输出技术面
- 如果基本面存在明显来源警告，不要在末尾操作建议里忽略它
- 如果技术面只是震荡或未确认状态，结论应偏观察而不是强动作
- 如果未来要补 `combined_comment`，也应建立在现有两个区块都完整保留的前提下

换句话说，当前仓库里“联合分析”更接近：

- 一份有顺序、有口径说明的组合报告

而不是：

- 一个把所有判断压缩成单句结论的黑盒信号

## 8. 当前文件与发布约定

当前桌面微信发送链路已经移除，联合分析输出约定回收到 canonical 报告目录与 CloudBase 发布层：

- 文本与技术面 JSON 保持可直接落盘、可直接打包
- 结构图 JPG 保持适合移动端查看
- 文件名与目录便于后续回溯、重建和发布

## 9. 当前已知限制

截至 2026-05-11，这条链路仍有这些限制：

- 港股保险 `insurance_v1` 的部分字段仍依赖 `manual supplement`
- 港股券商 `broker_v1` 的 `net_capital_ratio` 当前仍可能是官方年报代理映射值
- 联合文本里虽然已经有“警告”与“计算”，但还没有单独的 machine-readable 联合结果模型文档
- A 股与港股当前都以 60M 观察为主，尚未扩到统一的多周期联合输出规范

因此这份规格描述的是“当前可交付版本”，不是最终形态。

## 10. 后续扩展建议

如果继续往下做，优先级建议是：

1. 为联合分析增加独立的结构化结果模型，而不只是一段文本
2. 让末尾的“操作建议”明确引用前文的技术/基本面触发条件
3. 把当前 `plus_60m` 文本生成逻辑进一步收口到公共服务层，减少脚本侧拼装
4. 再决定是否要扩展到日线、周线或批量输出格式