# Chanlun Stock Analysis

基于缠论的股票辅助分析工具，当前主线是先把技术面规则和基本面规则都定义清楚，再按文档分阶段实现。

项目定位是“研究与辅助决策工具”，不是自动荐股器，也不是收益承诺系统。

## 当前重点

当前项目分两条主线推进：

- 技术面：缠论结构识别、结构图导出、规则回归验证
- 基本面：财务快照模型、评分规则、风险标记、港股 / A 股公共抓取入口，以及与技术面联动的接口设计

当前已形成“文档定义口径 + 公共入口落地 + 测试回归”的基本闭环，后续新增能力继续优先遵循既有文档与公共入口。

截至 2026-05-11，基本面侧还补上了两个今天最值得注意的变化：

- 港股金融 second source 已进入部分 live 落地：
	- 华泰证券 `06886` 可通过官方年报 PDF fallback 补 `net_capital_ratio` 代理值
	- 中国人保 `01339` 可通过官网偿付能力披露 fallback 补 `solvency_adequacy_ratio`
- 基本面文本报告现在会额外输出：
	- 字段来源口径警告
	- 维度得分的简版计算说明

截至 2026-05-12，今天收尾后建议优先关注这几条新增变化：

- 非金融扩展行业桶已继续向持仓侧收敛：
	- `00175` 吉利汽车已接入 `auto_manufacturing_v1`
	- 该子模型当前强调盈利质量、现金流转化、渠道/周转效率，以及 `pe_percentile_5y + peg` 口径下的估值匹配
- 基本面快照已补齐一批派生字段：
	- `peg`
	- `net_margin`
	- `asset_turnover`
	- `equity_multiplier`
	- `dupont_driver`
- A 股快照当前默认优先最近一个 `12-31` 年报期；只有拿不到年报时才回退到最新报告期
- 港股快照当前也改成“优先年报，必要时显式回退到最新可用期”，并把 `period_type` 真实写入快照
- 文本简报对非年报口径现在会显式给出警告，避免把季报 / 中报结果直接与年报口径标的横向比较
- 港股金融补充字段当前也会优先对齐主快照的 `report_period`；匹配不到同报告期时才回退到最新指标期，并在 assumptions 里留下明确痕迹

## 文档索引

建议按“总边界 -> 字段边界 -> 数据源与实现 -> 联动扩展”的顺序阅读基本面文档。

- [docs/chanlun-rule-spec.md](docs/chanlun-rule-spec.md): 缠论规则规格
- [docs/capital-flow-module-spec.md](docs/capital-flow-module-spec.md): 资金面模块设计规格
- [docs/hk-minute-data-source.md](docs/hk-minute-data-source.md): 港股分钟线数据源策略与调用约定

基本面建议阅读顺序：

- [docs/fundamental-doc-map.md](docs/fundamental-doc-map.md): 基本面文档总导航，先看这份会更快进入主线
- [docs/fundamental-module-spec.md](docs/fundamental-module-spec.md): 先看模块目标、边界、输入输出和总骨架
- [docs/fundamental-v1-minimum-fields.md](docs/fundamental-v1-minimum-fields.md): 再看第一版必须支持哪些字段，哪些字段先放宽
- [docs/fundamental-industry-layering.md](docs/fundamental-industry-layering.md): 再看行业怎么分层，哪些行业共用主模型
- [docs/fundamental-tech-submodels.md](docs/fundamental-tech-submodels.md): 再看科技行业子模型的业务规则差异
- [docs/fundamental-data-source.md](docs/fundamental-data-source.md): 然后看标准快照如何从港股 / A 股公开数据源进入公共层
- [docs/fundamental-python-model-draft.md](docs/fundamental-python-model-draft.md): 然后看领域模型如何落到 Python 对象
- [docs/fundamental-tech-config-draft.md](docs/fundamental-tech-config-draft.md): 再看子模型配置对象如何表达评分与解释规则
- [docs/fundamental-code-layout-draft.md](docs/fundamental-code-layout-draft.md): 最后看代码目录怎么落地到 `src/fundamental/`

补充文档：

