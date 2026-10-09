# Qwen3.5 9B 智能助手微调项目

请先阅读 [项目总文档](项目总文档.md)。它说明当前进度、已落地文件、每个训练阶段和需要确认的决定。

- 模型：Qwen3.5-9B；框架方向：Unsloth；路线：SFT → DPO。
- 硬件：用户确认的单卡 32GB 实际显存。
- 当前状态：已有 599 条来源轨迹及候选试导出，尚未开始训练。
- 原始数据、评分和所需验证代码已独立保存，不需要原 agent server。
- `archive` 是历史记录；`data/candidates/v0` 是未定稿的试导出结果。

查看 [迁移说明](docs/迁移说明.md) 和 [迁移验证记录](docs/迁移验证记录.json)。离线单元测试可运行：

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

规则确认后，可用以下命令导出到一个尚不存在的新目录；现在无需执行：

```bash
python3 scripts/prepare_training_data.py --config configs/data-v1.json --output-dir data/candidates/v1
```

当前只需 Python 标准库运行离线准备与测试。GPU 训练依赖、Qwen3.5 tokenizer 和训练脚本尚待确认后适配。
