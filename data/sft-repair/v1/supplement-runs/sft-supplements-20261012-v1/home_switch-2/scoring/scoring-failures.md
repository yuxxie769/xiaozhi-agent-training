# 家居开关未通过详情

规则：home_switch/1.5；有效评分 20 条；未通过 7 条。

本文件只展示未通过检查项和证据摘录；通过项及完整证据保留在 `scores.json`。

## 评分错误

本批没有评分错误。

## 未通过样本

### T08（1 条未通过）

#### T08-R020-P2

Preset：`study_normal_v1_sft_r1_08`；未通过检查项：HC01、HC02

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 2 | HC01 | 调用场景外工具 | 消息5：切换失败，错误码: 404<br>消息7：{"connected": true, "outdated": false, "highlight": [{"entity_id": "light.bedroom_desk", "n": "卧室台灯", "s": "on"}, {"entity_id": "light.stud… |
| 2 | HC02 | 未知工具 | 消息5：切换失败，错误码: 404<br>消息7：{"connected": true, "outdated": false, "highlight": [{"entity_id": "light.bedroom_desk", "n": "卧室台灯", "s": "on"}, {"entity_id": "light.stud… |

### T17（1 条未通过）

#### T17-R038-P2

Preset：`study_normal_v1_sft_r1_01`；未通过检查项：HC01、HC02

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC01 | 调用场景外工具 | 消息3：切换失败，错误码: 404<br>消息5：{"connected": true, "outdated": false, "highlight": [{"entity_id": "light.study_desk", "n": "书房台灯", "s": "on"}, {"entity_id": "binary_senso… |
| 1 | HC02 | 未知工具 | 消息3：切换失败，错误码: 404<br>消息5：{"connected": true, "outdated": false, "highlight": [{"entity_id": "light.study_desk", "n": "书房台灯", "s": "on"}, {"entity_id": "binary_senso… |
| 2 | HC01 | 不操作轮调用工具；调用场景外工具 | 消息9：退出意图已处理 |
| 2 | HC02 | 未知工具 | 消息9：退出意图已处理 |

### T19（3 条未通过）

#### T19-R044-P2

Preset：`balcony_read_error_recover_v1_sft_r1_05`；未通过检查项：HC01、HC02、HC06

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC01 | 调用场景外工具 | 消息3：{"ok": false, "error": "tool_error", "tool": "state_hub_snapshot", "detail": "isolated view error", "hint": "Continue without calling tools…<br>消息5：切换失败，错误码: 404<br>另有1条 |
| 1 | HC02 | 未知工具 | 消息3：{"ok": false, "error": "tool_error", "tool": "state_hub_snapshot", "detail": "isolated view error", "hint": "Continue without calling tools…<br>消息5：切换失败，错误码: 404<br>另有1条 |
| 1 | HC06 | 答复建议去 Home Assistant 确认设备是否在线，但之前的 hass_get_state 工具返回仅为“切换失败，错误码: 404”，未表明设备离线或需要检查在线状态，属于无依据扩展。 | 消息7：请稍后再让我试一次，或在 Home Assistant 里确认设备是否在线。<br>消息5：切换失败，错误码: 404 |

#### T19-R047-P2

Preset：`balcony_read_error_recover_v1_sft_r1_01`；未通过检查项：HC01、HC02

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC01 | 调用场景外工具 | 消息3：{"ok": false, "error": "tool_error", "tool": "state_hub_snapshot", "detail": "isolated view error", "hint": "Continue without calling tools…<br>消息5：切换失败，错误码: 404<br>另有1条 |
| 1 | HC02 | 未知工具 | 消息3：{"ok": false, "error": "tool_error", "tool": "state_hub_snapshot", "detail": "isolated view error", "hint": "Continue without calling tools…<br>消息5：切换失败，错误码: 404<br>另有1条 |

#### T19-R050-P2

Preset：`balcony_read_error_recover_v1_sft_r1_01`；未通过检查项：HC01、HC02、HC06

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC01 | 调用场景外工具 | 消息3：{"ok": false, "error": "tool_error", "tool": "state_hub_snapshot", "detail": "isolated view error", "hint": "Continue without calling tools…<br>消息5：切换失败，错误码: 404<br>另有1条 |
| 1 | HC02 | 未知工具 | 消息3：{"ok": false, "error": "tool_error", "tool": "state_hub_snapshot", "detail": "isolated view error", "hint": "Continue without calling tools…<br>消息5：切换失败，错误码: 404<br>另有1条 |
| 1 | HC06 | 工具仅返回快照 tool_error（isolated view error）和 hass_get_state 404 切换失败，未给出设备在线状态或 Home Assistant 侧问题的依据；答复却让用户去检查这两个设备在 Home Assistant 里是否在线，把读取失败扩展为设备可能离线，超出可见证据。 | 消息7：也可以先检查一下这两个设备在 Home Assistant 里是否在线<br>消息3：isolated view error<br>另有1条 |
| 2 | HC01 | 调用场景外工具；控制接受或效果未知后未读取 | 消息10：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>消息12：设备已打开<br>另有1条 |
| 2 | HC02 | 未知工具 | 消息10：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>消息12：设备已打开<br>另有1条 |

### T20（2 条未通过）

#### T20-R056-P2

Preset：`balcony_second_device_error_v1_sft_r1_05`；未通过检查项：HC01、HC02

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC01 | 调用场景外工具 | 消息3：切换失败，错误码: 404<br>消息5：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>另有1条 |
| 1 | HC02 | 未知工具 | 消息3：切换失败，错误码: 404<br>消息5：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>另有1条 |

#### T20-R059-P2

Preset：`balcony_second_device_error_v1_sft_r1_03`；未通过检查项：HC06

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 2 | HC06 | 答复把403解释为“临时的权限/连接抖动”，但此前hass_set_state仅返回错误码403，未提供权限或连接抖动依据，属于无据推断。 | 消息14：刚才那次 403 应该是临时的权限/连接抖动，现在执行正常。<br>消息5：设置失败，错误码: 403 |

