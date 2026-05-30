# 小程序云存储发布 Schema

这份文档只定义一件事：

- 当前 `data/reports` 产物如果要发布到微信云开发云存储，并由微信小程序原生渲染消费，发布层应该长什么样

它不重复定义基本面评分规则、缠论识别规则，也不替代当前 `data/reports` 的底层落盘约定。它回答的是“如何把当前报告产物整理成适合手机端消费的发布包”。

关联文档：

- [combined-analysis-output-spec.md](combined-analysis-output-spec.md): 当前原始报告落盘格式
- [combined-analysis-service-interface.md](combined-analysis-service-interface.md): 当前联合分析公共接口边界

## 1. 目标与边界

当前目标是：

- 继续保留 `data/reports` 作为分析计算和落盘真源
- 额外生成一层“发布包”上传到微信云存储
- 小程序只读发布包，不直接解释底层 CSV / 原始 TXT / manifest
- 小程序使用原生组件渲染，不依赖 HTML WebView

当前明确不做的事：

- 不让小程序直接消费 `analyze/*.csv`
- 不让小程序直接渲染 Markdown 表格
- 不把本地绝对路径、脚本审计信息、批处理 manifest 暴露给前端

## 2. 为什么不能直接把 `data/reports` 原样给小程序

当前 `data/reports` 已经很适合作为“发布层上游数据源”，但还不是“小程序最终展示层”。原因主要有四个：

- `overview.txt`、`group_*_overview_*.txt` 偏工程输出，仍包含文件路径、口径说明、长段文本，不适合手机端默认直出
- 组合总览里存在 Markdown 表格，窄屏阅读体验差
- `analyze/*.csv`、manifest、审计文件属于中间结果或运维结果，不应暴露给用户
- 小程序如果直接扫目录找“最新文件”，逻辑会很脆弱，必须有一份顶层索引文件承接“发现最新内容”这件事

因此当前推荐：

- `data/reports` 做生产层
- `publish/` 做上传层
- 小程序只消费 `publish/` 中的 JSON 和图片

## 3. 发布层总体原则

### 3.1 只发布三类内容

- 列表页需要的轻量摘要 JSON
- 详情页需要的结构化 JSON
- 直接展示用的图片资产 `jpg/png`

### 3.2 不发布这些原始内容给前端直接渲染

- `analyze/*.csv`
- `report.txt`、`analysis.txt`、`advice.txt` 原文全文
- `group_*_overview_*.txt` 原始 Markdown 表格
- `*_manifest_*.json|txt`

这些文件可以继续保留在生产层或运维层，但不应作为小程序直接消费协议。

### 3.3 以“可原生渲染”优先，不以“保留原文”优先

发布层 JSON 应该优先提供：

- 标题
- 标签
- 分数
- 简短说明
- 卡片列表
- 分段 bullet
- 图表资源路径

而不是让小程序自行拆 Markdown 或正则解析长文本。

## 4. 推荐云存储目录

当前推荐把上传后的云存储目录收成一个固定前缀，例如：

```text
miniapp-publish/
  latest/
    index.json
    groups/
      a_share.json
      h_share.json
      portfolio.json
    stocks/
      000651/
        summary.json
        detail.json
        charts/
          60m.jpg
          15m.jpg
          day.jpg
      00700/
        summary.json
        detail.json
        charts/
          60m.jpg
          15m.jpg
          day.jpg
  snapshots/
    20260530_203730/
      index.json
      groups/...
      stocks/...
```

约定说明：

- `latest/` 是小程序默认读取入口
- `snapshots/<stamp>/` 用于回溯历史发布快照
- 小程序通常只读 `latest/`
- 上传脚本可选择同时维护 `latest/` 和一次性快照目录

当前仓库里的落地脚本：

- 生成发布包：`scripts/build_miniapp_publish_bundle.py`
- 上传发布包：`scripts/upload_miniapp_publish_bundle.py`

当前上传脚本默认上传本地 `build/miniapp-publish/latest` 到云端 `miniapp-publish/latest`，并在本地生成 `build/miniapp-publish/cloudbase-upload-manifest.json`。

当前推荐环境变量：

- `CLOUDBASE_ENV_ID` 或 `TCB_ENV_ID`
- `CLOUDBASE_REGION` 或 `TCB_REGION`
- `CLOUDBASE_APIKEY`

如果没有现成 `CLOUDBASE_APIKEY`，上传脚本也支持在存在 `TENCENT_SECRET_ID/TENCENT_SECRET_KEY` 时临时创建一个服务端 API Key 再执行上传。

## 5. 顶层发布索引

这是整个方案的核心。即使当前只用云存储、不用云数据库，也必须有一个顶层索引文件。

建议路径：

- `miniapp-publish/latest/index.json`

建议结构：