- [docs/fundamental-roadmap.md](docs/fundamental-roadmap.md): 基本面模块落地路线图
- [docs/fundamental-snapshot-example.md](docs/fundamental-snapshot-example.md): 基本面标准输入样例
- [docs/combined-analysis-output-spec.md](docs/combined-analysis-output-spec.md): 当前 `plus_60m` 联合文本与微信发送产物规格
- [docs/combined-analysis-service-interface.md](docs/combined-analysis-service-interface.md): 联合分析链路的公共服务接口说明
- [.github/agents/chanlun-python.agent.md](.github/agents/chanlun-python.agent.md): 项目专用 agent 定义

## 当前公共入口

当前建议直接复用这些公共入口，不要在脚本里重复拼源站请求：

- 港股分钟线: `chanlun.data.hk_minute_fetcher.fetch_hk_minute_with_policy(...)`
- 港股基本面快照: `fundamental.data.fetch_hk_fundamental_snapshot(...)`
- A 股基本面快照: `fundamental.data.fetch_cn_fundamental_snapshot(...)`
- 港股抓取并分析: `fundamental.services.fetch_and_analyze_hk_snapshot(...)`
- A 股抓取并分析: `fundamental.services.fetch_and_analyze_cn_snapshot(...)`
- 基本面简报落盘: `fundamental.reporting.save_fundamental_brief(...)`
- 纯文本评分卡落盘: `fundamental.reporting.save_scorecard_text(...)`

对应的数据源约定见：

- [docs/hk-minute-data-source.md](docs/hk-minute-data-source.md)
- [docs/fundamental-data-source.md](docs/fundamental-data-source.md)

## 基本面报告输出

当前脚本层已经同时支持两类文本产物：

- `fundamental_brief`: 面向用户阅读的简报，包含评级、维度结论、警告、补充说明
- `scorecard`: 更偏结构化的纯文本评分卡，保留维度打分、缺失字段和关键指标摘要

单标的生成示例：

```powershell
.\venv\Scripts\python.exe scripts/generate_fundamental_brief.py 601088 --name 中国神华 --save-scorecard-text
```

生成后的 `brief` 和 `scorecard` 文件名当前都会带上 `submodel_id`，便于同一标的在多子模型场景下直接区分产物。

如果希望把 scorecard 文本单独落到另一个目录：

```powershell
.\venv\Scripts\python.exe scripts/generate_fundamental_brief.py 03690 --name 美团 --market HK --quote-overlay-source xueqiu --save-scorecard-text --scorecard-output-dir data\_meta\scorecards
```

批量重生成为当前格式时，也可以一起输出 scorecard 文本：

```powershell
.\venv\Scripts\python.exe scripts/batch_regenerate_fundamental_briefs.py --meta-dir data\_meta --save-scorecard-text
```

如果要把已经生成好的文本报告发到当前已打开的微信会话，当前建议使用稳定的文本发送入口：

```powershell
.\venv\Scripts\python.exe scripts/send_wechat_current_chat_text.py data\_meta\02208_金风科技_industrial_automation_v1_blended_fundamental_brief_20260518_203254.txt
```

使用前先手动打开目标微信群或联系人会话。该入口默认只向当前会话发送文本文件，不执行自动搜索切换，也不依赖附件发送链路。

如果要把已经生成好的结构图或其他文件发到当前已打开的微信会话，当前建议使用对应的文件发送入口：

```powershell
.\venv\Scripts\python.exe scripts/send_wechat_current_chat_files.py build\wechat\data\02208_金风科技\60m\02208_60m_20260109_to_20260518_normalized_with_boxes_wechat.jpg
```

该入口同样要求先手动打开目标会话；发送后会检查当前会话消息列表是否发生变化，避免“命令成功但微信未收到”的静默失败。

如果要一次发送“文本报告 + 一张或多张图”，当前建议使用组合发送入口：

```powershell
.\venv\Scripts\python.exe scripts/send_wechat_current_chat_bundle.py --message-file data\_meta\02208_金风科技_industrial_automation_v1_blended_fundamental_brief_20260518_203254.txt --file build\wechat\data\02208_金风科技\60m\02208_60m_20260109_to_20260518_normalized_with_boxes_wechat.jpg
```

该入口会先发文本，再按当前会话发送文件，适合“报告正文 + 技术图”这类常见组合场景。

