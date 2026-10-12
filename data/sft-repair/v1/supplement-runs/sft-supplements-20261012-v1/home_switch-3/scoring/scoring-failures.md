# 家居开关未通过详情

规则：home_switch/1.5；有效评分 20 条；未通过 7 条。

本文件只展示未通过检查项和证据摘录；通过项及完整证据保留在 `scores.json`。

## 评分错误

本批没有评分错误。

## 未通过样本

### T06（1 条未通过）

#### T06-R006-P3

Preset：`balcony_normal_v1_sft_r1_02`；未通过检查项：HC01、HC02

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC01 | 超过本轮工具次数预算；调用场景外工具 | 消息3：切换失败，错误码: 404<br>消息5：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>另有2条 |
| 1 | HC02 | 未知工具 | 消息3：切换失败，错误码: 404<br>消息5：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>另有2条 |

### T11（1 条未通过）

#### T11-R036-P3

Preset：`mixed_normal_v1_sft_r1_01`；未通过检查项：HC06

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC06 | 答复将“阳台植物灯（植物灯）”列为“可选的插座”，但先前system目录中该设备名称与别名均不含“插座”；“可选的插座有”未覆盖该列表项，属事实错误。 | 消息2：4. **阳台植物灯**（植物灯）<br>消息0：{"entity_id": "switch.balcony_grow", "name": "阳台植物灯", "aliases": ["植物灯"], "room": "阳台", "controllable": true} |

### T19（2 条未通过）

#### T19-R045-P3

Preset：`balcony_read_error_recover_v1_sft_r1_07`；未通过检查项：HC01、HC02、HC06

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC01 | 调用场景外工具 | 消息3：{"ok": false, "error": "tool_error", "tool": "state_hub_snapshot", "detail": "isolated view error", "hint": "Continue without calling tools…<br>消息5：切换失败，错误码: 404 |
| 1 | HC02 | 未知工具 | 消息3：{"ok": false, "error": "tool_error", "tool": "state_hub_snapshot", "detail": "isolated view error", "hint": "Continue without calling tools…<br>消息5：切换失败，错误码: 404 |
| 1 | HC06 | 工具返回显示切换失败，说明已发出开关命令并失败；答复却称没有发出开关命令，属于把未确认/失败说成确定未执行，与可见工具结果矛盾。 | 消息6：所以没有发出开关命令<br>消息5：切换失败，错误码: 404 |

#### T19-R048-P3

Preset：`balcony_offline_recover_v1_sft_r1_07`；未通过检查项：HC01、HC02

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC01 | 调用场景外工具 | 消息3：{"connected": false, "outdated": true, "highlight": [], "fields": {"connected": "Whether the connection with Home Assistant has been establ…<br>消息5：切换失败，错误码: 404 |
| 1 | HC02 | 未知工具 | 消息3：{"connected": false, "outdated": true, "highlight": [], "fields": {"connected": "Whether the connection with Home Assistant has been establ…<br>消息5：切换失败，错误码: 404 |

### T20（3 条未通过）

#### T20-R054-P3

Preset：`balcony_timeout_applied_v1_sft_r1_02`；未通过检查项：HC01、HC02

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC01 | 超过本轮工具次数预算；调用场景外工具 | 消息3：切换失败，错误码: 404<br>消息5：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>另有2条 |
| 1 | HC02 | 未知工具 | 消息3：切换失败，错误码: 404<br>消息5：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>另有2条 |
| 2 | HC01 | 本轮未出现必需读取 | 消息11：先别重试，告诉我它当前开还是关。 |

#### T20-R057-P3

Preset：`balcony_second_device_error_v1_sft_r1_05`；未通过检查项：HC06

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC06 | 助手建议检查Home Assistant权限设置，将403错误扩展为权限不足，但工具仅返回错误码403，未明确权限原因，属于无依据推断。 | 消息6：或检查一下该设备在 Home Assistant 中的权限设置。<br>消息5：设置失败，错误码: 403 |
| 2 | HC06 | 回复将之前的403拒绝归因为“偶发问题”，但此前工具仅返回“设置失败，错误码: 403”，未提供偶发或临时故障的依据，属于无依据归因。 | 消息14：之前的 403 拒绝应该只是偶发问题<br>消息5：设置失败，错误码: 403 |

#### T20-R060-P3

Preset：`balcony_timeout_applied_v1_sft_r1_04`；未通过检查项：HC01

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 2 | HC01 | 本轮未出现必需读取 | 消息9：先别重试，告诉我它当前开还是关。 |

