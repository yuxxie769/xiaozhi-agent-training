# 训练脚本本地验证

已确认非思考模式。训练脚本、参数和加载检查入口已编写；Qwen3.5-9B 的 Unsloth/CUDA 试跑待在训练服务器执行。

- 全部 556 条 CPU 预检通过，9 个工具、1,840 条 assistant 消息、952 次工具调用，最长 6,848 tokens。
- 49 项测试通过，包括数据校验、异常隔离、标签和 padding 保真、试跑样本包含每个场景最长轨迹。
- 真实 Transformers Trainer + PyTorch CPU 微型模型完成一次优化，loss 有限、labels 原样进入 forward、参数确有变化。
- 未下载 Qwen 模型权重，未运行 Unsloth GPU 内核，未验证显存、业务效果或适配器重新加载。

本次环境：Python 3.14、PyTorch 2.14.1、Transformers 5.19.0、tokenizers 0.23.2。具体包版本在 environment.json；这是 CPU 验证环境，不是训练服务器的 GPU 锁定配置。

训练默认 BF16 LoRA、8192 上下文、batch 1、梯度累积 8，试跑取 8 条、5 个优化步骤。完整操作见根目录《训练说明.md》。本目录的 run-fingerprint.json 记录实际检查的数据、配置和训练代码校验值。
