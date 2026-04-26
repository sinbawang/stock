# Chanlun Stock Analysis

基于缠论（Chan theory / 缠论）的 Python 股票辅助分析工具。

## 功能

- K 线数据读取与清洗
- 缠论结构识别：分型、笔、线段、中枢
- 信号解释与可视化
- 回测验证框架

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
│   └── chanlun-rule-spec.md    # 规则规格
├── pyproject.toml
├── requirements.txt
└── README.md
```

## 快速开始

```bash
# 安装依赖
pip install -e .

# 运行演示
python src/chanlun/main.py path/to/data.csv

# 运行测试
pytest tests/
```

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

1. 准备样例 K 线 CSV 数据
2. 运行 `reader.py` 验证数据载入
3. 逐个验证规则模块（分型、笔、中枢）
4. 补全测试案例
5. 迭代规则细化

## 第一阶段里程碑

- [ ] 数据结构与读取
- [ ] 包含关系处理
- [ ] 分型识别与去重
- [ ] 笔识别与确认
- [ ] 最小中枢识别
- [ ] 样例可视化与验证

## 许可

MIT
