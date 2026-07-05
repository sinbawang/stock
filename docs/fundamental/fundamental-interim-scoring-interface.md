# 年报锚定 + 季报刷新评分接口

这份文档回答的是另一个问题：

- 当前“年报锚定 + 季报刷新”已经接进基本面服务层后，领域对象、服务接口和输出结构现在是什么，以及还预留了哪些扩展点

如果关心的是为什么要这么设计，先看 [fundamental-interim-scoring-design.md](fundamental-interim-scoring-design.md)。

如果需要回到总导航，见 [fundamental-doc-map.md](fundamental-doc-map.md)。

## 1. 当前接口约束

当前已存在的服务入口是：

- [src/fundamental/services/fetch_and_analyze_cn_snapshot.py](c:/sinba/stock/src/fundamental/services/fetch_and_analyze_cn_snapshot.py)
- [src/fundamental/services/fetch_and_analyze_hk_snapshot.py](c:/sinba/stock/src/fundamental/services/fetch_and_analyze_hk_snapshot.py)
- [src/fundamental/services/fetch_and_analyze_cn_blended.py](c:/sinba/stock/src/fundamental/services/fetch_and_analyze_cn_blended.py)
- [src/fundamental/services/fetch_and_analyze_hk_blended.py](c:/sinba/stock/src/fundamental/services/fetch_and_analyze_hk_blended.py)

当前已存在的核心输入输出对象是：

- `FundamentalSnapshot`
- `FundamentalScoreCard`
- `AnnualAnchorScore`
- `InterimOverlayScore`
- `BlendedFundamentalScoreCard`

当前实现继续遵循这两个原则：

- 尽量复用现有单报告期评分对象
- 不把“加权跨期评分”硬塞回单期 `FundamentalScoreCard`

## 2. 当前对象层次

### 2.1 单期中间报告快照

当前实现没有为“中间报告快照”发明独立类。

当前继续复用 `FundamentalSnapshot`，并主要通过以下字段区分期别：

- `report_period`
- `period_type`

`annual_anchor` / `interim_overlay` 这层语义当前保留在更上层的 blended 对象里，而不是继续扩 `FundamentalSnapshot`。

### 2.2 年报锚定结果

当前已实现：

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

当前已实现：

```python
@dataclass(frozen=True)
class InterimOverlayScore:
    snapshot: FundamentalSnapshot
    components: tuple[OverlayComponent, ...]
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

当前已实现：

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

## 3. 当前服务接口

### 3.1 数据层接口

当前数据层已经补上“同一标的两类报告期快照”这层获取能力。

当前入口：

```python
def fetch_cn_period_snapshots(
    symbol: str,
    name: str | None = None,
    annual_period: date | None = None,
    interim_period: date | None = None,
) -> CnPeriodSnapshotsFetchResult:
    ...


def fetch_hk_period_snapshots(
    symbol: str,
    name: str | None = None,
    annual_period: date | None = None,
    interim_period: date | None = None,
    quote_overlay_source: str | None = None,
) -> HkPeriodSnapshotsFetchResult:
    ...
```

返回对象当前会同时携带 annual / interim 两份 fetched 结果，而不是只返回裸 `FundamentalSnapshot`：

```python
@dataclass(frozen=True)
class CnPeriodSnapshotsFetchResult:
    annual: FetchedCnFundamentalSnapshot
    interim: FetchedCnFundamentalSnapshot | None = None
```

```python
@dataclass(frozen=True)
class HkPeriodSnapshotsFetchResult:
    annual: FetchedHkFundamentalSnapshot
    interim: FetchedHkFundamentalSnapshot | None = None
    warnings: tuple[str, ...] = ()
```

### 3.2 评分层接口

当前已实现如下服务入口：

```python
def fetch_and_analyze_cn_blended_fundamentals(
    symbol: str,
    name: str | None = None,
    submodel: str | None = None,
    manual_supplement: Mapping[str, Any] | None = None,
    manual_supplement_path: str | None = None,
    weighting_profile: InterimWeightingProfile = DEFAULT_INTERIM_WEIGHTING_PROFILE,
) -> BlendedCnFundamentalAnalysis:
    ...


