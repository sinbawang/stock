# Data Storage Layout

## 目标

这个方案解决 3 个问题：

1. `data/` 现在同时承载本地配置、报告产物、抓取中间文件和缓存，职责混在一起。
2. `reports/<symbol>/<timeframe>/analyze/` 会持续膨胀，但当前代码并没有系统复用这些历史中间文件。
3. 云端容器部署不适合依赖本地 `data/` 目录做长期状态存储。

目标不是一次把所有代码都改完，而是先把目录职责划清，后续代码按这个边界逐步迁移。

## 总原则

1. 源码、文档、模板进 Git。
2. 真实持仓、抓取缓存、报告产物、中间分析文件不进 Git。
3. 对外消费的最新报告和内部可复用的历史行情缓存分开存放。
4. “分析输出目录” 和 “行情缓存目录” 不能混用。
5. 云端服务不依赖容器本地磁盘保存长期状态。

## 推荐目录树

```text
config/
	stock_holdings.json
	stock_holdings.example.json
	runtime/
		local.env.example

data/
	reports/
		_meta/
		<symbol>/
			base.json
			fund.json
			overview.txt
			day/
				tech.json
				report.txt
				analysis.txt
				advice.txt
				structure.svg
				analyze/
					latest/
						raw.csv
						normalized.csv
						fractals.csv
						confirmed_fractals.csv
						bis.csv
						segments.csv
						zhongshu.csv
						macd.csv
			60m/
				...
			30m/
				...
			15m/
				...
			5m/
				...

	cache/
		capital_flow/
		kline/
			HK/
				03690/
					day.parquet
					60m.parquet
					30m.parquet
					15m.parquet
					5m.parquet
			CN/
				300124/
					day.parquet
					60m.parquet
					30m.parquet
					15m.parquet
					5m.parquet

	tmp/
		service_jobs/
		publish_build/

build/
	miniapp-publish/
	logs/
```

## 每层职责

### `config/`

放可提交的仓库级配置和模板。

建议内容：

1. `stock_holdings.json`
2. `stock_holdings.example.json`
3. 本地 `.env` 模板
4. 运行参数样例

这里的 `config/stock_holdings.json` 表示“仓库默认持仓/默认观察列表”。

它的作用是：

1. GitHub repo 里有一个默认可运行的 holdings 文件。
2. TCB / CloudBase 容器从 Git 构建后，容器内也天然有这个文件。
3. 本地和云端都能拿到同一份 bootstrap 配置，不会再出现“代码默认找 holdings，但镜像里没有文件”的问题。

如果这份清单包含敏感真实持仓，就不应该直接提交；这种情况下应只提交一个脱敏后的默认观察列表，真实持仓走本地覆盖或云端外部配置。

### `data/reports/`

只放当前对外消费的最新报告结果。

这里的文件是给以下场景用的：

1. 小程序读取最新技术结果
2. 本地查看最新单股报告
3. 组合层汇总最新结论

建议保留：

1. `tech.json`
2. `report.txt`
3. `analysis.txt`
4. `advice.txt`
5. `structure.svg`
6. `base.json`
7. `fund.json`
8. `overview.txt`

这些文件按 `symbol + timeframe` 只保留当前最新版即可。

### `data/reports/<symbol>/<timeframe>/analyze/latest/`

只放“最近一次分析运行”的中间文件。

建议内容：

1. `raw.csv`
2. `normalized.csv`
3. `fractals.csv`
4. `confirmed_fractals.csv`
5. `bis.csv`
6. `segments.csv`
7. `zhongshu.csv`
8. `macd.csv`

这里不要再按时间戳无限累积。当前代码只对极少数 case 做复用，绝大多数历史中间文件现在只是占空间。

### `data/cache/kline/`

这是未来真正应该积累历史行情的地方。

它和 `reports/.../analyze/` 的区别是：

1. `analyze/` 是某次分析运行生成的中间文件。
2. `kline/` 是跨运行、可持续积累、可去重、可复用的行情缓存。

如果后面要突破外部数据源“最大返回 K 线条数限制”，真正应该增强的是这里，而不是继续保留大量历史 `analyze/*.csv`。

建议设计目标：

1. 同一 `market/symbol/timeframe` 维护一份长期缓存。
2. 新抓取结果按时间追加。
3. 按时间戳去重。
4. 优先从缓存读取，不足部分再补抓。
5. 最终分析输入从缓存切片，而不是直接依赖每次临时抓取。

### `data/cache/capital_flow/`

继续承接已有资金面缓存逻辑，和行情缓存并列，不混进 `reports/`。

### `data/tmp/`

放短生命周期产物，例如：

1. 服务任务临时文件
2. 临时打包目录
3. 一次性调试文件

