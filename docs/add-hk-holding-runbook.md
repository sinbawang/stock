# 新增港股持仓并发布到 CloudBase Checklist

这份 runbook 解决一件事：

- 当你要把一只新的港股加入持仓，例如阿里巴巴 `09988`，如何从“加入持仓”走到“小程序可见”

当前链路已经有一键总控脚本，但新增标的时最容易卡住的不是发布，而是：

- 名称和代码格式写错
- 基本面子模型首次命中后，缺少 manual supplement
- 单股报告没先验证，就直接全量刷新

所以当前推荐流程分两段：

- 先做“单股探针”
- 探针通过后，再做“全持仓刷新并发布”

## 1. 先确认基础信息

新增港股前，先确认：

- 交易代码是否为 5 位港股代码
- 名称是否采用当前仓库里会长期使用的中文名
- 是否属于已有子模型可覆盖的行业桶

阿里巴巴示例：

- `symbol`: `09988`
- `name`: `阿里巴巴-W`

说明：

- 当前仓库里还没有 `09988` 的既有样本或 manual supplement 模板
- 不要直接假设它一定能一次无补充跑通

## 2. 把新标的加入持仓文件

编辑 [data/stock_holdings.json](c:/sinba/stock/data/stock_holdings.json)，在 `markets.HK` 里加入：

```json
{
  "symbol": "09988",
  "name": "阿里巴巴-W"
}
```

注意：

- 港股代码在仓库内部按 5 位存储
- 名称一旦进入持仓，会参与报告标题、发布包和小程序展示，尽量第一次就定好

## 3. 先跑单股 mixed 报告探针

先不要急着全量刷新，先验证单股能否生成：

```powershell
c:/sinba/stock/venv/Scripts/python.exe scripts/generate_h_share_single_mixed_report.py 09988 --name 阿里巴巴-W --source xueqiu --fallback-source akshare
```

这一步的目标是确认三件事：

- 基本面是否能生成 `base.json`
- 60M 技术面是否能生成 `60m/tech.json`
- 资金面是否能生成 `fund.json` 与 `overview.txt`

成功后，至少应看到这些文件：

- [data/reports](c:/sinba/stock/data/reports) 下新增 `09988/`
- `data/reports/09988/base.json`
- `data/reports/09988/fund.json`
- `data/reports/09988/overview.txt`
- `data/reports/09988/60m/tech.json`

## 4. 判断是否需要 manual supplement

如果单股 mixed 报告能跑出结果，不代表基本面口径已经完整。

当前判断规则：

- 如果 `base.json` / 简报警告里明确提示字段缺失或人工补充口径，就补 manual supplement
- 如果命中的子模型是平台互联网类，优先检查是否需要 `guidance_attainment`

当前平台互联网类已有样本：

- [data/_meta/manual_supplements/00700_腾讯_platform_internet_v1_latest.txt](c:/sinba/stock/data/_meta/manual_supplements/00700_腾讯_platform_internet_v1_latest.txt)
- [data/_meta/manual_supplements/01024_快手_platform_internet_v1_latest.txt](c:/sinba/stock/data/_meta/manual_supplements/01024_快手_platform_internet_v1_latest.txt)
- [data/_meta/manual_supplements/03690_美团_platform_internet_v1_latest.txt](c:/sinba/stock/data/_meta/manual_supplements/03690_美团_platform_internet_v1_latest.txt)

阿里巴巴如果命中 `platform_internet_v1`，当前最可能需要补的也是：

- `guidance_attainment`

建议直接新建：

- `data/_meta/manual_supplements/09988_阿里巴巴-W_platform_internet_v1_latest.txt`

可直接用下面的最小模板：

```text
# 阿里巴巴-W platform_internet_v1 手工补充模板
# 可填值: beat / meet / miss
# 仅在确认公司曾公开给出可比的管理层指引时填写。
# notes 建议写明公告标题、日期、比较口径。

- guidance_attainment=null
- notes=null
```

如果你确认过业绩会 / 公告里有稳定、可比较的管理层指引，再把 `guidance_attainment` 从 `null` 改成：

- `beat`
- `meet`
- `miss`

## 5. 补充后再 rerun 单股探针

如果你新增了 manual supplement，再跑一次单股命令：

```powershell
c:/sinba/stock/venv/Scripts/python.exe scripts/generate_h_share_single_mixed_report.py 09988 --name 阿里巴巴-W --source xueqiu --fallback-source akshare
```

目标不是只看“是否成功退出”，而是确认：

