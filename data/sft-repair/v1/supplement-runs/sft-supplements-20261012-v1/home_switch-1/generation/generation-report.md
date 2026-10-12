# 家居开关对话样本生成报告

运行ID：`generation`
System提示词模式：`eval_override`
System提示词 SHA-256：`76a6618cfa39d3a6fca541ffff27e2ccaca65f36c29b9db6b5fb719b57be4009`
对话模型模式：`eval_override`
对话模型：`deepseek-flash`

| 指标 | 数量 |
|---|---:|
| 计划种子 | 20 |
| 成功保存 | 18 |
| 失败 | 2 |
| 生成成功率 | 90.0% |

## 错误

- `T08-R022-P1` · `message_trace/incomplete_home_trace`：用户轮次与seed不一致
- `T08-R025-P1` · `message_trace/incomplete_home_trace`：用户轮次与seed不一致

## 正负分组

{"planned": {"positive": 12, "negative": 8}, "completed": {"positive": 10, "negative": 8}}

## 实际覆盖

{"templates": {"T04": 2, "T06": 2, "T07": 2, "T08": 1, "T11": 3, "T17": 2, "T19": 3, "T20": 3}, "tool_backend": "simulated", "fault_injection": "simulator_records", "scenario_ids": ["HS01", "HS02", "HS03", "HS04", "HS05", "HS06", "HS08", "HS09", "HS10", "HS12", "HS14"]}
