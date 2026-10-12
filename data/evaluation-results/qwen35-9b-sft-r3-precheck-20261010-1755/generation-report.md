# 家居开关对话样本生成报告

运行ID：`qwen35-9b-sft-r3-precheck-20261010-1755`
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

- `T06-E001-P2` · `model_request/model_response_error`：对话模型服务响应异常

## 正负分组

{"planned": {"positive": 2}, "completed": {"positive": 1}}

## 实际覆盖

{"templates": {"T03": 1}, "tool_backend": "simulated", "fault_injection": "simulator_records", "scenario_ids": ["HS01", "HS02", "HS05", "HS12"]}