如果希望把“生成 + 发送”合并成一条高层命令，当前建议使用统一任务入口：

```powershell
.\venv\Scripts\python.exe scripts/run_wechat_report_task.py fundamental 02208 --name 金风科技 --blended-hk
.\venv\Scripts\python.exe scripts/run_wechat_report_task.py hk60m --symbol 02208 --name 金风科技
.\venv\Scripts\python.exe scripts/run_wechat_report_task.py cn60m --symbol 300124 --name 汇川技术
```

这些命令默认面向“当前已打开微信会话”的发送场景；如果只想生成、不发送，可加 `--generate-only`。
每次通过该统一入口执行后，都会在 `data\_meta` 额外落一份 `wechat_task_manifest_*` 审计文件，记录任务类型、参数、状态和生成/发送产物，便于后续回查与重放。

如果已经把当前持仓维护在项目文件里，也可以直接按持仓清单批量生成：

```powershell
.\venv\Scripts\python.exe scripts/batch_regenerate_fundamental_briefs.py --holdings-file data\_meta\current_holdings.json --save-scorecard-text
```

资金面也有独立的 A 股持仓批量入口，默认读取 `data\_meta\current_a_share_holdings.json`，并在 `data\_meta` 生成单标的资金面评分卡和批量概览：

```powershell
.\venv\Scripts\python.exe scripts\batch_generate_capital_flow_reports.py
```

公开资金流接口偶发断连时，脚本默认会尝试使用 `data\_meta\capital_flow_cache` 下 7 天内的缓存；如需禁用缓存或放宽缓存年龄：

```powershell
.\venv\Scripts\python.exe scripts\batch_generate_capital_flow_reports.py --no-cache
.\venv\Scripts\python.exe scripts\batch_generate_capital_flow_reports.py --max-cache-age-days -1
```

如果东方财富主源和缓存都不可用，脚本默认会尝试同花顺低置信度 fallback；该口径使用资金净额替代主力净流入，并会在报告 `notes` 中标明。可用 `--no-fallback` 禁用。

如果只想每天一条命令更新 A 股持仓资金面并生成三轴管理清单，可以使用：

```powershell
.\venv\Scripts\python.exe scripts\run_a_share_daily_overview.py
```

该入口会先生成 A 股资金面单标的报告与 `group_a_share_capital_flow_overview_*.txt`，再复用最新基本面简报、最新 60M 技术面组合建议和刚生成的资金面概览，输出 `group_a_share_combined_overview_*.txt`。常用调试参数与资金面批处理保持一致：

```powershell
.\venv\Scripts\python.exe scripts\run_a_share_daily_overview.py --limit 2
.\venv\Scripts\python.exe scripts\run_a_share_daily_overview.py --max-cache-age-days -1
.\venv\Scripts\python.exe scripts\run_a_share_daily_overview.py --no-fallback
```

每次运行默认还会在 `data\_meta` 写入 `a_share_daily_overview_manifest_*.json`，记录持仓输入、关键参数、资金面成功/失败数量、输出报告路径和微信发送状态；如不需要审计文件，可加 `--no-manifest`。

如果要生成后把最终三轴管理清单发送到当前已打开的微信会话：

```powershell
.\venv\Scripts\python.exe scripts\run_a_share_daily_overview.py --send-wechat
```

发送前请先手动打开目标微信群或联系人会话。该开关只发送最终 `group_a_share_combined_overview_*.txt`，不发送单标的资金面明细。

港股资金面有独立的持仓批量入口，默认读取 `data\_meta\current_h_share_holdings.json`，并在 `data\_meta` 生成 `group_h_share_capital_flow_overview_*.txt`：

```powershell
.\venv\Scripts\python.exe scripts\batch_generate_h_share_capital_flow_reports.py
```

当前 HK V1 使用东方财富港股通成份行情中的成交额/换手率、东方财富港股通个股成交榜历史中的个股南向净买额、东方财富沪深港通持股统计中的 1 日南向持股市值变化，以及 HKEX 日终沽空成交额，并支持 `data\_meta\capital_flow_cache` 缓存回退；沽空比例会在成交额可用时用 `沽空成交额 / 成交额` 计算。个股南向净买额当前只在标的进入港股通成交榜的交易日可用，因此港股资金面仍应与技术面和基本面联动判断，不应孤立使用。

