# Qwen3.5 9B 智能助手微调项目

**数据、GPU 环境、小规模试跑和适配器重载均已通过；下一步补齐后端原模型基线，再开始正式 SFT。** 已确认非思考模式，使用现有数据即可。

当前产物：

- `data/prepared/train.jsonl`：556 条 SFT 样本，每条包含 messages 和 9 个非 MCP 工具。
- `data/prepared/failed.jsonl`、`review.jsonl`：28 条未通过、15 条待复核。
- `data/evaluation-seeds/v3/`：天气、家居各 60 条测试种子，尚未运行模型评测。
- `train-sft.json`：训练参数；`system-prompt.txt`、`tools.json`：提示词与工具定义。

按 [训练说明](训练说明.md) 操作：**准备环境 → 步骤 6 格式验证 → 原模型基线评测 → 试跑与加载检查 → 正式训练 → SFT 复测。**

格式验证结果在 `data/validation/v3/`；GPU 试跑使用本地 `/autodl-fs/data/qwen3.5-9b`，成功运行 5 个优化步骤并完成重载生成。训练入口的 `preflight` 不能替代完整格式验证。正式训练仍必须等原模型基线完成。

50 项本地测试通过。GPU smoke 最长覆盖 6,848 tokens，labels 保持不变，248 个 LoRA 目标层全部对齐；最终平均 loss 0.6929，峰值保留显存 19.04 GiB。这不代表业务评测通过。

项目阶段和数据来源见 [项目总文档](项目总文档.md)；当前格式检查见 [验证报告](data/validation/v3/report.md)。

业务评测计划复用后端生成与评分链路，结果继续放在后端 `main/xiaozhi-server/tmp/` 的新批次目录。当前后端 checkout 只有天气评测入口；家居链路、完整 9 工具和固定环境对齐尚待实现，见 [项目总文档第 7 节](项目总文档.md#7-原模型基线评测试跑与正式训练)。
