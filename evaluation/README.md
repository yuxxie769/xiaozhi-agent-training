# 评分规则与实现

天气和家居均使用最新修订规则。本目录复用原 server 的评分实现，不另建一套判断标准。数据准备时读取已有评分并检查样本、检查项和证据；原模型基线和 SFT 后评测复用后端已有生成器、工具环境和评分调用。本项目仅规划调用入口；完整工具与固定测试环境尚待对齐，详见项目总文档第 7 节。结果继续保存在后端 tmp 批次目录，不在本项目另建业务评测链路。

- `weather_scoring.py`、`home_switch_scoring.py`、`eval_scoring.py`：原评分逻辑副本。
- `home_switch_seeds.py`、`home-switch-templates.json`：独立验证所需的模板和种子检查。
- `weather-tool.json`：从原天气工具定义恢复的契约，城市名说明已与最新评分统一，允许省略末尾“市”；不是历史工具快照。其他参数保持不变。
- `LICENSE.server`：所复用代码的原许可证。

原始来源与迁移记录保存在 `archive/before-simplification/migration-manifest.json`；原始天气源码和目录变更前副本也在同一归档目录内。

更新规则时应明确同步版本，记录变化，重新评估受影响样本。训练与测试模型使用相同规则，不能为了某个模型的输出另放宽一套标准。
