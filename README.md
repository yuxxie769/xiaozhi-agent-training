# Qwen3.5 9B 智能助手微调项目

**数据已准备好，训练脚本已编写，下一步接入后端原模型基线评测，再推进训练试跑。** 已确认非思考模式，使用现有数据即可。

当前产物：

- `data/prepared/train.jsonl`：556 条 SFT 样本，每条包含 messages 和 9 个非 MCP 工具。
- `data/prepared/failed.jsonl`、`review.jsonl`：28 条未通过、15 条待复核。
- `data/evaluation-seeds/v3/`：天气、家居各 60 条测试种子，尚未运行模型评测。
- `train-sft.json`：训练参数；`system-prompt.txt`、`tools.json`：提示词与工具定义。

按 [训练说明](训练说明.md) 操作：**准备环境 → 步骤 6 格式验证 → 原模型基线评测 → 试跑与加载检查 → 正式训练 → SFT 复测。**

先运行 `scripts/validate_training_format.py`，检查报告和输入/学习内容预览；通过后先完成原模型基线，再运行 `scripts/train_sft.py --mode smoke`。步骤 6 是必要步骤，训练入口的 `preflight` 不能替代步骤 6。`smoke` 自带训练配置检查，单独的 `preflight` 仅供排查时使用。数据和测试种子沿用现有版本。

49 项本地测试通过，包含全量数据预检和微型模型的 Trainer 标签检查。尚未执行 Qwen GPU 训练，显存和模型效果待实测。

项目阶段和数据来源见 [项目总文档](项目总文档.md)；历史格式检查见 [验证报告](data/validation/v1/report.md)。

业务评测计划复用后端已有生成与评分链路，本项目只提供调用入口，结果继续放在后端 `main/xiaozhi-server/tmp/` 的新批次目录。入口及完整工具/固定环境对齐尚待实现，见 [项目总文档第 7 节](项目总文档.md#7-原模型基线评测试跑与正式训练)。
