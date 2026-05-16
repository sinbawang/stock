# 年报锚定 + 季报刷新评分设计草案

这份文档回答的是下面这个问题：

- 当前基本面评分既然默认优先年报，那么在年报之后又披露了一季报 / 中报 / 三季报时，如何引入“更新鲜”的评分，又不把季报和年报生硬混成一套口径

这份文档只定义方案，不直接落实现代码。

如果需要回到总导航，见 [fundamental-doc-map.md](fundamental-doc-map.md)。

如果关心的是未来公共服务入口和返回对象长什么样，继续看 [fundamental-interim-scoring-interface.md](fundamental-interim-scoring-interface.md)。

## 1. 当前现状

截至 2026-05-16，当前基本面 live 评分的默认行为可以总结成一句话：

- CN / HK 快照都优先取最近年报；只有没有年报时，才回退到最新可用报告期

当前代码依据：

- [src/fundamental/data/cn_snapshot_fetcher.py](c:/sinba/stock/src/fundamental/data/cn_snapshot_fetcher.py)
- [src/fundamental/data/hk_snapshot_fetcher.py](c:/sinba/stock/src/fundamental/data/hk_snapshot_fetcher.py)
- [src/fundamental/services/source_warning_helpers.py](c:/sinba/stock/src/fundamental/services/source_warning_helpers.py)

这意味着当前系统不是“永远只看年报”，但它也不是“永远优先最新披露”。

因此一旦出现下面这种情况：

- 2025-12-31 年报已经披露
- 2026-03-31 一季报也已经披露

当前评分仍会继续锚定 2025 年报。

这个行为的优点是口径稳定，缺点是：

- 评分新鲜度可能落后于公司最新经营变化

## 2. 设计目标

这次要解决的不是“能不能给季报也打个分”，而是下面三个更具体的问题：

1. 如何把年报的完整性和季报的新鲜度同时保留下来
2. 如何避免把季报和年报直接混成一套不可解释的黑盒总分
3. 如何在现有 `FundamentalSnapshot -> FundamentalScoreCard -> 报告` 链路上平滑扩展，而不是推翻重做

## 3. 不建议直接做简单线性混分

最直观的想法通常是：

```text
加权总分 = 年报总分 * w1 + 季报总分 * w2
```

当前不建议第一版直接这样做，原因有三类。

### 3.1 口径不对称

年报和季报不是同等完整的两份输入：

- 年报更适合承载稳定性、三年均值、多期波动、完整现金流质量
- 季报更适合承载短期增长、盈利兑现、营运压力和监管类最新变化

直接把两份“完整总分”相加，容易制造伪精确。

### 3.2 季节性会污染分数

很多单季指标天然有季节性：

- 一季报现金流
- 半年报利润率
- 三季报营运周转
- 金融机构阶段性拨备、息差或投资收益波动

如果直接按总分线性混合，很容易把季节性扰动误写成“基本面趋势变化”。

### 3.3 会重复计量同一类事实

季报和年报底层依赖的很多事实并不独立，例如：

- `revenue_growth`
- `net_profit_growth`
- `gross_margin`
- `debt_to_asset`

简单相加会让同一类信号被重复折算进总分。

## 4. 当前建议的总体思路

当前建议不是“年报分 + 季报分”的并列双总分，而是：

- 年报锚定分 + 季报刷新层

也就是：

```text
最终分 = annual_anchor_score + interim_overlay_adjustment
```

为了对用户更直观，也可以在报告展示成：

```text
年报锚定分
季报刷新分
加权总分
```

但在内部建模上，建议始终把“季报”视为 overlay，而不是第二套完整评分主体系。

## 5. 建议的评分结构

### 5.1 年报锚定分 `annual_anchor_score`

职责：

- 保留当前完整评分体系的主体地位
- 继续负责长期质量、完整财报口径、跨年稳定性判断

第一版建议：

- 尽量复用当前 `score_snapshot(...)` 逻辑
- 不在这一层引入季报特有权重

### 5.2 季报刷新分 `interim_overlay_score`

职责：

- 反映“自上一次年报以来”的最新经营变化
- 只覆盖适合季报判断的少数指标簇

