# Qwen3.5 9B 智能助手微调项目

**SFT 训练数据集已生成，Qwen3.5-9B 适配预检脚本已准备，待训练服务器执行。** 详细进度见 [项目总文档](项目总文档.md)。

现有 599 条源轨迹，已生成 **556 条 SFT 训练数据**，另存 28 条未通过、15 条待复核。未通过样本可能用于后续 DPO rejected，当前不做适用性评估或配对。尚未开始训练。

- `data/prepared/train.jsonl`：完整 messages 与统一的 9 个非 MCP 工具；下一阶段直接用于训练适配验证。
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

导出不会调用模型或设备。不从元数据添加日期、时区；保留原 system 的可见设备目录，所有样本统一使用根目录 tools.json 的 9 个非 MCP 工具；tools-source.json 记录来源。Qwen3.5 模板、token 长度与 assistant 损失掩码由 `scripts/validate_qwen35_adapter.py` 在训练服务器验证。

测试种子生成已接入数据准备结果，已输出天气 60 条、家居 60 条到 `data/evaluation-seeds/v2/`。重新生成时使用尚不存在的新目录：

```bash
python3 scripts/generate_evaluation_seeds.py \
  --config config.json \
  --prepared-dir data/prepared \
  --output-dir data/evaluation-seeds/v3 \
  --random-seed 20261009
```

评估规模默认读取 `config.evaluation_seed_fraction`，与训练数据划分无关。生成器读取 inventory、audit 和训练集清单，默认按实际导出的 556 条训练数据计算模板比例，排除与全部 599 条源种子重合的语义变量组。上游文件不匹配时拒绝生成。相同文案但语义变量不同可保留，并在报告中统计。种子 v2 已绑定当前完整工具列表，模型评测也须使用这份列表。测试种子是任务定义，尚未运行模型。详细说明见 [评估种子生成器](evaluation/seed_generation/README.md)。

模型固定为官方指令模型 `Qwen/Qwen3.5-9B@c202236235762e1c871ad0ccb60c8ee5ba337b9a`，硬件为用户确认的单卡 32GB 实际显存。训练框架为 Unsloth + TRL，统一关闭思考模式；具体依赖版本与训练参数由服务器预检和显存实测决定。

训练服务器预检（只下载 Processor/tokenizer，不加载模型权重）：

```bash
python3 scripts/validate_qwen35_adapter.py \
  --dataset data/prepared/train.jsonl \
  --output data/adapter-validation/qwen35-9b-c202236.json
```

预检会逐条渲染 `messages + tools`，检查 assistant-only loss 掩码，并统计完整 token 长度。报告通过后再编写和执行小规模训练脚本。
