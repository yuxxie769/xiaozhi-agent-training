# Qwen3.5 9B 智能助手微调项目

**SFT 数据已生成，CPU 格式与标签检查通过；GPU 训练器接入待完成。** 详细进度见 [项目总文档](项目总文档.md)。

现有 599 条源轨迹，已生成 **556 条 SFT 训练数据**，另存 28 条未通过、15 条待复核。未通过样本可能用于后续 DPO rejected，当前不做适用性评估或配对。尚未开始训练。

- `data/prepared/train.jsonl`：完整 messages 与统一的 9 个非 MCP 工具；已完成 CPU 格式和标签验证。
- `data/prepared/inventory.json`、`report.md`：仅盘点来源与数量、任务覆盖、对话结构。
- `data/prepared/failed.jsonl`、`review.jsonl`：未通过与待复核记录。
- `config.json`、`system-prompt.txt`：模型、来源、评估种子规模及统一提示词。
- `data/raw`：原始轨迹与最新评分；`evaluation`：独立复用的评分与种子生成依赖。
- `archive`：旧版本。源数据不划分测试集，测试任务由评估种子生成器负责。

只需 Python 3.10+ 标准库。自检：

```bash
python3 -B -m unittest discover -s tests -p 'test_*.py'
```

重新生成训练数据集时，输出到尚不存在的目录：

```bash
python3 -B scripts/prepare_training_data.py --config config.json --output-dir data/prepared-next
```

导出不会调用模型或设备。不从元数据添加日期、时区；保留原 system 的可见设备目录，所有样本统一使用根目录 tools.json 的 9 个非 MCP 工具；tools-source.json 记录来源。已用固定 Qwen3.5 tokenizer 验证全量模板、长度和显式 labels，尚未验证 GPU 训练。

测试种子生成已接入数据准备结果，已输出天气 60 条、家居 60 条到 `data/evaluation-seeds/v3/`。重新生成时使用尚不存在的新目录：

```bash
python3 scripts/generate_evaluation_seeds.py \
  --config config.json \
  --prepared-dir data/prepared \
  --output-dir data/evaluation-seeds/v4 \
  --random-seed 20261009
```

评估规模默认读取 `config.evaluation_seed_fraction`，与训练数据划分无关。生成器读取 inventory、audit 和训练集清单，默认按实际导出的 556 条训练数据计算模板比例，排除与全部 599 条源种子重合的语义变量组。上游文件不匹配时拒绝生成。相同文案但语义变量不同可保留，并在报告中统计。种子 v3 已绑定当前提示词与完整工具列表，模型评测也须使用这份列表。测试种子是任务定义，尚未运行模型。详细说明见 [评估种子生成器](evaluation/seed_generation/README.md)。

模型为 Qwen3.5-9B，硬件为用户确认的单卡 32GB 实际显存。具体模型版本、训练环境及参数后续确认。

抽查了 14 条代表性轨迹，修正了“禁止 Markdown”与原回答的风格冲突，保留原始回答。完整验证报告见 [CPU 格式验证](data/validation/v1/report.md)。最长样本 6,848 tokens，8,192 可容纳全部数据；实际训练显存待测。思考模式尚待确认，本次按非思考模式进行 CPU 验证。

`tokenizer/` 只保存固定版本 tokenizer、模板和配置；`scripts/training_format.py` 生成显式 assistant 标签，`scripts/validate_training_format.py` 负责全量检查。标准库自检会跳过需要 Transformers 的测试；41 项全量测试是在 tokenizer 环境运行通过的。验证环境使用 Transformers 4.57.6、tokenizers 0.22.2、Jinja2 3.1.6，不能据此认定这些版本已适配 GPU 模型训练。