def fetch_and_analyze_hk_blended_fundamentals(
    symbol: str,
    name: str | None = None,
    submodel: str | None = None,
    quote_overlay_source: str | None = None,
    manual_supplement: Mapping[str, Any] | None = None,
    manual_supplement_path: str | None = None,
    weighting_profile: InterimWeightingProfile = DEFAULT_INTERIM_WEIGHTING_PROFILE,
) -> BlendedHkFundamentalAnalysis:
    ...
```

返回对象当前分别为：

```python
@dataclass(frozen=True)
class BlendedCnFundamentalAnalysis:
    blended: BlendedFundamentalScoreCard
    annual_anchor: AnnualAnchorScore
    interim_overlay: InterimOverlayScore | None
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
```

```python
@dataclass(frozen=True)
class BlendedHkFundamentalAnalysis:
    blended: BlendedFundamentalScoreCard
    annual_anchor: AnnualAnchorScore
    interim_overlay: InterimOverlayScore | None
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
```

## 4. 权重配置接口

当前实现没有把权重硬编码成裸字符串，而是通过配置对象传递：

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

当前实现也只有一个 `default` profile。

## 5. Overlay 结果的内部结构

当前实现没有让 `InterimOverlayScore` 复制一套完整 `dimension_scores`，而是采用组件化结构：

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

这样比复制完整维度体系更容易解释，也更符合当前“刷新层”定位。

对于少量需要行业特化解释的组件，建议优先把解释收敛到 `note`，而不是再额外扩字段。

例如 `bank_v1` 的 `profitability_refresh`，第一版更适合在组件层保留如下语义：

- `covered_metrics` 仍记录原始字段名：`roe`、`net_interest_margin`
- `note` 明确说明：`roe` 按报告期先做年化代理，再与 `net_interest_margin` 按银行语义组合

这样可以保持接口稳定，同时把“字段名”和“计分口径”区分开。

## 6. 报告接口

当前实现没有修改现有 `render_scorecard_text(...)` 去承载 blended 字段。

当前新增的是：

```python
def render_blended_scorecard_text(blended: BlendedFundamentalScoreCard) -> str:
    ...


def render_blended_fundamental_brief(blended: BlendedFundamentalScoreCard) -> str:
    ...
```

对应落盘 helper 当前也已存在：

```python
def save_blended_scorecard_text(blended: BlendedFundamentalScoreCard, ...) -> Path:
    ...


def save_blended_fundamental_brief(blended: BlendedFundamentalScoreCard, ...) -> Path:
    ...
```

当前 blended 报告会新增以下区块：

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

## 7. CLI 接口

当前 CLI 是：

- [scripts/generate_fundamental_brief.py](c:/sinba/stock/scripts/generate_fundamental_brief.py)

当前实现没有替换原入口，而是在原入口上增加 blended 开关。

当前已开放参数：

- `--blended-cn`
- `--blended-hk`

默认仍保持现有行为：

- 不开启 blended 开关时，继续输出单期评分

当前还没有在 CLI 层开放：

- `weighting_profile`
- 指定 `annual_period` / `interim_period`

也就是说，当前 CLI 已经能切换单期 / blended 两条主路径，但更细粒度的 blended 参数仍保留在服务层。

## 8. 兼容性原则

当前实现仍坚持下面几条：

1. 旧的 `fetch_and_analyze_*_snapshot(...)` 不破坏
2. 旧的 `FundamentalScoreCard` 不扩展成跨期黑盒对象
3. 新能力通过新增服务和新增报告函数暴露
4. CLI 默认行为不变，开启新参数才走 blended 路径

## 9. 当前落地范围与边界

当前已落地的范围可以概括为：

1. CN / HK 都已有 blended 服务入口
2. `annual + latest_interim` 两层对象、权重、报告和落盘 helper 已贯通
3. 单标的入口已经落到现有 CLI
4. HK blended 当前仍保留按子模型白名单渐进开放的边界
5. 更细的 CLI 参数、更多子模型覆盖和批量回补仍可继续扩展

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

这两点当前都已经落实到代码。后续正确扩展方向不是：

- 把所有逻辑继续往 `fetch_and_analyze_*_snapshot(...)` 里面堆

而是：

- 保留单期服务
- 新增 blended 服务
- 在报告和 CLI 层显式切换