- `overview.txt` 已更新
- `base.json` 中的 summary / warnings 更符合预期
- 没有再出现你无法接受的缺失字段口径

## 6. 再做全持仓刷新并发布

单股探针通过后，再跑一键刷新：

```powershell
$env:CLOUDBASE_ENV_ID="cloudbase-d9gplq92zc1d88ee6"
$env:CLOUDBASE_REGION="ap-guangzhou"
$env:CLOUDBASE_APIKEY="<your-api-key>"
c:/sinba/stock/venv/Scripts/python.exe scripts/refresh_holdings_publish_to_cloudbase.py --latest-only
```

这一步会顺序执行：

- 重生所有持仓 mixed 报告和 60M 结构图
- 重建 `build/miniapp-publish/latest`
- 上传到 CloudBase 的 `miniapp-publish/latest`

如果你只是刚新增了阿里巴巴，想先做“单股增量刷新 + 全局发布包重建”，可以直接用：

```powershell
$env:CLOUDBASE_ENV_ID="cloudbase-d9gplq92zc1d88ee6"
$env:CLOUDBASE_REGION="ap-guangzhou"
$env:CLOUDBASE_APIKEY="<your-api-key>"
c:/sinba/stock/venv/Scripts/python.exe scripts/refresh_holdings_publish_to_cloudbase.py --symbols 09988 --latest-only
```

这个模式的行为是：

- 只重生 `09988` 这只股票的 mixed 报告和图
- 但仍然会重建完整的 `build/miniapp-publish/latest`
- 然后把完整的 `latest` 发布到 CloudBase

所以它适合“新增/修正单只股票后，尽快把最新发布层推上去”的场景。

如果这次不是持仓变更，而是要验证缠论结构口径或抓取窗口，也可以直接在这个总控入口上追加参数，例如：

```powershell
c:/sinba/stock/venv/Scripts/python.exe scripts/refresh_holdings_publish_to_cloudbase.py --symbols 09988 --latest-only --zhongshu-level segment --pending-reverse-mode tail_mixed --day-bars 1000 --m60-bars 800 --m15-bars 1200 --skip-upload
```

这组参数分别控制：

- `zhongshu-level`: 画笔中枢或线段中枢
- `pending-reverse-mode`: 尾部反向分型占位口径
- `day-bars`: 日线目标抓取根数
- `m60-bars`: 60M 目标抓取根数
- `m15-bars`: 15M 目标抓取根数

## 7. 发布后确认点

发布完成后，至少确认三件事：

- [build/miniapp-publish/latest/index.json](c:/sinba/stock/build/miniapp-publish/latest/index.json) 里已经出现 `09988`
- [build/miniapp-publish/cloudbase-upload-manifest.json](c:/sinba/stock/build/miniapp-publish/cloudbase-upload-manifest.json) 里已经包含 `stocks/09988/summary.json`、`stocks/09988/detail.json`
- 小程序重新读取最新 `index.json` 后，首页或港股页能看到阿里巴巴

## 8. 小程序什么时候能看到

只要下面三件事同时成立，小程序就能看到：

- `data/reports/09988/...` 已经生成
- `build/miniapp-publish/latest/index.json` 已经重新写入 `09988`
- CloudBase 上的 `miniapp-publish/latest/...` 已经被新发布覆盖

注意：

- 如果小程序有缓存，它可能不会“自动秒刷”，但下一次拉最新索引时就会出现
- 所以问题不在“小程序要不要改代码”，而在“你有没有重新生成并重新发布 latest”

## 9. 最短实战路径

如果你现在要加的就是阿里巴巴，最短路径就是：

1. 改 [data/stock_holdings.json](c:/sinba/stock/data/stock_holdings.json)，加入 `09988 / 阿里巴巴-W`
2. 跑单股探针
3. 如有需要，新建 `09988_阿里巴巴-W_platform_internet_v1_latest.txt`
4. rerun 单股探针
5. 跑 [scripts/refresh_holdings_publish_to_cloudbase.py](c:/sinba/stock/scripts/refresh_holdings_publish_to_cloudbase.py)
6. 打开 [build/miniapp-publish/latest/index.json](c:/sinba/stock/build/miniapp-publish/latest/index.json) 确认 `09988` 已进入发布包

## 10. 当前局限

当前一键总控脚本已经支持“只重生指定股票”，但发布层仍然是“完整 latest 重建后整体上传”。

这意味着：

- 新增阿里巴巴后，你可以只重生它这一只，再整体重建和重发 latest
- CloudBase 侧当前仍是覆盖式上传完整 `latest/`，不是只上传单只股票目录