```json
{
  "schema_version": "v1",
  "generated_at": "2026-05-30T20:55:00+08:00",
  "source_root": "data/reports",
  "markets": ["CN", "HK"],
  "counts": {
    "stocks": 14,
    "cn": 6,
    "hk": 8
  },
  "groups": {
    "portfolio": "groups/portfolio.json",
    "a_share": "groups/a_share.json",
    "h_share": "groups/h_share.json"
  },
  "stocks": [
    {
      "symbol": "000651",
      "name": "格力电器",
      "market": "CN",
      "updated_at": "2026-05-30T20:35:15+08:00",
      "summary": "stocks/000651/summary.json",
      "detail": "stocks/000651/detail.json",
      "cover_chart": "stocks/000651/charts/60m.jpg",
      "tags": ["watch", "P2", "等待触发"]
    }
  ]
}
```

当前这份索引必须回答小程序的三个问题：

- 现在有哪些持仓可展示
- 每只股票的摘要和详情去哪里读
- 首页默认该按什么顺序展示

## 6. 列表页摘要协议

建议每只股票至少产出一份 `summary.json`，供：

- 首页持仓列表
- 搜索结果
- 市场分组页
- 组合页跳转卡片

建议路径：

- `stocks/<symbol>/summary.json`

建议结构：

```json
{
  "schema_version": "v1",
  "symbol": "000651",
  "name": "格力电器",
  "market": "CN",
  "updated_at": "2026-05-30T20:35:15+08:00",
  "priority": "P2",
  "action": "等待触发",
  "bucket": "watch",
  "cards": {
    "fundamental": {
      "score": 54.8,
      "rating": "C",
      "summary": "基本面暂处可跟踪区间"
    },
    "technical": {
      "timeframe": "60m",
      "conclusion": "偏强，持有为主。",
      "suggestion": "已有仓位可继续持有，回踩不破 38.34 再考虑加仓。"
    },
    "capital_flow": {
      "score": 51.4,
      "rating": "C",
      "source": "ths.fund_flow.fallback",
      "summary": "资金面中性偏弱"
    }
  },
  "cover_chart": {
    "timeframe": "60m",
    "path": "stocks/000651/charts/60m.jpg"
  },
  "jump": {
    "detail": "stocks/000651/detail.json"
  }
}
```

设计要求：

- 列表页只放摘要，不放大段原文
- 关键字段尽量已经是展示友好的文案，不要求小程序再推理
- `priority/action/bucket` 必须直接可用，避免前端自己再按三轴重新分组

## 7. 详情页协议

建议每只股票至少产出一份 `detail.json`，供原生详情页渲染。

建议路径：

- `stocks/<symbol>/detail.json`

建议结构：

```json
{
  "schema_version": "v1",
  "symbol": "000651",
  "name": "格力电器",
  "market": "CN",
  "updated_at": "2026-05-30T20:35:15+08:00",
  "headline": {
    "title": "格力电器 000651",
    "subtitle": "三轴综合观察",
    "priority": "P2",
    "action": "等待触发",
    "bucket": "watch"
  },
  "overview": {
    "summary": "观察：60M 技术节奏偏积极",
    "bullets": [
      "基本面 54.8/C，质量一般但可跟踪",
      "60M 技术面偏强，持有为主",
      "资金面 51.4/C，当前不构成强确认"
    ]
  },
  "sections": [
    {
      "key": "fundamental",
      "title": "基本面",
      "rating": "C",
      "score": 54.8,
      "summary": "基本面暂处可跟踪区间",
      "highlights": ["盈利质量较好", "利润与现金流匹配度较稳"],
      "follow_ups": ["关注行业景气和经营效率变化"]
    },
    {
      "key": "technical",
      "title": "技术面",
      "timeframe": "60m",
      "conclusion": "偏强，持有为主。",
      "suggestion": "已有仓位可继续持有，回踩不破 38.34 再考虑加仓。",
      "overview": [
        "时间区间：2026-01-19 10:30 到 2026-05-29 15:00",
        "中枢数量：1"
      ],
      "structure": [
        "最新确认向上笔：...",
        "最新确认向下笔：..."
      ],
      "signals": ["buy_3", "无确认卖点"]
    },
    {
      "key": "capital_flow",
      "title": "资金面",
      "rating": "C",
      "score": 51.4,
      "source": "ths.fund_flow.fallback",
      "summary": "资金面中性偏弱",
      "metrics": [
        {"label": "主力净流入", "value": "-64388500"},
        {"label": "5日主力净流入", "value": "-960000000"}
      ],
      "risks": ["关键资金指标出现净流出"]
    }
  ],
  "charts": [
    {"timeframe": "60m", "path": "stocks/000651/charts/60m.jpg", "label": "60M 结构图"},
    {"timeframe": "15m", "path": "stocks/000651/charts/15m.jpg", "label": "15M 结构图"},
    {"timeframe": "day", "path": "stocks/000651/charts/day.jpg", "label": "日线结构图"}
  ],
  "disclaimer": "本页面仅用于持仓跟踪与研究，不构成投资建议。"
}
```

