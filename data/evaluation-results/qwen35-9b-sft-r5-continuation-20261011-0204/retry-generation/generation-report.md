# 家居开关对话样本生成报告

运行ID：`home_switch`
System提示词模式：`eval_override`
System提示词 SHA-256：`76a6618cfa39d3a6fca541ffff27e2ccaca65f36c29b9db6b5fb719b57be4009`
对话模型模式：`eval_override`
对话模型：`xiaozhi-sft`

| 指标 | 数量 |
|---|---:|
| 计划种子 | 2 |
| 成功保存 | 1 |
| 失败 | 1 |
| 生成成功率 | 50.0% |

## 错误

- `T16-E001-P2` · `message_trace/incomplete_home_trace`：原始工具返回记录缺失或重复

## 正负分组

{"planned": {"positive": 2}, "completed": {"positive": 1}}

## 实际覆盖

{"templates": {"T16": 1}, "tool_backend": "simulated", "fault_injection": "simulator_records", "scenario_ids": ["HS01", "HS15"]}
