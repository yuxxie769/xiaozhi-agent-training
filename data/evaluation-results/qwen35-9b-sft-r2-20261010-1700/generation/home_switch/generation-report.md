# 家居开关对话样本生成报告

运行ID：`home_switch`
System提示词模式：`eval_override`
System提示词 SHA-256：`76a6618cfa39d3a6fca541ffff27e2ccaca65f36c29b9db6b5fb719b57be4009`
对话模型模式：`eval_override`
对话模型：`xiaozhi-sft`

| 指标 | 数量 |
|---|---:|
| 计划种子 | 60 |
| 成功保存 | 47 |
| 失败 | 13 |
| 生成成功率 | 78.3% |

## 错误

- `T03-E001-P1` · `model_request/model_response_error`：对话模型服务响应异常
- `T06-E001-P2` · `model_request/model_response_error`：对话模型服务响应异常
- `T06-E001-P3` · `model_request/model_response_error`：对话模型服务响应异常
- `T07-E001-P2` · `model_request/model_response_error`：对话模型服务响应异常
- `T08-E001-P3` · `model_request/model_response_error`：对话模型服务响应异常
- `T09-E001-P2` · `message_trace/incomplete_home_trace`：用户轮次没有可见答复
- `T10-E001-P2` · `model_request/model_response_error`：对话模型服务响应异常
- `T10-E001-P3` · `model_request/model_response_error`：对话模型服务响应异常
- `T13-E001-P2` · `model_request/model_response_error`：对话模型服务响应异常
- `T14-E001-P1` · `model_request/model_response_error`：对话模型服务响应异常
- `T14-E001-P2` · `model_request/model_response_error`：对话模型服务响应异常
- `T14-E001-P3` · `model_request/model_response_error`：对话模型服务响应异常
- `T16-E001-P3` · `message_trace/incomplete_home_trace`：原始工具返回记录缺失或重复

## 正负分组

{"planned": {"positive": 48, "negative": 12}, "completed": {"positive": 35, "negative": 12}}

## 实际覆盖

{"templates": {"T01": 3, "T02": 3, "T03": 2, "T04": 3, "T05": 3, "T06": 1, "T07": 2, "T08": 2, "T09": 2, "T10": 1, "T11": 3, "T12": 3, "T13": 2, "T15": 3, "T16": 2, "T17": 3, "T18": 3, "T19": 3, "T20": 3}, "tool_backend": "simulated", "fault_injection": "simulator_records", "scenario_ids": ["HS01", "HS02", "HS03", "HS04", "HS05", "HS06", "HS07", "HS08", "HS09", "HS10", "HS11", "HS12", "HS13", "HS14", "HS15"]}
