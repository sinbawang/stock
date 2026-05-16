# 年报锚定 + 季报刷新评分接口草案

这份文档回答的是另一个问题：

- 如果后续要把“年报锚定 + 季报刷新”的设计真正接进当前基本面服务层，领域对象、服务接口和输出结构应该怎么定义

如果关心的是为什么要这么设计，先看 [fundamental-interim-scoring-design.md](fundamental-interim-scoring-design.md)。

如果需要回到总导航，见 [fundamental-doc-map.md](fundamental-doc-map.md)。

## 1. 当前接口约束

当前已存在的服务入口是：

- [src/fundamental/services/fetch_and_analyze_cn_snapshot.py](c:/sinba/stock/src/fundamental/services/fetch_and_analyze_cn_snapshot.py)
- [src/fundamental/services/fetch_and_analyze_hk_snapshot.py](c:/sinba/stock/src/fundamental/services/fetch_and_analyze_hk_snapshot.py)

当前已存在的核心输入输出对象是：

- `FundamentalSnapshot`
- `FundamentalScoreCard`

当前设计草案的原则是：

- 尽量复用现有单报告期评分对象
- 不把“加权跨期评分”硬塞回单期 `FundamentalScoreCard`

## 2. 建议新增的对象层次

### 2.1 单期中间报告快照

第一版不建议为“季报快照”单独发明完全不同的类。

建议继续复用 `FundamentalSnapshot`，但通过以下字段显式区分：

- `report_period`
- `period_type`
- 新增 `period_scope`

建议的 `period_scope`：

- `annual_anchor`
- `interim_overlay`

如果不想修改当前快照模型，也可以在更上层对象里保留这层语义。

### 2.2 年报锚定结果

建议引入：

```python
@dataclass(frozen=True)
class AnnualAnchorScore:
    snapshot: FundamentalSnapshot
    scorecard: FundamentalScoreCard
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
```

职责：

- 保留“最近年报口径”的完整评分结果

### 2.3 季报刷新结果

建议引入：

```python
@dataclass(frozen=True)
class InterimOverlayScore:
    snapshot: FundamentalSnapshot
    overlay_score: float
    rating_hint: str | None = None
    covered_metrics: tuple[str, ...] = ()
    missing_metrics: tuple[str, ...] = ()
    drivers_positive: tuple[str, ...] = ()
    drivers_negative: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
```

职责：

- 表达“最新中间报告对评分新鲜度的刷新”
- 不试图替代完整 `FundamentalScoreCard`

### 2.4 最终加权结果

建议引入：

```python
@dataclass(frozen=True)
class BlendedFundamentalScoreCard:
    symbol: str
    name: str
    market: str
    submodel_id: str
    annual_anchor: AnnualAnchorScore
    interim_overlay: InterimOverlayScore | None
    annual_weight: float
    interim_weight: float
    blended_total_score: float
    blended_rating: str
    freshness_label: str
    warnings: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    combined_comment: str | None = None
```

职责：

- 把跨期结果收敛成用户可消费的最终对象

## 3. 建议的服务接口

### 3.1 数据层接口

当前服务层上面缺的不是“打分公式”，而是“同一标的两类报告期快照”这层获取能力。

建议新增如下数据层入口：

```python
def fetch_cn_period_snapshots(
    symbol: str,
    name: str | None = None,
    annual_period: date | None = None,
    interim_period: date | None = None,
) -> CnPeriodSnapshots:
    ...


def fetch_hk_period_snapshots(
    symbol: str,
    name: str | None = None,
    annual_period: date | None = None,
    interim_period: date | None = None,
    quote_overlay_source: str | None = None,
) -> HkPeriodSnapshots:
    ...
```

建议返回对象：

```python
@dataclass(frozen=True)
class PeriodSnapshots:
    annual_snapshot: FundamentalSnapshot | None
    interim_snapshot: FundamentalSnapshot | None
    annual_assumptions: tuple[str, ...] = ()
    interim_assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
```

### 3.2 评分层接口

建议新增如下服务入口：

```python
def analyze_cn_blended_fundamentals(
    symbol: str,
    name: str | None = None,
    submodel: str | None = None,
    manual_supplement: Mapping[str, Any] | None = None,
    manual_supplement_path: str | None = None,
    weighting_profile: str = "default",
) -> BlendedFundamentalAnalysis:
    ...


def analyze_hk_blended_fundamentals(
    symbol: str,
    name: str | None = None,
    submodel: str | None = None,
    quote_overlay_source: str | None = None,
    manual_supplement: Mapping[str, Any] | None = None,
    manual_supplement_path: str | None = None,
    weighting_profile: str = "default",
) -> BlendedFundamentalAnalysis:
    ...
```

建议返回对象：

```python
@dataclass(frozen=True)
class BlendedFundamentalAnalysis:
    blended: BlendedFundamentalScoreCard
    annual_anchor: AnnualAnchorScore
    interim_overlay: InterimOverlayScore | None
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
```