港股持仓也可以先生成同样结构的三段式综合概览：

```powershell
.\venv\Scripts\python.exe scripts\generate_h_share_combined_overview.py
```

该入口默认读取 `data\_meta\current_h_share_holdings.json`，复用最新港股基本面简报、最新 group888 60M 技术面组合建议，以及最新港股资金面批量概览，输出 `group_h_share_combined_overview_*.txt`。如果没有港股资金面概览，会显示 `missing/HK pending`；如果 HK V1 远端抓取失败，会显示 `failed/primary`。当前 HK V1 资金面线索不会单独给出完整资金确认加分。

如果要每天一条命令更新港股持仓资金面、生成三轴管理清单，并可选发送到当前微信会话，可以使用：

```powershell
.\venv\Scripts\python.exe scripts\run_h_share_daily_overview.py
```

该入口会先生成港股资金面单标的报告与 `group_h_share_capital_flow_overview_*.txt`，再复用最新基本面简报、最新 60M 技术面组合建议和刚生成的资金面概览，输出 `group_h_share_combined_overview_*.txt`。每次运行默认还会在 `data\_meta` 写入 `h_share_daily_overview_manifest_*.json`，记录输入、参数、资金面成功/失败数量、输出路径和微信发送状态；如不需要审计文件，可加 `--no-manifest`。

如果要生成后把最终港股三轴管理清单发送到当前已打开的微信会话：

```powershell
.\venv\Scripts\python.exe scripts\run_h_share_daily_overview.py --send-wechat
```

发送前请先手动打开目标微信群或联系人会话。该开关只发送最终 `group_h_share_combined_overview_*.txt`，不发送单标的资金面明细。

如果你在 Python 代码里直接消费报告输出，当前推荐：

```python
from fundamental.reporting import save_fundamental_brief, save_scorecard_text

brief_path = save_fundamental_brief(
	scorecard=result.scorecard,
	snapshot=result.fetched.snapshot,
	field_sources=result.fetched.field_sources,
)

scorecard_path = save_scorecard_text(
	scorecard=result.scorecard,
	snapshot=result.fetched.snapshot,
)
```

## 项目结构

