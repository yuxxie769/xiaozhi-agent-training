# 家居开关对话样本生成报告

运行ID：`home_switch`
System提示词模式：`eval_override`
System提示词 SHA-256：`76a6618cfa39d3a6fca541ffff27e2ccaca65f36c29b9db6b5fb719b57be4009`
对话模型模式：`eval_override`
对话模型：`xiaozhi-sft`

| 指标 | 数量 |
|---|---:|
| 计划种子 | 17 |
| 成功保存 | 15 |
| 失败 | 2 |
| 生成成功率 | 88.2% |

## 错误

- `T16-E001-P2` · `message_trace/incomplete_home_trace`：原始工具返回记录缺失或重复
- `T16-E001-P3` · `message_trace/incomplete_home_trace`：原始工具返回记录缺失或重复

## 正负分组

{"planned": {"positive": 5, "negative": 12}, "completed": {"positive": 3, "negative": 12}}

## 实际覆盖

{"templates": {"T15": 2, "T16": 1, "T17": 3, "T18": 3, "T19": 3, "T20": 3}, "tool_backend": "simulated", "fault_injection": "simulator_records", "scenario_ids": ["HS01", "HS03", "HS04", "HS05", "HS06", "HS07", "HS08", "HS09", "HS10", "HS12", "HS14", "HS15"]}
