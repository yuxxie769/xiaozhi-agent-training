# Qwen3.5 9B 智能助手微调项目

**数据已准备好，训练脚本已编写，下一步到训练服务器预检和试跑。** 已确认非思考模式，使用现有数据即可。

当前产物：

- `data/prepared/train.jsonl`：556 条 SFT 样本，每条包含 messages 和 9 个非 MCP 工具。
- `data/prepared/failed.jsonl`、`review.jsonl`：28 条未通过、15 条待复核。
- `data/evaluation-seeds/v3/`：天气、家居各 60 条测试种子，尚未运行模型评测。
- `train-sft.json`：训练参数；`system-prompt.txt`、`tools.json`：提示词与工具定义。

**只按 [训练说明](训练说明.md) 操作：环境准备 → 预检 → 试跑与加载检查 → 正式训练。现在先做到试跑与加载检查。**

预检使用 `scripts/train_sft.py --mode preflight`，通过后再用同一入口的 `--mode smoke` 试跑。旧的 `validate_training_format.py` 已完成格式验证，正常训练不用再跑；数据和测试种子也不用重新生成。

49 项本地测试通过，包含全量数据预检和微型模型的 Trainer 标签检查。尚未执行 Qwen GPU 训练，显存和模型效果待实测。

项目阶段和数据来源见 [项目总文档](项目总文档.md)；历史格式检查见 [验证报告](data/validation/v1/report.md)。
