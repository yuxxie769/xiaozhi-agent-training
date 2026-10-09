# Qwen3.5 9B 智能助手微调项目

**SFT 训练数据集已生成，目标模型训练适配待验证。** 详细进度见 [项目总文档](项目总文档.md)。

现有 599 条源轨迹，已生成 **556 条 SFT 训练数据**，另存 28 条未通过、15 条待复核。未通过样本可能用于后续 DPO rejected，当前不做适用性评估或配对。尚未开始训练。

- `data/prepared/train.jsonl`：完整 messages 与逐条 tools；下一阶段直接用于训练适配验证。
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

导出不会调用模型或设备。不从元数据添加日期、时区；保留原 system 的可见设备目录及每条对应的工具定义。Qwen3.5 模板、token 长度与 assistant 损失掩码留待下一阶段验证。

测试种子生成已接入数据准备结果，已输出天气 60 条、家居 60 条到 `data/evaluation-seeds/v1/`。重新生成时使用尚不存在的新目录：

```bash
python3 scripts/generate_evaluation_seeds.py \
  --config config.json \
  --prepared-dir data/prepared \
  --output-dir data/evaluation-seeds/v2 \
  --random-seed 20261009
```

评估规模默认读取 `config.evaluation_seed_fraction`，与训练数据划分无关。生成器读取 inventory、audit 和训练集清单，默认按实际导出的 556 条训练数据计算模板比例，排除与全部 599 条源种子重合的语义变量组。上游文件不匹配时拒绝生成。相同文案但语义变量不同可保留，并在报告中统计。测试种子是任务定义，尚未运行模型。详细说明见 [评估种子生成器](evaluation/seed_generation/README.md)。

模型为 Qwen3.5-9B，硬件为用户确认的单卡 32GB 实际显存。具体模型版本、训练环境及参数后续确认。
