# 联合分析公共服务接口说明

这份文档回答的是另一个问题：

- 当前 `plus_60m` 联合分析链路，如果要从“脚本拼装”收敛成“公共服务入口”，接口应该怎么定义

如果你关心的是联合文本最后长什么样，看 [combined-analysis-output-spec.md](combined-analysis-output-spec.md)。

如果你关心的是这条链路以后应该由哪些公共函数承接、脚本该保留什么职责，看这份文档。

## 1. 当前现状

截至 2026-05-11，当前仓库已经有两层比较清晰的公共能力：

- 基本面公共服务：
  - [src/fundamental/services/fetch_and_analyze_hk_snapshot.py](c:/sinba/stock/src/fundamental/services/fetch_and_analyze_hk_snapshot.py)
  - [src/fundamental/services/fetch_and_analyze_cn_snapshot.py](c:/sinba/stock/src/fundamental/services/fetch_and_analyze_cn_snapshot.py)
- 基本面文本渲染：
  - [src/fundamental/reporting/text_report.py](c:/sinba/stock/src/fundamental/reporting/text_report.py)

但“技术面 + 基本面”的联合分析仍主要停留在脚本层组织：

- [scripts/run_hk_60m_chanlun_report.py](c:/sinba/stock/scripts/run_hk_60m_chanlun_report.py)
- [scripts/run_cn_60m_chanlun_report.py](c:/sinba/stock/scripts/run_cn_60m_chanlun_report.py)

当前脚本层实际上承担了四类职责：

1. 抓取并标准化 60M K 线
2. 识别分型、笔、中枢、MACD 并导出结构图
3. 生成技术面观察文本与末尾操作建议
4. 把技术面文本、基本面文本和图片拼成最终交付物

这意味着当前“联合分析”已经能交付，但还不是一个干净的公共服务接口。

## 2. 为什么要收口到公共服务层

如果继续把联合逻辑留在脚本里，后面会出现几个实际问题：

- HK / CN 两条链路会重复维护拼接逻辑
- 以后新增日线、周线或批量分析时，很容易复制出第二套第三套文本拼装
- 文件落盘、发布准备、分析计算三类职责会继续缠在一起
- 想做测试时，很难只验证“联合分析文本是否正确”，因为当前逻辑混在脚本流程里

所以这里真正需要收口的不是“再写一个大脚本”，而是：

- 把联合分析的计算与文本生成变成可复用、可测试的公共服务

## 3. 当前最合理的边界

当前最合理的分层边界是：

### 3.1 公共服务层负责

- 调基本面服务，得到 `FetchedFundamentalAnalysis` / `FetchedCnFundamentalAnalysis`
- 调技术面分析流程，得到结构分析结果
- 生成联合文本
- 生成适合落盘或发送的结构化结果对象

### 3.2 脚本层负责

- 解析 CLI 参数
- 决定是否落盘
- 决定是否渲染 SVG / PNG / JPG
- 决定是否落盘或进入发布流程
- 决定输出目录、文件命名和联系人

### 3.3 不应该放进联合服务层的东西

- 硬编码联系人 `888`
- 依赖某个脚本的路径规则去决定领域结果
- 在服务层里直接 print 终端提示

一句话说，联合公共服务层负责“分析与组装”，脚本层负责“入口与交付”。

## 4. 当前建议的公共接口形态

当前建议不要一上来就设计成非常抽象的通用大接口，而是先落一个最小可复用形态。

建议分成两层：

### 4.1 第一层：技术面分析结果服务

建议提供类似这样的公共入口：

```python
analyze_hk_60m_chanlun(...)
analyze_cn_60m_chanlun(...)
```

这层只负责：

- 输入 symbol / name / 时间区间 / 数据源参数
- 返回技术面结构结果与技术面文本
- 不直接发送微信

### 4.2 第二层：联合分析报告服务

建议提供类似这样的公共入口：

```python
build_hk_60m_combined_analysis(...)
build_cn_60m_combined_analysis(...)
```

这层只负责：

- 调基础技术面服务
- 调基础基本面服务
- 产出联合文本与结构化结果
- 不直接处理发布动作

这样设计的原因是：

- 技术面分析本身未来也可能单独复用
- 联合层不需要知道技术面内部如何抓数、识别笔或中枢
- HK / CN 可以先各自稳定，再考虑是否再往上提炼成更通用入口

