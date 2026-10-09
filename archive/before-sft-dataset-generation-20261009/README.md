# Qwen3.5 9B 智能助手微调项目

先看 [项目总文档](项目总文档.md)。本项目负责源数据评估、划分、统一提示词、训练与测试数据提取、训练及模型评测。

- `config.json`：模型、数据来源和划分配置。
- `system-prompt.txt`：统一提示词草稿。
- `data/raw`：原始轨迹和最新修订评分。
- `data/prepared`：当前训练、测试、未通过和待复核结果。
- `scripts`：已实现数据准备；训练与模型评测入口后续加入。
- `evaluation`：复用 server 的评分逻辑，独立运行，不另写一套标准。
- `evaluation/seed_generation`：原模板种子生成逻辑及只读 preset 快照适配器。
- `archive`：旧资料，日常不需要看。

现有 599 条源轨迹，导出 447 条训练候选、109 条测试候选、28 条未通过样本、15 条待复核。未通过样本可能用于后续 DPO rejected，当前不做评估或配对。尚未开始训练。

自检只需 Python 3.10+ 标准库：

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

需要重跑时输出到尚不存在的目录，避免覆盖当前结果：

```bash
python3 scripts/prepare_training_data.py --config config.json --output-dir data/prepared-next
```

模型为 Qwen3.5-9B，用户已确认单卡 32GB 实际显存；训练环境和具体参数后续确认。

按当前评分结果的模板比例生成一批新评估种子，并自动排除与全部源种子语义重合的变量组：

```bash
python3 scripts/generate_evaluation_seeds.py \
  --config config.json \
  --output-dir data/evaluation-seeds/v1 \
  --random-seed 20261009
```

评估规模默认读取 `config.test_fraction`。生成报告会保存模板配额、碰撞数量、源文件哈希和输出哈希；输出目录已存在时拒绝覆盖。
