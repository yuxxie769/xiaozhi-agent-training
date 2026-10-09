# 数据准备报告

状态：离线筛选及统一输入候选已完成；尚未验证目标 Qwen 聊天模板和统一提示词下的行为。

原始轨迹：599；SFT train：444；SFT validation：107；DPO 待配对：33；待复核：15。

| 场景 | 分类 | 数量 |
|---|---|---:|
| home_switch | dpo_review_candidate:train | 8 |
| home_switch | dpo_review_candidate:validation | 3 |
| home_switch | quarantine:train | 9 |
| home_switch | quarantine:validation | 6 |
| home_switch | sft_candidate:train | 222 |
| home_switch | sft_candidate:validation | 51 |
| weather | dpo_review_candidate:train | 18 |
| weather | dpo_review_candidate:validation | 4 |
| weather | sft_candidate:train | 222 |
| weather | sft_candidate:validation | 56 |

## 评分选择

- weather：保留城市名逐字一致的原评分，与当前工具说明及目标提示词一致；不使用放宽城市名后的评分。
- home_switch：使用已按当前规则重新计算程序检查并选择性复评的版本，允许相邻上一轮同设备可用状态复用。

## 训练前剩余检查

- 选定 Qwen checkpoint，渲染工具调用聊天模板，验证 assistant-only token labels；messages JSONL 本身不实现损失屏蔽。
- 在统一提示词及三个工具同时可见的环境下重评，并增加跨场景组合样本。
- validation 按模板及相同完整用户序列隔离，属于开发验证集；最终测试必须另行收集并锁定。
- DPO review 仅存失败候选及证据，必须在相同历史下补充正确候选并复核。
- 运行器插入的限次提示未被删除后冒充普通对话；相关轨迹保留在原文件，并记录到 quarantine。
