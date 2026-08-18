# 小程序发布包样本审计（2026-08）

本页记录一次基于真实本地发布产物的抽样审计，目标不是讨论“schema 应该长什么样”，而是回答：

1. `build/miniapp-publish/latest` 现在实际上长什么样。
2. 它与 [miniapp-cloud-publish-schema.md](miniapp-cloud-publish-schema.md) 当前建议协议相比，已经落地了什么。
3. 还缺哪些关键文件、字段和上传环节。
4. confirmed/pending/auxiliary 三态在真实样本里处于什么落点。

## 1. 审计范围

本轮只审计当前工作区里的真实样本，不推断远端云存储是否另有补充：

- 本地目录：`build/miniapp-publish/latest`
- 上传 manifest：`build/miniapp-publish/cloudbase-upload-manifest.json`
- 抽样股票：`000651`、`000591`

## 2. 样本结论总览

先给结论：当前样本更像“部分单股发布产物 + 图表 JSON 上传残留”，还不能视为一份完整、可直接供小程序冷启动的 `latest` 发布包。

最重要的三个结论：

1. 顶层缺少 `index.json` 与 `groups/*.json`，因此当前本地 `latest` 目录不是完整发布包。
2. `summary.json` / `detail.json` 已经真实存在，而且内容比 schema 示例更丰富，但不少列表层字段仍为 `null`。
3. 上传 manifest 与 schema 脱节明显：manifest 里只记录了部分 `charts/*.json`，`index/summary/detail/groups` 都没有进入上传清单。

## 3. 实际目录现状

### 3.1 顶层目录

当前 `build/miniapp-publish/latest` 下只有：

- `stocks/`

没有看到：

- `index.json`
- `groups/a_share.json`
- `groups/h_share.json`
- `groups/portfolio.json`

这与 [miniapp-cloud-publish-schema.md](miniapp-cloud-publish-schema.md) 里的推荐根目录结构不一致。

### 3.2 单股目录

以 `000651` 为例，当前单股目录已有：

- `base.json`
- `summary.json`
- `detail.json`
- `charts/1m.json`
- `charts/5m.json`
- `charts/30m.json`
- `charts/day.json`

`000591` 样本呈现同样模式。

当前结论：

- 单股层产物并非缺失。
- 缺的是顶层发现入口、组合分组文件，以及完整上传收口。

## 4. 与 schema 的逐项对照

### 4.1 `index.json` / `groups/*.json`

当前状态：缺失。

影响：

- 小程序无法按 [miniapp-cloud-publish-schema.md](miniapp-cloud-publish-schema.md) 既定方式从 `latest/index.json` 冷启动。
- 组合页、A 股页、港股页缺少稳定数据入口。
- 首页的持仓计数、排序、市场分组都无法由发布包统一提供。

判定：P0 缺口。

### 4.2 `summary.json`

当前状态：已真实落地，但与 schema 示例存在明显差异。

已落地字段：

- `schema_version`
- `symbol`
- `name`
- `market`
- `updated_at`
- `comment`
- `cards.fundamental.*`
- `cards.technical.*`
- `cards.capital_flow.*`

当前样本中明显偏离 schema 的点：

1. `priority/action/bucket` 当前为 `null`。
2. 没看到 schema 示例中的 `cover_chart` 与 `jump.detail`。
3. 技术块远比 schema 示例更富，已经带出：
   - `signal_catalog`
   - `same_level_decomposition`
   - `latest_signal_summary`
   - `technical_focus_lines`
   - `latest_zhongshu`
   - `latest_lei_zhongshu`
   - `segment_tail_interpretations`

判定：

- 从“单股技术摘要足不足”看，当前样本不是过少，而是“有信息，但字段组织尚未按发布层统一收口”。
- 从“小程序首页/搜索页能不能稳定消费”看，`priority/action/bucket` 为空会直接削弱列表排序和管理分桶。

### 4.3 `detail.json`

当前状态：已真实落地，而且比 schema 示例更接近多周期详情页，而不是单一技术块。

已落地特征：

- `headline.priority/action/bucket` 当前也为 `null`
- `overview.summary` 直接使用技术结论文案
- `sections` 不只是 `fundamental/technical/capital_flow` 三段，而是至少包含：
  - `fundamental`
  - `technical_day`
  - `technical`（30M）
  - 其余技术或资金段落按样本继续展开

技术 section 里的真实字段已明显 richer than schema：

- `source`
- `operation_level`
- `score_breakdown`
- `signal_catalog`
- `same_level_decomposition`
- `latest_signal_summary`
- `technical_focus_lines`
- `latest_zhongshu`
- `latest_lei_zhongshu`
- `precision_*`

判定：

- `detail.json` 已经是最接近 machine-readable 状态载体的发布层文件。
- 但当前状态字段还没有按 [../chanlun/theory-implementation-consumer-diff-matrix.md](../chanlun/theory-implementation-consumer-diff-matrix.md) 的统一命名完全收口，例如仍主要使用 `same_level_decomposition.*`，而不是统一外露 `structure_state.*`、`same_level_decomposition_mode` 等扁平入口。

### 4.4 图表资产

当前状态：样本里是 `charts/*.json`，不是 schema 示例中的 `jpg`。

样本实际存在：

- `1m.json`
- `5m.json`
- `30m.json`
- `day.json`

判定：

