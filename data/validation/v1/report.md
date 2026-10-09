# Qwen3.5 训练格式验证

已对 556 条训练数据完成 CPU tokenizer、工具模板和显式训练标签检查。没有下载模型权重或启动训练。

模型：Qwen/Qwen3.5-9B；固定 revision：c202236235762e1c871ad0ccb60c8ee5ba337b9a。

本次 enable_thinking=False。这是格式验证参数，最终训练与推理须使用确认后的相同模式。

所有样本均渲染完整 9 个工具。1840 条 assistant 消息、952 次工具调用均有学习标签；用户、system、工具定义、工具返回、空思考前缀和 padding 不参与损失。

官方模板没有 Jinja generation 标记，因此本项目显式生成 labels，不能仅开启 assistant_only_loss 后假定其有效。

| token 长度 | 最小 | 中位数 | P90 | P95 | 最大 |
|---|---:|---:|---:|---:|---:|
| 全部 | 3068 | 3664.0 | 4545 | 5286 | 6848 |
| home_switch | 3308 | 4106 | 5286 | 6004 | 6848 |
| weather | 3068 | 3485 | 3722 | 3816 | 3941 |

超长样本数：4096 tokens：143 条；8192 tokens：0 条；16384 tokens：0 条。本次没有截断或拼接样本。

rendered-example.txt 展示最长样本真正输入模型的文本；learned-example.txt 仅展示参与学习的 assistant 内容。逐条长度见 token-lengths.jsonl。

这次验证使用本机 CPU tokenizer 环境，尚未验证 Unsloth/TRL 的实际 GPU 数据整理、loss 和显存；后续训练器必须保留这里生成的 labels，并再次检查实际 batch，不能重新覆盖为全量文本损失。
训练服务器的上下文长度和 batch 仍需小规模实测，未在本阶段确定。