当前详情页协议的重点不是“字段越全越好”，而是：

- 小程序页面能直接按 section 渲染
- 不需要解析长文本
- 不暴露本地路径和脚本内部结构

## 8. 组合页协议

当前组合总览的原始 `.txt` 很有价值，但不适合手机端直接展示。

建议发布层把它们转成 JSON：

- `groups/a_share.json`
- `groups/h_share.json`
- `groups/portfolio.json`

建议结构：

```json
{
  "schema_version": "v1",
  "group": "a_share",
  "generated_at": "2026-05-30T20:05:33+08:00",
  "counts": {
    "today_action": 0,
    "watch_pool": 5,
    "risk_pool": 1
  },
  "sections": [
    {
      "key": "today_action",
      "title": "今日动作",
      "items": []
    },
    {
      "key": "watch_pool",
      "title": "观察池",
      "items": [
        {
          "symbol": "000651",
          "name": "格力电器",
          "priority": "P2",
          "action": "等待触发",
          "bucket": "watch",
          "fundamental": "54.8/C",
          "technical": "偏强，持有为主。",
          "capital_flow": "51.4/C/fallback",
          "comment": "观察：60M 技术节奏偏积极"
        }
      ]
    }
  ],
  "notes": [
    "priority/action 只用于持仓管理排序，不改变底层评分",
    "本报告用于三轴对照，不构成投资建议"
  ]
}
```

当前组合页必须避免两件事：

- 直接把 Markdown 表格塞进富文本
- 让前端去解析 `P2 | 等待触发 | 000651 ...` 这种行文本

## 9. 当前生产层到发布层的映射建议

### 9.1 直接复用的生产层文件

- `data/reports/<symbol>/base.json`
- `data/reports/<symbol>/fund.json`
- `data/reports/<symbol>/<timeframe>/tech.json`
- `data/reports/<symbol>/<timeframe>/structure.jpg`

这些文件适合做发布层的主来源。

### 9.2 只作为“摘要提取来源”的文件

- `data/reports/<symbol>/overview.txt`
- `data/reports/_meta/group_a_share_combined_overview_*.txt`
- `data/reports/_meta/group_h_share_combined_overview_*.txt`
- `data/reports/_meta/group888_single_compact_*.txt`

这些文件可继续保留，但建议只在发布脚本里抽取摘要，不建议让小程序直接消费。

### 9.3 不进入发布层的文件

- `data/reports/<symbol>/<timeframe>/analyze/*.csv`
- `data/reports/_meta/*manifest*.json|txt`

## 10. 小程序端推荐页面模型

当前推荐的小程序原生页面模型：

### 10.1 首页

- 数据来源：`index.json`
- 展示方式：卡片流
- 每张卡只显示：名称、代码、priority/action、三轴摘要、更新时间、封面图

### 10.2 单股详情页

- 数据来源：`detail.json`
- 展示方式：原生 `scroll-view + tabs + card`
- 建议分 4 个区块：概览、基本面、技术面、图表

### 10.3 组合页

- 数据来源：`groups/*.json`
- 展示方式：`今日动作 / 观察池 / 风险池` 三段卡片列表

### 10.4 搜索页

- 数据来源：`index.json`
- 搜索字段：`symbol`、`name`、`market`、`tags`

## 11. 云存储-only 的实现注意点

当前如果只用云存储，不用云数据库，仍然有一个现实问题：

- 小程序必须先拿到一份“已知路径或已知文件 ID 的顶层索引文件”

所以当前至少要满足下面一个条件：

- 方案 A：约定一个固定发布路径，并通过上传脚本额外维护一份可稳定访问的 `latest/index.json`
- 方案 B：上传脚本在本地生成一份 `upload_manifest.json`，保存顶层 `index.json` 对应的云端 file id，供小程序配置使用

不论采用哪种方式，发布层 schema 本身都不变；变化的只是“小程序如何拿到第一份入口索引”。

## 12. 当前推荐的最小发布集合

如果要先做第一版，不必一次发布全部原始内容。当前建议第一版只发布：

- `index.json`
- `groups/a_share.json`
- `groups/h_share.json`
- 每只股票一个 `summary.json`
- 每只股票一个 `detail.json`
- 每只股票一个 `60m.jpg`

这样已经足够支撑：

- 首页
- A/H 组合页
- 单股详情页

`15m/day` 图片、更多解释字段、历史快照，可以留到第二版再加。

## 13. 下一步落地建议

当前最自然的下一步是：

1. 先在脚本层新增一个“发布包生成器”，从 `data/reports` 生成本地 `publish/` 目录
2. 再写一个“云存储上传器”，把 `publish/` 上传到微信云存储并输出顶层索引信息
3. 小程序第一版只对接 `index.json + groups/*.json + stocks/*/detail.json + 60m.jpg`

这样可以先把发布协议稳定下来，再决定是否需要引入云数据库做更强的索引与版本管理。