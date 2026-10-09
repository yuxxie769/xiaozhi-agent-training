# 数据准备报告

状态：离线筛选及统一输入候选已完成；尚未验证目标 Qwen 聊天模板和统一提示词下的行为。

原始轨迹：599；训练候选：447；测试候选：109；未通过样本：28；待复核：15。

| 场景 | 分类 | 数量 |
|---|---|---:|
| home_switch | failed_sample:test | 3 |
| home_switch | failed_sample:train | 8 |
| home_switch | passed_sample:test | 51 |
| home_switch | passed_sample:train | 222 |
| home_switch | quarantine:test | 6 |
| home_switch | quarantine:train | 9 |
| weather | failed_sample:test | 2 |
| weather | failed_sample:train | 15 |
| weather | passed_sample:test | 58 |
| weather | passed_sample:train | 225 |

## 评分选择

- weather：使用已修订的最新评分版本。
- home_switch：使用已修订的最新评分版本。

## 训练前剩余检查

- 选定 Qwen checkpoint，渲染工具调用聊天模板，验证 assistant-only token labels；messages JSONL 本身不实现损失屏蔽。
- 在统一提示词及三个工具同时可见的环境下重评，并增加跨场景组合样本。
- test 按模板及相同完整用户序列隔离，属于开发测试集；最终测试必须另行收集并锁定。
- failed 文件统一保存未通过样本；可能可用于后续 DPO rejected，当前不做配对或适用性评估。
- 运行器插入的限次提示未被删除后冒充普通对话；相关轨迹保留在原文件，并记录到 review.jsonl。