## 5. 建议的返回对象

当前最值得先统一的不是参数数量，而是返回对象。

建议最小返回对象包含这些部分：

```python
@dataclass(frozen=True)
class CombinedAnalysisResult:
    symbol: str
    name: str
    market: str
    timeframe: str
    generated_at: datetime
    fundamental: Any
    technical: Any
    combined_text: str
    title: str
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
```

这里的重点不是字段名必须一模一样，而是返回对象至少要同时保留：

- 结构化基本面结果
- 结构化技术面结果
- 用户可直接发送的联合文本
- 联合层新增的警告与假设

否则以后还是只能靠重新拼字符串回溯上下文。

## 6. 建议的输入边界

当前建议联合服务入口只接受“分析所需参数”，不要直接把发送参数塞进去。

### 6.1 联合分析服务建议输入

- `symbol`
- `name`
- `start`
- `end`
- `timeframe`
- `submodel`
- `quote_overlay_source`
- `manual_supplement`
- `minute_source` 或 `primary_source`
- `fallback_sources`

### 6.2 不建议放进联合分析服务的输入

- `contact`
- `visible_row_index`
- `allow_search_switch`
- `result_index`
- `current_chat_only`

原因很简单：这些不是分析参数，而是交付参数。

## 7. 当前推荐的数据流

建议后续把数据流收成下面这样：

1. 技术面服务返回结构分析结果和技术面文本
2. 基本面服务返回 `Fetched*FundamentalAnalysis`
3. 联合服务调用两者，产出 `CombinedAnalysisResult`
4. 渲染/落盘/微信脚本只消费 `CombinedAnalysisResult`

这样脚本层就不用再自己理解：

- 如何把 `render_scorecard_text(...)` 的结果插入联合报告
- 标题里何时写“手工补充版”
- 警告应该保留在哪个区块
- 末尾操作建议和技术面观察如何排列

## 8. 当前建议的最小公共 API

如果只做第一步，建议先把接口定义收在一个新服务模块里，例如：

- `src/analysis_services/combined_60m.py`
- 或 `src/chanlun/services/combined_analysis.py`
- 或 `src/fundamental/services/combined_analysis.py`

从当前仓库分层来看，更推荐单独新建一个并列服务层，而不是硬塞进 `fundamental/services/`。

原因是：

- 这条链路天然跨 `chanlun` 和 `fundamental`
- 放进任一单侧模块都会让职责看起来偏斜

第一版最小 API 可以先只定这两个函数：

```python
def build_hk_60m_combined_analysis(...) -> CombinedAnalysisResult:
    ...


def build_cn_60m_combined_analysis(...) -> CombinedAnalysisResult:
    ...
```

先让 HK / CN 两条链路复用起来，比一开始强行做成 market-agnostic 泛化接口更稳妥。

## 9. 当前与现有服务的衔接方式

这层新接口不应该重写已有服务，而应直接复用：

- HK 基本面：`fetch_and_analyze_hk_snapshot(...)`
- CN 基本面：`fetch_and_analyze_cn_snapshot(...)`
- 基本面文本：`render_scorecard_text(...)`
- 技术面现有识别流程：当前在 `run_hk_60m_chanlun_report.py` / `run_cn_60m_chanlun_report.py` 内部

也就是说，最现实的第一步不是重写算法，而是：

- 先把脚本里现有的联合拼装逻辑提取成可调用函数

## 10. 对测试的直接收益

一旦有了公共服务接口，至少可以单独测这些事情：

- 给定一个 `scorecard`，联合文本是否保留 `警告` 与 `计算:`
- 使用 `manual supplement` 时，标题或正文是否能反映手工补充口径
- 技术面偏弱但基本面较强时，联合文本是否仍保持“观察而非强动作”口径
- HK / CN 两条链路是否输出相同的区块顺序

这比现在只能跑脚本再肉眼看输出，要稳定得多。

## 11. 当前最务实的落地顺序

如果按最小风险推进，建议顺序是：

1. 先冻结这份公共接口说明
2. 再把 HK / CN 两个脚本里共同的联合文本拼装逻辑提成函数
3. 让脚本层只负责参数、落盘、图片和发布准备
4. 最后再考虑是否统一成更上层的跨市场接口

这样不会打断现有 live 可用链路，也不会为了“架构好看”提前抽象过度。