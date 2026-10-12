# Qwen3.5 9B 智能助手微调项目

<<<<<<< Updated upstream
**数据、GPU 环境、小规模试跑和适配器重载均已通过；下一步补齐后端原模型基线，再开始正式 SFT。** 已确认非思考模式，使用现有数据即可。
=======
**最新 SFT 复测部分完成：71/107 条通过，另有 13 条生成异常。服务已恢复，下一步解决仍为 8192 的上下文限制，再补齐完整评测。**
>>>>>>> Stashed changes

当前产物：

- `data/prepared/train.jsonl`：556 条 SFT 样本，每条包含 messages 和 9 个非 MCP 工具。
- `data/prepared/failed.jsonl`、`review.jsonl`：28 条未通过、15 条待复核。
- `data/evaluation-seeds/v3/`：天气、家居各 60 条测试种子，已完成原模型基线评测。
- `train-sft.json`：训练参数；`system-prompt.txt`、`tools.json`：提示词与工具定义。

按 [训练说明](训练说明.md) 操作：**准备环境 → 步骤 6 格式验证 → 原模型基线评测 → 试跑与加载检查 → 正式训练 → SFT 复测。**

格式验证结果在 `data/validation/v3/`；GPU 试跑使用本地 `/autodl-fs/data/qwen3.5-9b`，成功运行 5 个优化步骤并完成重载生成。训练入口的 `preflight` 不能替代完整格式验证。正式训练仍必须等原模型基线完成。

<<<<<<< Updated upstream
50 项本地测试通过。GPU smoke 最长覆盖 6,848 tokens，labels 保持不变，248 个 LoRA 目标层全部对齐；最终平均 loss 0.6929，峰值保留显存 19.04 GiB。这不代表业务评测通过。
=======
55 项本地测试通过，包含数据预检、Trainer 标签检查及评测入口的报告回传和失败处理。用户已在外部服务器加载 SFT 接口，本任务已完成业务复测；GPU 训练日志、显存和实际加载权重尚未核验。
>>>>>>> Stashed changes

项目阶段和数据来源见 [项目总文档](项目总文档.md)；当前格式检查见 [验证报告](data/validation/v3/report.md)。

<<<<<<< Updated upstream
业务评测计划复用后端生成与评分链路，结果继续放在后端 `main/xiaozhi-server/tmp/` 的新批次目录。当前后端 checkout 只有天气评测入口；家居链路、完整 9 工具和固定环境对齐尚待实现，见 [项目总文档第 7 节](项目总文档.md#7-原模型基线评测试跑与正式训练)。
=======
业务评测使用 `scripts/run_backend_evaluation.py` 调用后端已有生成与评分链路。完整结果保存在后端 `tmp/model-eval-runs/<批次ID>/`，报告返回本项目 `data/evaluation-results/<批次ID>/`。原模型基线已完成：天气 32/60、家居 3/60，总体 35/120（29.2%），运行错误 0；[查看报告](data/evaluation-results/qwen35-9b-baseline-20261010-1127/scoring-report.md)。复测命令见 [项目总文档第 7 节](项目总文档.md#7-原模型基线评测试跑与正式训练)。

SFT 复测：天气 27/60、家居 2/60，总体 29/120（24.2%），运行错误 0。[三组对比](data/evaluation-results/comparison-20261010.md)。文字客户端 deepseek-flash：天气 58/60、家居 41/60，总体 99/120（82.5%），运行错误 0。

[调整后 SFT 第二次复测](data/evaluation-results/comparison-20261010-sft-r2.md)：天气 44/60、家居 27/47；同一批有效任务较首次 SFT 改善，完成率为 89.2%。
>>>>>>> Stashed changes
