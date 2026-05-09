# Chanlun Stock Analysis

基于缠论的股票辅助分析工具，当前主线是先把技术面规则和基本面规则都定义清楚，再按文档分阶段实现。

项目定位是“研究与辅助决策工具”，不是自动荐股器，也不是收益承诺系统。

## 当前重点

当前项目分两条主线推进：

- 技术面：缠论结构识别、结构图导出、规则回归验证
- 基本面：财务快照模型、评分规则、风险标记、与技术面联动的接口设计

在开始写基本面代码前，先冻结文档口径，避免实现过程中频繁返工。

## 文档索引

- [docs/chanlun-rule-spec.md](docs/chanlun-rule-spec.md): 缠论规则规格
- [docs/fundamental-module-spec.md](docs/fundamental-module-spec.md): 基本面模块设计规格
- [docs/fundamental-roadmap.md](docs/fundamental-roadmap.md): 基本面模块落地路线图
- [docs/fundamental-snapshot-example.md](docs/fundamental-snapshot-example.md): 基本面标准输入样例
- [docs/fundamental-v1-minimum-fields.md](docs/fundamental-v1-minimum-fields.md): 基本面第一版最小字段集
- [docs/fundamental-industry-layering.md](docs/fundamental-industry-layering.md): 基本面行业分层规则
- [docs/fundamental-tech-submodels.md](docs/fundamental-tech-submodels.md): 科技行业子模型
- [docs/fundamental-tech-config-draft.md](docs/fundamental-tech-config-draft.md): 科技子模型代码配置草案
- [docs/fundamental-python-model-draft.md](docs/fundamental-python-model-draft.md): 基本面 Python 数据模型草案
- [.github/agents/chanlun-python.agent.md](.github/agents/chanlun-python.agent.md): 项目专用 agent 定义

## 项目结构

```
chanlun-stock/
├── src/
│   └── chanlun/
│       ├── models.py           # 数据结构定义
│       ├── normalize.py        # 包含关系处理
│       ├── fractal.py          # 分型识别
│       ├── bi.py               # 笔识别
│       ├── zhongshu.py         # 中枢识别
│       ├── data/
│       │   ├── reader.py       # K线读取
│       │   └── cleaner.py      # 数据清洗
│       ├── strategy/
│       │   └── signals.py      # 信号定义
│       ├── backtest/
│       │   └── engine.py       # 回测引擎
│       ├── visualization/
│       │   └── plotter.py      # 可视化
│       └── cli.py              # CLI入口
├── tests/
│   ├── test_normalize.py
│   ├── test_fractal.py
│   ├── test_bi.py
│   └── test_zhongshu.py
├── docs/
│   ├── chanlun-rule-spec.md         # 缠论规则规格
│   ├── fundamental-module-spec.md   # 基本面模块规格
│   ├── fundamental-roadmap.md       # 基本面模块路线图
│   ├── fundamental-snapshot-example.md  # 基本面标准输入样例
│   ├── fundamental-v1-minimum-fields.md # 基本面第一版最小字段集
│   ├── fundamental-industry-layering.md # 基本面行业分层规则
│   ├── fundamental-tech-submodels.md    # 科技行业子模型
│   ├── fundamental-tech-config-draft.md # 科技子模型代码配置草案
│   └── fundamental-python-model-draft.md # 基本面 Python 数据模型草案
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

## 后续实现顺序

1. 先实现基本面标准快照模型
2. 再实现评分与风险标记引擎
3. 然后补 CLI 和测试
4. 最后接入数据源与联合分析

## 许可

MIT