第一版建议只覆盖三类：

1. 增长刷新
2. 盈利与现金流刷新
3. 资产负债 / 监管状态刷新

不要在第一版尝试复制全部子模型维度。

### 5.3 最终展示分 `blended_total_score`

建议公式：

```text
blended_total_score = annual_anchor_score * annual_weight + interim_overlay_score * interim_weight
```

这里的关键不是公式本身，而是：

- `interim_overlay_score` 不应被构造成和年报总分完全同口径的另一套总分

它应是“刷新层的可比标准分”，不是“第二套完整体检报告”。

## 6. 季报适用指标边界

### 6.1 第一版建议纳入季报 overlay 的指标

通用非金融：

- `revenue_growth`
- `net_profit_growth`
- `gross_margin`
- `gross_margin_trend`
- `operating_cashflow_to_profit`
- `accounts_receivable_growth`
- `inventory_growth`
- `debt_to_asset`
- `current_ratio`

金融：

- `core_tier1_ratio`
- `capital_adequacy_ratio`
- `npl_ratio`
- `provision_coverage_ratio`
- `net_interest_margin`
- `loan_deposit_growth_gap`
- `solvency_adequacy_ratio`
- `combined_ratio`
- `investment_return`
- `net_capital_ratio`

### 6.2 第一版不建议纳入季报 overlay 的指标

- `roe_3y_mean`
- `roe_3y_cv`
- 依赖完整年报现金流结构的长期稳定性判断
- 强依赖年度分红节奏的 `dividend_yield` 主判断
- 强依赖完整年报口径的某些行业代理指标

原因很简单：这些字段更像“长期锚”，不是“季报刷新”。

### 6.3 `bank_v1` 的盈利刷新建议单独处理

银行的 `profitability_refresh` 不建议直接照搬一般行业的“两个单季值等权平均”思路。

原因是：

- `Q1 ROE` 直接使用单季值时，天然会低于全年口径，不适合与年报 `ROE` 直觉比较
- `net_interest_margin` 更接近银行当前盈利能力的核心经营信号，但其含义又和 `ROE` 不完全同层
- 如果把 `Q1 ROE` 和 `NIM` 简单等权平均，往往会把“季节性较强的 ROE”误写成“银行盈利能力突然转弱”

因此，第一版更建议：

1. `ROE` 在季报层只以“年化代理值”进入，不直接使用单季原值
2. `NIM` 继续保留在季报层，并作为银行盈利刷新里的主信号
3. `roe_3y_cv`、`roe_3y_mean` 继续留在年报锚定层，不进入第一版季报盈利刷新

如果沿用当前 `profitability_refresh` 组件名，建议其内部按下面口径构造：

```text
profitability_refresh = 0.35 * score(annualized_roe_proxy)
					  + 0.65 * score(net_interest_margin)
```

这里的核心不是精确到小数点后的权重，而是明确两件事：

- `ROE` 在银行季报里应先做年化，再进入刷新层
- `NIM` 在银行季报盈利刷新里应高于 `ROE` 的解释权重

第一版推荐的年化口径可以直接按报告期离散处理：

- 一季报：`ROE * 4`
- 中报：`ROE * 2`
- 三季报：`ROE * 4 / 3`

这样做的目的不是把季报 ROE 伪装成精确全年预测，而是把它还原成更接近“年度盈利能力”的可比代理值。

第一版同时建议保持下面边界：

- 不把 `investment_return` 并入银行盈利刷新，除非 live 数据源已经稳定
- 不对 `NIM` 再做历史平滑，除非后续验证发现公共源存在明显口径跳变
- 当 `NIM` 缺失时，允许仅用年化 `ROE` 刷新并留痕
- 当 `ROE` 缺失时，允许仅用 `NIM` 刷新并留痕

对应到当前 blended 结构，`bank_v1` 第一版更合理的划分是：

- `capital_refresh`: 继续负责资本充足、资产质量、拨备缓冲
- `profitability_refresh`: 只负责年化 `ROE` 与 `NIM`
- `business_quality_refresh`: 继续负责存贷增速匹配