- 这说明当前发布层已经偏向“结构化图表 JSON 驱动”，而不是单纯图片驱动。
- [miniapp-cloud-publish-schema.md](miniapp-cloud-publish-schema.md) 仍以 `60m.jpg` 等图片示例为主，和当前样本不一致。

## 5. 三态语义在真实样本里的落点

### 5.1 已出现的 pending 证据

当前样本里已经能看到一些明确的 pending 证据，不只是文案猜测：

- `same_level_decomposition.is_strict_theory_equivalent=false`
- `same_level_decomposition.current.status=ongoing`
- `same_level_decomposition.relationship.kind=undetermined`
- `segment_tail_interpretations[*].kind=pending_confirmation`
- `segment_tail_interpretations[*].evidence` 中显式出现 `stop_category=pending`

这说明：

- 发布层样本其实已经携带部分 pending 语义。
- 但这些语义还没有被统一抽象成 schema 明文必读字段。

### 5.2 当前仍偏文本化的 confirmed 风险

样本里同时存在：

- `conclusion`: 例如“偏多，允许轻仓试错。”
- `signal_points` / `signal_catalog`: 例如活跃 `buy3`、`sell3`

风险在于：

- 如果前端只读取 `conclusion` 或活跃买卖点，而不同时读取 `same_level_decomposition`、`segment_tail_interpretations` 等降级证据，就容易把工程摘要误读成严格 confirmed。

### 5.3 auxiliary 语义已具备，但未统一外显

样本里已有：

- `latest_lei_zhongshu`
- `zhongshu_level_note`: 明示“类中枢仅作辅助参考”

这说明 auxiliary 语义并不缺；缺的是发布层对“辅助提示”这一档的稳定 UI 和字段规范。

## 6. 上传 manifest 审计

`build/miniapp-publish/cloudbase-upload-manifest.json` 暴露出一个更直接的问题。

当前 manifest 的关键事实：

- `file_count = 12`
- `index.relative_path = null`
- `index.cloud_path = null`
- `index.file_id = null`
- `files[]` 中只看到若干 `stocks/*/charts/1m.json` 与 `stocks/*/charts/5m.json`

没看到：

- `index.json`
- `groups/*.json`
- `stocks/*/summary.json`
- `stocks/*/detail.json`

判定：

- 当前 upload manifest 不是“完整发布包已上传”的证据。
- 它更像一次只触达部分图表 JSON 的上传残留。

这也是本轮最关键的操作性结论：

- 现在的问题不只是 schema 设计，而是发布构建或上传链路并没有把 schema 规定的主入口文件真正产出并上传。

## 7. 风险分级

### P0

- 顶层 `index.json` 缺失
- `groups/*.json` 缺失
- upload manifest 中没有 `index/summary/detail/groups`

### P1

- `priority/action/bucket` 在真实样本里仍为 `null`
- 图表资产当前是 `*.json`，而 schema 和若干前端提示词仍以 `jpg` 为主示例

### P2

- `summary/detail` 已有较丰富状态字段，但未统一收口到发布层必读字段集合

## 8. 建议动作

1. 先核对并修复发布构建脚本，确保 `latest/index.json` 和 `groups/*.json` 必产出。
2. 再核对上传脚本，确保 `summary.json`、`detail.json`、`groups/*.json`、`index.json` 进入 manifest 和上传清单。
3. 把 `priority/action/bucket` 的来源重新接通，避免列表页只有单股内容、没有组合管理标签。
4. 明确发布层图表主协议到底是 `charts/*.json` 还是 `*.jpg`；文档、脚本、前端提示词三边统一一种主口径。
5. 在 `detail.json` 中正式外露统一状态入口，例如：
   - `structure_state.*`
   - `same_level_decomposition_mode`
   - `zs_monitor_alert`
   - `signal_state`

## 8.1 已落地的链路硬化

基于这轮审计，发布链路已经补上三道明确防线，后续复盘这里应以“当前代码状态”而不是上面的历史样本状态为准：

1. `build_miniapp_publish_bundle.py` 已改为先写 staging，再原子替换 `latest/`，避免构建失败时把旧的完整发布包清空成半残目录。
2. `upload_miniapp_publish_bundle.py` 已增加 source bundle 完整性校验；当 `index.json`、`groups/portfolio.json` 或 `stocks/*/{base,summary,detail}.json` 缺失时，会直接拒绝上传。
3. `refresh_holdings_publish_to_cloudbase.py` 现在会产出显式 `bundle_integrity` 摘要，并把 build/upload 失败分类写进 timing report，避免后续只能靠异常文本判断问题。

当前建议的最小排查顺序也因此更新为：

1. 先看 `data/reports/_meta/holdings_refresh_timing_latest.json` 的 `artifacts.bundle_integrity`。
2. 再看同一份 timing report 里的 `publish_failures[*]` 是否已经给出 `incomplete_bundle_missing_entry_files`、`incomplete_bundle_missing_stock_meta`、`empty_upload_source_dir` 等分类。
3. 只有当 timing report 不能解释问题时，再回看 `build/miniapp-publish/latest` 实际目录和 `cloudbase-upload-manifest.json`。

## 9. 结论

这轮样本审计说明：

- 当前单股发布内容已经明显有料，甚至比 schema 示例更接近真实消费所需。
- 真正的断点不在“字段太少”，而在“顶层入口缺失 + 上传链路未收口 + 状态字段未统一命名”。

因此下一步不该继续抽象讨论，而应直接转到：

- 发布构建/上传链路核对
- 发布层状态字段正式收口
- 用真实样本回写 schema 示例
