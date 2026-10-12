# 家居开关未通过详情

规则：home_switch/1.5；有效评分 15 条；未通过 6 条。

本文件只展示未通过检查项和证据摘录；通过项及完整证据保留在 `scores.json`。

## 评分错误

本批没有评分错误。

## 未通过样本

### T15（2 条未通过）

#### T15-E001-P2

Preset：`balcony_normal_v1`；未通过检查项：HC01、HC06

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC01 | 已达目标仍控制 | 消息3：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>消息5：设备已打开<br>另有2条 |
| 2 | HC06 | 回复将书房阅读灯的实体 ID 写成 light.studyreading，但可见工具回读中其实体 ID 为 light.study_reading，该 ID 并非来自可见消息或工具结果。 | 消息17：light.studyreading（书房阅读灯）：关闭，状态为 off<br>消息16：light.study_reading |

#### T15-E001-P3

Preset：`balcony_normal_v1`；未通过检查项：HC01、HC02、HC04

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC01 | 超过本轮工具次数预算；调用场景外工具；已达目标仍控制 | 消息3：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>消息5：设备已打开<br>另有5条 |
| 1 | HC02 | 未知工具 | 消息3：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>消息5：设备已打开<br>另有5条 |
| 1 | HC04 | 工具返回 hass_get_state 错误码 404，但最终回复未解释该错误，仅含糊表示可再询问，未履行解释错误。 | 消息10：切换失败，错误码: 404<br>消息15：若回读中曾见失败码或状态不符，可再询问，我会立刻重查。 |

### T17（1 条未通过）

#### T17-E001-P3

Preset：`balcony_normal_v1`；未通过检查项：HC06

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC06 | 回复举例“楼梯灯”，该设备未在可信设备目录或工具返回状态中出现，属于无据内容。 | 消息8：请告诉我具体是哪一盏（例如：楼梯灯、阳台植物灯），我再执行关闭并回读确认。 |

### T19（2 条未通过）

#### T19-E001-P2

Preset：`balcony_offline_recover_v1`；未通过检查项：HC01

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC01 | 超过本轮工具次数预算 | 消息3：{"connected": false, "outdated": true, "highlight": [], "fields": {"connected": "Whether the connection with Home Assistant has been establ…<br>消息5：{"connected": false, "outdated": true, "highlight": [], "fields": {"connected": "Whether the connection with Home Assistant has been establ…<br>另有2条 |

#### T19-E001-P3

Preset：`balcony_offline_recover_v1`；未通过检查项：HC05、HC06

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC05 | 目标实体应为 light.study_reading，助手写成 switch.study_reading，未按可信目录正确承接设备。 | 消息4：书房阅读灯（switch.study_reading） |
| 1 | HC06 | 回复中的实体ID switch.study_reading 与可信目录 light.study_reading 不符，工具结果也未提供该ID，属无据事实。 | 消息4：书房阅读灯（switch.study_reading） |

### T20（1 条未通过）

#### T20-E001-P3

Preset：`balcony_second_device_error_v1`；未通过检查项：HC01、HC06

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC06 | 回复中“因此当前仍亮着”将开关状态on夸大为电器运行，违反不能把电源开启夸大为电器运行的规定。 | 消息8：回读状态仍为「on」，因此当前仍亮着。 |
| 2 | HC01 | 超过本轮工具次数预算 | 消息11：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>消息13：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>另有3条 |