也就是说，银行需要的不是“把更多季报字段硬塞进 overlay”，而是先把已有两个盈利字段按银行语义重新摆正。

## 7. 权重建议

第一版不建议固定全年都使用一套死权重。

建议按“距最近年报的披露阶段”切换权重：

1. 年报后、季报未出：`annual=1.00, interim=0.00`
2. 一季报后：`annual=0.80, interim=0.20`
3. 中报后：`annual=0.65, interim=0.35`
4. 三季报后：`annual=0.50, interim=0.50`
5. 下一次年报披露后：重置回 `annual=1.00, interim=0.00`

这套权重的好处是：

- 用户直觉容易理解
- 越远离年报，季报刷新权重越高
- 年报一出，重新回到完整口径主导

第一版先做离散档位，不建议直接上连续时间衰减模型。

## 8. 报告层展示建议

报告层不要只展示一个最终分。

建议至少增加以下字段：

- `年报锚定分`
- `季报刷新分`
- `当前加权总分`
- `最新纳入的中间报告期`
- `当前权重说明`
- `季报刷新主要驱动项`

示意：

```text
年报锚定分: 72.4
季报刷新分: 58.0
当前加权总分: 67.3
年报口径: 2025-12-31
最新季报口径: 2026-03-31
当前权重: 年报 80% / 季报 20%
```

这样用户才能区分：

- “这家公司底盘其实还行”
- “但最新一季有走弱迹象”

## 9. 数据模型扩展方向

第一版文档层先假设会新增三类对象：

- `AnnualAnchorScore`
- `InterimOverlayScore`
- `BlendedFundamentalScoreCard`

不建议直接把所有字段都塞回现有 `FundamentalScoreCard`，否则会让当前对象职责变模糊。

更合理的方向是：

- 现有 `FundamentalScoreCard` 继续代表“单一报告期口径评分”
- 新增上层对象代表“跨报告期加权结果”

## 10. 第一版实现范围建议

第一版目标应当收窄成：

1. 先支持单一市场链路能跑通
2. 先支持年报 + 一季报双层加权
3. 先支持少数行业桶

建议优先级：

1. `utility_operator_v1`
2. `home_appliance_v1`
3. `bank_v1`
4. 再推广到其他行业桶

原因：

- 这三类已经存在“年报锚定后容易因后续披露变旧”的真实需求
- 字段相对稳定
- 对比结果更容易人工验算

## 11. 第一版不做什么

- 不做连续时间衰减
- 不做自动识别所有中间报告披露节奏
- 不做“所有子模型全部季报化”
- 不把 current score、annual score、interim score 混成一张不可解释的大对象
- 不在第一版就把所有 CLI 和导出脚本都改完

## 12. 实施顺序建议

建议按下面顺序推进：

1. 冻结这份设计文档
2. 冻结接口与数据模型草案
3. 先做单市场、单行业桶 POC
4. 再做报告层展示
5. 再做脚本入口与批量回补

## 13. 当前需要明确的开放问题

真正需要在实现前拍板的，不多，但必须明确：

1. `interim_overlay_score` 的分值范围是否与当前 `0-100` 总分完全同标尺
2. 季报 overlay 是否允许引入少量行业特化规则，而不是只用通用规则
3. `dividend_yield` 这类更接近年度股东回报的字段，在中报 / 三季报阶段是否完全不参与 overlay
4. 第一版是否只做 A 股，还是 CN / HK 一起开工
5. 第一版报告是否直接对外展示三套分值，还是先只展示加权总分 + 说明

当前建议答案：

- 第一版保持同标尺，便于解释
- 允许少量行业特化，但要克制
- `dividend_yield` 不进入第一版 overlay 主判断
- 第一版优先 A 股，再推广 HK
- 报告里直接展示三套分值，避免黑盒

## 14. 结论

这次扩展最重要的设计结论不是“是否要引入季报”，而是：

- 季报应该作为刷新层，而不是替代层

也就是说，正确方向不是“再做一套完整季报评分系统”，而是：

- 保留年报作为长期锚
- 用季报对评分新鲜度做有边界的刷新

这样才能同时保住：

- 解释性
- 稳定性
- 新鲜度
- 演进空间