这类目录可随时清理，不应承载任何需要长期保留的业务状态。

## 是否进 Git

建议按下面执行：

| 路径 | 是否进 Git | 说明 |
| --- | --- | --- |
| `src/` | 是 | 源码 |
| `scripts/` | 是 | 脚本 |
| `docs/` | 是 | 文档 |
| `config/stock_holdings.json` | 是 | 仓库默认 holdings，同时作为本地和容器内统一默认配置 |
| `config/*.example.*` | 是 | 模板 |
| `data/reports/**` | 否 | 运行产物 |
| `data/cache/**` | 否 | 本地缓存 |
| `data/tmp/**` | 否 | 临时文件 |
| `build/**` | 否 | 构建产物 |

## 保留策略

### 报告产物

保留最新即可：

1. `base.json`
2. `fund.json`
3. `overview.txt`
4. `tech.json`
5. `report.txt`
6. `analysis.txt`
7. `advice.txt`
8. `structure.svg`

### 分析中间文件

默认只保留最近一次；如果调试需要，可以放宽到最近 3 次。

推荐默认策略：

1. 每个 `symbol + timeframe` 只保留 `analyze/latest/`
2. 不再保留带时间戳滚动的整套中间 CSV

### 行情缓存

行情缓存不按“最近一次”删，而按“长期可复用资产”管理。

推荐策略：

1. 日线长期保留
2. 60m/30m/15m/5m 也可长期保留，但按时间戳去重
3. 定期做压缩、去重、完整性校验

## 本地与云端的职责划分

### 本地

本地可以保留：

1. 真实持仓配置
2. 可复用行情缓存
3. 最近分析中间文件
4. 最新报告产物

### 云端容器

云端容器不应假定本地磁盘长期可靠。

云端更适合：

1. 启动后即时读取配置
2. 任务执行时生成结果
3. 把最终发布结果上传到 CloudBase / 对象存储
4. 把长期配置和长期缓存放到外部存储

短期内如果云端还没有完整配置中心，最少也应做到：

1. 默认可从 Git 仓库里的 `config/stock_holdings.json` 启动
2. 不依赖 Git 仓库里的 `data/`
3. 不依赖容器本地磁盘保存长期真实 holdings 和历史行情

## 迁移建议

建议分 3 步走，不要一次性大改。

### 第 1 步：先划清边界

1. 保持 `data/` 不进 Git。
2. 新增并提交 `config/stock_holdings.json` 作为仓库默认 holdings。
3. 保留 `config/stock_holdings.example.json` 作为模板或最小示例。
4. 保持 `data/reports/` 继续提供最新报告。

### 第 2 步：压缩中间文件占用

1. 把 `reports/<symbol>/<timeframe>/analyze/` 改成只保留 `latest/`。
2. 增加自动清理逻辑，删除旧的时间戳中间 CSV。
3. 让现有 case 复用逻辑优先读取 `latest/`。

### 第 3 步：单独建设行情缓存

1. 新增 `data/cache/kline/`。
2. 抓取逻辑优先读缓存，不足再补抓。
3. 分析逻辑从缓存切片，而不是直接依赖一次性抓取文件。
4. 后续如有需要，再把缓存从本地迁到对象存储或数据库。

## 对当前代码的最小影响建议

如果只做最小必要调整，优先顺序建议是：

1. 先不要把 `data/` 提交进 Git。
2. 继续把 `data/reports/` 当“最新结果区”。
3. 尽快把 `analyze/` 从“多次历史累积”改成“最近一次覆盖”。
4. 默认图表产物先收敛到 `structure.svg`。
5. 等确实要复用历史 K 线时，再新增 `data/cache/kline/` 和对应缓存逻辑。

这样做的好处是：

1. 先立刻控制磁盘膨胀。
2. 不会把“历史缓存”和“分析中间文件”继续混在一起。
3. 不会为了一个未来可能用到的缓存能力，提前把当前目录变得更复杂。

## 建议的近期决策

短期建议直接采用下面这组结论：

1. `data/` 不进 Git。
2. `config/stock_holdings.json` 作为 repo 和容器内的默认 holdings。
3. `reports/<symbol>/<timeframe>/` 只保留最新对外产物。
4. `reports/<symbol>/<timeframe>/analyze/` 只保留最近一次中间文件。
5. 未来长期历史行情另建 `data/cache/kline/`，不要继续堆在 `analyze/`。

## 当前代码与目标态的差异

当前代码还没有完全迁到这个目标态，至少还有一类存量依赖需要后续代码调整：

1. 一些脚本和路径定义仍会生成或读取 `structure.png` / `structure.jpg`。

所以这份文档现在表达的是目标目录方案，不是“代码已经全部完成迁移”的现状说明。
