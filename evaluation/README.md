# 评分规则与实现

天气和家居均使用最新修订规则。本目录复用原 server 的评分实现，不另建一套判断标准。数据准备时读取已有评分并检查样本、检查项和证据；训练后模型评测需要另接模型运行入口和语义评分调用入口，目前尚未实现。

- `weather_scoring.py`、`home_switch_scoring.py`、`eval_scoring.py`：原评分逻辑副本。
- `home_switch_seeds.py`、`home-switch-templates.json`：独立验证所需的模板和种子检查。
- `weather-tool.json`：从原天气工具定义恢复的契约，城市名说明已与最新评分统一，允许省略末尾“市”；不是历史工具快照。其他参数保持不变。
- `LICENSE.server`：所复用代码的原许可证。

原始来源与迁移记录保存在 `archive/before-simplification/migration-manifest.json`；原始天气源码和目录变更前副本也在同一归档目录内。

更新规则时应明确同步版本，记录变化，重新评估受影响样本。训练与测试模型使用相同规则，不能为了某个模型的输出另放宽一套标准。