```
chanlun-stock/
├── src/
│   ├── chanlun/
│   │   ├── __init__.py         # 技术面包导出入口
│   │   ├── models.py           # 数据结构定义
│   │   ├── normalize.py        # 包含关系处理
│   │   ├── fractal.py          # 分型识别
│   │   ├── bi.py               # 笔识别
│   │   ├── zhongshu.py         # 中枢识别
│   │   ├── wechat.py           # 微信发送相关封装
│   │   ├── data/
│   │   │   ├── __init__.py
│   │   │   ├── cleaner.py      # 数据清洗
│   │   │   ├── hk_fetcher.py   # 港股K线抓取
│   │   │   ├── hk_minute_fetcher.py # 港股分钟线策略抓取
│   │   │   └── kline_fetcher.py # 通用K线抓取入口
│   │   ├── strategy/
│   │   │   └── __init__.py
│   │   ├── backtest/
│   │   │   └── __init__.py
│   │   ├── visualization/
│   │   │   └── __init__.py
│   │   └── cli.py              # CLI入口
│   └── fundamental/
│       ├── __init__.py         # 基本面包导出入口
│       ├── data/               # 基本面外部数据源抓取与快照映射
│       │   ├── __init__.py
│       │   ├── hk_snapshot_fetcher.py # 港股快照抓取与标准化
│       │   └── cn_snapshot_fetcher.py # A股快照抓取与标准化
│       ├── models/             # 基本面输入输出模型
│       │   ├── __init__.py
│       │   ├── common.py
│       │   ├── snapshot.py
│       │   └── scorecard.py
│       ├── config/             # 子模型配置与注册表
│       │   ├── __init__.py
│       │   ├── models.py
│       │   ├── registry.py
│       │   └── tech_submodels.py
│       ├── validation/         # 字段校验
│       │   ├── __init__.py
│       │   └── snapshot_validator.py
│       ├── scoring/            # 评分规则与风险规则
│       │   ├── __init__.py
│       │   ├── base_engine.py
│       │   ├── common_rules.py
│       │   └── risk_rules.py
│       ├── reporting/          # brief / scorecard 文本报告渲染与保存
│       │   ├── __init__.py
│       │   ├── brief_report.py
│       │   └── text_report.py
│       └── services/           # 基本面分析入口
│           ├── __init__.py
│           ├── analyze_snapshot.py
│           ├── fetch_and_analyze_hk_snapshot.py
│           └── fetch_and_analyze_cn_snapshot.py
├── tests/
│   ├── conftest.py
│   ├── test_normalize.py
│   ├── test_fractal.py
│   ├── test_bi.py
│   ├── test_zhongshu.py
│   ├── test_hk_minute_fetcher.py
│   ├── test_fundamental.py
│   ├── test_fundamental_data_source.py
│   ├── test_integration.py
│   └── test_wechat.py
├── docs/
│   ├── chanlun-rule-spec.md         # 缠论规则规格
│   ├── hk-minute-data-source.md     # 港股分钟线数据源策略
│   ├── fundamental-doc-map.md       # 基本面文档总导航
│   ├── fundamental-data-source.md   # 基本面数据源策略
│   ├── fundamental-module-spec.md   # 基本面模块规格
│   ├── fundamental-roadmap.md       # 基本面模块路线图
│   ├── fundamental-snapshot-example.md  # 基本面标准输入样例
│   ├── fundamental-v1-minimum-fields.md # 基本面第一版最小字段集
│   ├── fundamental-industry-layering.md # 基本面行业分层规则
│   ├── fundamental-tech-submodels.md    # 科技行业子模型
│   ├── fundamental-tech-config-draft.md # 科技子模型代码配置草案
│   ├── fundamental-python-model-draft.md # 基本面 Python 数据模型草案
│   └── fundamental-code-layout-draft.md # 基本面代码目录草案
├── pyproject.toml
├── requirements.txt
└── README.md
```

## 设计原则

- 先统一规则口径，再开始编码
- 先建立最小可运行闭环，再接外部数据源
- 先输出可解释结果，再做自动化组合
- 技术面与基本面并列，不相互替代

## 图表导出约定

之后默认使用 `scripts/export_structures_with_boxes.py` 生成结构图，不再把旧的 `plot_*.py` 脚本作为首选出图入口。

标准输出内容包括：

- 包含关系处理后的方框标注
- 顶底分型
- 笔
- 笔中枢
- MACD 副图与 `*_macd.csv` 数据导出

示例：

```bash
python scripts/export_structures_with_boxes.py \
	--raw "data/300124_汇川技术/60m/300124_60m_20260116_to_20260419.csv" \
	--normalized "data/300124_汇川技术/60m/300124_60m_20260116_to_20260419_normalized.csv" \
	--output-dir "data/300124_汇川技术/60m" \
	--prefix "300124_60m_20260116_to_20260419_normalized"
```

输出文件默认包括：

- `*_fractals.csv`
- `*_confirmed_fractals.csv`
- `*_bis.csv`
- `*_zhongshu.csv`
- `*_macd.csv`
- `*_with_boxes.svg`

## 开发流程

1. 先补或修改规则文档
2. 准备样例数据和标准输入示例
3. 按文档实现最小闭环
4. 补全测试案例
5. 再接数据源和输出链路

## 当前文档阶段目标

- [x] 缠论规则规格
- [x] 基本面模块目标与边界
- [x] 基本面核心模型定义
- [x] 基本面评分和评级规则
- [x] 基本面实现路线图
- [x] 基本面示例输入模板
- [x] 基本面行业分层规则
- [ ] 技术面与基本面联合输出规格

## 当前实现状态

1. 基本面标准快照模型、评分与风险标记引擎已经落地
2. 港股 / A 股公共数据源入口已经接入，并有对应服务层封装
3. 数据源与评分链路已有针对性测试覆盖
4. 当前主要增量方向是文档收敛、联合分析输出和后续扩展字段
5. 报告期口径当前已进入显式治理阶段：主快照优先年报，无法对齐时必须保留 fallback trace 与用户可见警告

## 许可

MIT