## 4. 权重配置接口

第一版不要把权重硬编码进服务函数内部。

建议引入简单配置对象：

```python
@dataclass(frozen=True)
class InterimWeightingProfile:
    profile_id: str
    annual_after_annual: float = 1.0
    interim_after_annual: float = 0.0
    annual_after_q1: float = 0.8
    interim_after_q1: float = 0.2
    annual_after_h1: float = 0.65
    interim_after_h1: float = 0.35
    annual_after_q3: float = 0.5
    interim_after_q3: float = 0.5
```

第一版建议只有一个 `default` profile。

## 5. Overlay 结果的内部结构建议

第一版不建议让 `InterimOverlayScore` 再复制一套完整 `dimension_scores`。

更推荐的结构是：

```python
@dataclass(frozen=True)
class OverlayComponent:
    component: str
    score: float
    weight: float
    covered_metrics: tuple[str, ...] = ()
    missing_metrics: tuple[str, ...] = ()
    note: str | None = None
```

然后：

```python
@dataclass(frozen=True)
class InterimOverlayScore:
    snapshot: FundamentalSnapshot
    components: tuple[OverlayComponent, ...]
    overlay_score: float
    ...
```

这样比复制完整维度体系更容易解释，也更符合“刷新层”定位。

对于少量需要行业特化解释的组件，建议优先把解释收敛到 `note`，而不是再额外扩字段。

例如 `bank_v1` 的 `profitability_refresh`，第一版更适合在组件层保留如下语义：

- `covered_metrics` 仍记录原始字段名：`roe`、`net_interest_margin`
- `note` 明确说明：`roe` 按报告期先做年化代理，再与 `net_interest_margin` 按银行语义组合

这样可以保持接口稳定，同时把“字段名”和“计分口径”区分开。

## 6. 报告接口建议

第一版建议不要修改现有 `render_scorecard_text(...)` 去兼容所有新字段。

更合理的做法是新增：

```python
def render_blended_scorecard_text(result: BlendedFundamentalAnalysis) -> str:
    ...


def render_blended_fundamental_brief(result: BlendedFundamentalAnalysis) -> str:
    ...
```

报告建议新增以下区块：

- 年报锚定结果
- 季报刷新结果
- 当前权重与最终加权总分
- 刷新驱动项

如果某个刷新组件内部使用了代理口径，而不是原始字段直接计分，报告里建议直接写明。

例如 `bank_v1` 的 `profitability_refresh`，推荐展示成类似：

```text
profitability_refresh: 18.40 x 25%，覆盖 roe, net_interest_margin
说明: 银行盈利刷新优先使用年化 ROE 代理值，并与净息差按银行语义组合；不直接把单季 ROE 与年报 ROE横比。
```

这样做有两个好处：

- 用户能看懂为什么银行刷新层没有直接照搬一般行业的单季口径
- 后续如果 `ROE` 或 `NIM` 缺失，也能在同一块说明里留痕，而不用改报告主结构

## 7. CLI 接口建议

当前 CLI 是：

- [scripts/generate_fundamental_brief.py](c:/sinba/stock/scripts/generate_fundamental_brief.py)

第一版不建议直接替换原入口。

建议新增可选参数：

- `--blend-interim`
- `--weighting-profile`
- `--interim-period`
- `--annual-period`

默认仍保持现有行为：

- 不开启 `--blend-interim` 时，继续输出单期评分

这样可以避免把现有批量脚本和导出链路一次性全部打断。

## 8. 兼容性原则

后续实现时应坚持下面几条：

1. 旧的 `fetch_and_analyze_*_snapshot(...)` 不破坏
2. 旧的 `FundamentalScoreCard` 不扩展成跨期黑盒对象
3. 新能力通过新增服务和新增报告函数暴露
4. CLI 默认行为不变，开启新参数才走 blended 路径

## 9. 第一版落地范围建议

当前建议第一版只承诺这些：

1. 先支持 A 股
2. 先支持 `utility_operator_v1`、`home_appliance_v1`、`bank_v1`
3. 先支持 `annual + latest_interim` 两层
4. 先做单标的入口
5. 先做文本报告，不急着扩批量回补

## 10. 测试建议

实现阶段至少需要三类测试：

1. period selection tests
2. weighting tests
3. rendering tests

更具体地说：

- 有年报也有 Q1 时，能同时拿到两份期别对象
- 权重在 Q1/H1/Q3 节点切换正确
- overlay 缺字段时不会强行参与加权
- 文本报告能明确写出“年报锚定分 / 季报刷新分 / 当前权重”

## 11. 结论

这次接口层最重要的结论是：

- 现有单期评分接口应保留
- 跨期加权能力应作为并行新入口新增

也就是说，后续正确扩展方向不是：

- 把所有逻辑继续往 `fetch_and_analyze_*_snapshot(...)` 里面堆

而是：

- 保留单期服务
- 新增 blended 服务
- 在报告和 CLI 层显式切换