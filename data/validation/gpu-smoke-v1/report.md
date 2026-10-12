# Qwen3.5-9B GPU smoke 报告

状态：**训练、保存、适配器重载和最小生成均通过。** 这是训练链路验证，不是业务评测。

## 环境与底座

- GPU：NVIDIA GeForce RTX 4080 SUPER，31.475 GiB；驱动 595.71.05。
- Python 3.12.3；torch 2.8.0+cu128；Transformers 5.17.0；Unsloth/Unsloth Zoo 2026.10.3。
- xFormers 0.0.32.post2；TorchAO 0.13.0；PEFT 0.21.2；bitsandbytes 0.50.2。
- 底座：`Qwen/Qwen3.5-9B`，项目固定 revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`。
- 本地目录：`/autodl-fs/data/qwen3.5-9b`；config、tokenizer 和聊天模板与 `tokenizer/snapshot.json` 的 SHA-256 一致。
- 权重索引 SHA-256：`26d3539b516be613f39563617cb9d33b3f83d401298125be392c80cefb8f7fe5`；4 个分片的字节数和 SHA-256 均与 Hugging Face 固定 revision 官方 LFS 元数据一致。

## 试跑配置与结果

- 运行目录：本地 `runs/smoke-02/`（已被 `.gitignore` 排除）。
- 数据：8 条，包含家居最长 6,848 tokens 和天气最长 3,941 tokens 轨迹。
- 配置：BF16 LoRA，rank/alpha 16/16，batch 1，梯度累积 8，5 个优化步骤，上下文 8,192。
- LoRA：248 个显式语言线性层与 248 个实际挂载层完全一致；43,278,336 个可训练参数，占 0.4810%。
- 第一个真实 Trainer batch：`labels_preserved=true`，139 个 supervised tokens。
- 每步 loss：0.8152、0.8152、0.6958、0.5979、0.5402；最终平均 loss 0.6928563595。
- 峰值显存：allocated 18.884 GiB；reserved 19.039 GiB。
- 适配器权重 SHA-256：`9a21fe2704e2d55ccb4f395097fa06abd5d272b14f56a110af8087cdcc87fc19`。
- 重载检查：`adapter_reload_verified=true`，显式非思考，3,073 个输入 tokens，确定性生成成功；未执行工具。

## 试跑中发现并修复

1. 最新 xFormers 会将服务器现有 torch 2.8/CUDA 12.8 强制替换为 torch 2.14/CUDA 13；已固定为与 torch 2.8 匹配的 0.0.32.post2。
2. TorchAO 0.18 在 torch 2.8 上会导致 Transformers 模型导入失败；已固定为 0.13.0。本项目的 BF16 LoRA 不使用 TorchAO 量化。
3. 首次 `runs/smoke-01/` 在优化前被 Unsloth 的新模态筛选拒绝，没有更新参数。入口现使用完整语言层路径并在注入后反查全部 LoRA 层；`smoke-02` 通过。
4. 未安装 `causal_conv1d`，Qwen3.5 线性注意力使用正确但较慢的 PyTorch 回退实现。不影响本次正确性结论，正式训练前可再决定是否安装优化内核。

## 未完成

原模型 120 条业务基线、全量 SFT 和同条件复测尚未执行。当前后端 checkout 仅有天气评测入口，家居评测、完整 9 工具环境和固定天气回放仍需接入。
