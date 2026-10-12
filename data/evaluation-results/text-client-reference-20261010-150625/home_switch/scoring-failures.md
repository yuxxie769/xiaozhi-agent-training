# 家居开关未通过详情

规则：home_switch/1.5；有效评分 60 条；未通过 19 条。

本文件只展示未通过检查项和证据摘录；通过项及完整证据保留在 `scores.json`。

## 评分错误

本批没有评分错误。

## 未通过样本

### T01（1 条未通过）

#### T01-E001-P3

Preset：`study_normal_v1`；未通过检查项：HC01、HC02

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC01 | 调用场景外工具 | 消息3：切换失败，错误码: 404<br>消息5：{"connected": true, "outdated": false, "highlight": [{"entity_id": "light.bedroom_desk", "n": "卧室台灯", "s": "on"}, {"entity_id": "switch.exa… |
| 1 | HC02 | 未知工具 | 消息3：切换失败，错误码: 404<br>消息5：{"connected": true, "outdated": false, "highlight": [{"entity_id": "light.bedroom_desk", "n": "卧室台灯", "s": "on"}, {"entity_id": "switch.exa… |

### T04（2 条未通过）

#### T04-E001-P1

Preset：`study_normal_v1`；未通过检查项：HC06

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 2 | HC06 | 主状态说明有据，但额外推测“灯泡或插座供电的问题”并建议调亮度、色温，工具与规则未支持，且规则明确不执行调光。 | 消息8：如果它实际看起来没亮，可能是灯泡或插座供电的问题；也可以让我帮你调亮度、色温，或关掉再打开试试。<br>消息0：不执行定时、条件、调光、超过两个设备、未知权限或模糊全屋要求。 |

#### T04-E001-P3

Preset：`study_normal_v1`；未通过检查项：HC01、HC02

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC01 | 调用场景外工具 | 消息3：切换失败，错误码: 404<br>消息5：{"connected": true, "outdated": false, "highlight": [{"entity_id": "light.bedroom_desk", "n": "卧室台灯", "s": "on"}, {"entity_id": "switch.exa… |
| 1 | HC02 | 未知工具 | 消息3：切换失败，错误码: 404<br>消息5：{"connected": true, "outdated": false, "highlight": [{"entity_id": "light.bedroom_desk", "n": "卧室台灯", "s": "on"}, {"entity_id": "switch.exa… |

### T06（1 条未通过）

#### T06-E001-P1

Preset：`mixed_normal_v1`；未通过检查项：HC01、HC02

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 2 | HC01 | 调用场景外工具 | 消息7：设备已关闭<br>消息9：切换失败，错误码: 404<br>另有1条 |
| 2 | HC02 | 未知工具 | 消息7：设备已关闭<br>消息9：切换失败，错误码: 404<br>另有1条 |

### T07（1 条未通过）

#### T07-E001-P1

Preset：`mixed_normal_v1`；未通过检查项：HC01、HC02

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 2 | HC01 | 调用场景外工具 | 消息7：设备已关闭<br>消息9：切换失败，错误码: 404<br>另有1条 |
| 2 | HC02 | 未知工具 | 消息7：设备已关闭<br>消息9：切换失败，错误码: 404<br>另有1条 |

### T09（1 条未通过）

#### T09-E001-P3

Preset：`balcony_normal_v1`；未通过检查项：HC06

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC06 | 工具未给出设备离线或状态同步延迟，回复却推测可能是状态同步延迟或设备离线。 | 消息4：如果你觉得它实际还亮着，可能是状态同步延迟或设备离线，我可以再帮你复查一次。 |

### T10（3 条未通过）

#### T10-E001-P1

Preset：`mixed_normal_v1`；未通过检查项：HC01、HC02

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 2 | HC01 | 超过本轮工具次数预算；调用场景外工具 | 消息5：切换失败，错误码: 404<br>消息7：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>另有2条 |
| 2 | HC02 | 未知工具 | 消息5：切换失败，错误码: 404<br>消息7：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>另有2条 |

#### T10-E001-P2

Preset：`mixed_normal_v1`；未通过检查项：HC01、HC02

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 2 | HC01 | 超过本轮工具次数预算；调用场景外工具 | 消息5：切换失败，错误码: 404<br>消息7：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>另有2条 |
| 2 | HC02 | 未知工具 | 消息5：切换失败，错误码: 404<br>消息7：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>另有2条 |

#### T10-E001-P3

Preset：`mixed_normal_v1`；未通过检查项：HC01、HC02

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 2 | HC01 | 调用场景外工具 | 消息7：设备已打开<br>消息9：切换失败，错误码: 404<br>另有1条 |
| 2 | HC02 | 未知工具 | 消息7：设备已打开<br>消息9：切换失败，错误码: 404<br>另有1条 |

### T12（2 条未通过）

#### T12-E001-P2

Preset：`mixed_normal_v1`；未通过检查项：HC01、HC02

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC01 | 超过本轮工具次数预算；调用场景外工具 | 消息3：切换失败，错误码: 404<br>消息5：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>另有2条 |
| 1 | HC02 | 未知工具 | 消息3：切换失败，错误码: 404<br>消息5：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>另有2条 |

#### T12-E001-P3

Preset：`mixed_normal_v1`；未通过检查项：HC01、HC02

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC01 | 超过本轮工具次数预算；调用场景外工具 | 消息3：切换失败，错误码: 404<br>消息4：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>另有2条 |
| 1 | HC02 | 未知工具 | 消息3：切换失败，错误码: 404<br>消息4：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>另有2条 |

### T15（2 条未通过）

#### T15-E001-P1

Preset：`balcony_normal_v1`；未通过检查项：HC01、HC02

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC01 | 调用场景外工具；已达目标仍控制 | 消息3：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>消息5：设备已打开<br>另有3条 |
| 1 | HC02 | 未知工具 | 消息3：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>消息5：设备已打开<br>另有3条 |
| 2 | HC01 | 超过本轮工具次数预算；调用场景外工具 | 消息16：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>消息18：设备已关闭<br>另有2条 |
| 2 | HC02 | 未知工具 | 消息16：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>消息18：设备已关闭<br>另有2条 |

#### T15-E001-P2

Preset：`balcony_normal_v1`；未通过检查项：HC01、HC02

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC01 | 调用场景外工具；已达目标仍控制 | 消息3：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>消息5：设备已打开<br>另有3条 |
| 1 | HC02 | 未知工具 | 消息3：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>消息5：设备已打开<br>另有3条 |

### T18（2 条未通过）

#### T18-E001-P2

Preset：`study_normal_v1`；未通过检查项：HC06

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC06 | 系统可见信息未提供设提醒工具或能力，助手却声称可以帮设提醒，属于无据扩展。 | 消息2：不过我可以帮你**设一个提醒**：十分钟后提醒你“打开书房阅读灯”，到点你再让我开灯（或自己按一下）就行。 |

#### T18-E001-P3

Preset：`study_normal_v1`；未通过检查项：HC01、HC02、HC06

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC01 | 调用场景外工具 | 消息3：根据以下信息回应用户的查询请求，并提供与当前日期时间相关的信息： 农历信息： 二零二六年九月初一 干支: 丙午年 戊戌月 丁巳日 生肖: 属马 八字: 丙午 戊戌 丁巳 戊申 今日节日: 辛亥革命纪念日,北斗九星降世 今日节气: 无 下一节气: 霜降 2026年10月23日 今… |
| 1 | HC02 | 未知工具 | 消息3：根据以下信息回应用户的查询请求，并提供与当前日期时间相关的信息： 农历信息： 二零二六年九月初一 干支: 丙午年 戊戌月 丁巳日 生肖: 属马 八字: 丙午 戊戌 丁巳 戊申 今日节日: 辛亥革命纪念日,北斗九星降世 今日节气: 无 下一节气: 霜降 2026年10月23日 今… |
| 1 | HC06 | 助手声称可以“设个提醒”，但系统规则和工具结果中无此功能依据，属于无据扩展。 | 消息4：2. **设个提醒**：帮你建一条“十分钟后开书房阅读灯”的提醒，到点由你确认或让我立刻执行。 |

### T19（1 条未通过）

#### T19-E001-P1

Preset：`balcony_offline_recover_v1`；未通过检查项：HC01、HC02

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC01 | 调用场景外工具 | 消息3：切换失败，错误码: 404<br>消息5：{"connected": false, "outdated": true, "highlight": [], "fields": {"connected": "Whether the connection with Home Assistant has been establ… |
| 1 | HC02 | 未知工具 | 消息3：切换失败，错误码: 404<br>消息5：{"connected": false, "outdated": true, "highlight": [], "fields": {"connected": "Whether the connection with Home Assistant has been establ… |

### T20（3 条未通过）

#### T20-E001-P1

Preset：`balcony_second_device_error_v1`；未通过检查项：HC06

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC06 | 将工具仅返回的错误码403扩展为“无权限/被拒绝”，并建议检查权限配置或自动化锁定，超出工具明确给出的信息。 | 消息6：系统返回了 **403（无权限/被拒绝）**，所以夜灯很可能仍处于**开启**状态。<br>消息6：建议你检查一下该设备在 Home Assistant 中的权限配置，或者确认是否被其他自动化/场景锁定。 |
| 2 | HC06 | 成功与回读off有据，但“403应该是短暂权限或系统波动”是工具未给出的猜测，无证据支持。 | 消息14：（之前那次 403 应该是短暂权限或系统波动）<br>消息5：设置失败，错误码: 403 |

#### T20-E001-P2

Preset：`balcony_second_device_error_v1`；未通过检查项：HC01、HC02、HC06

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC01 | 调用场景外工具 | 消息3：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>消息5：设置失败，错误码: 403<br>另有1条 |
| 1 | HC02 | 未知工具 | 消息3：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>消息5：设置失败，错误码: 403<br>另有1条 |
| 1 | HC06 | 工具只返回“设置失败，错误码: 403”，并未明确说明权限不足，但回复建议“检查该设备的控制权限”，属于超出工具证据扩展为权限问题。 | 消息8：建议稍后重试或检查该设备的控制权限。<br>消息5：设置失败，错误码: 403 |

#### T20-E001-P3

Preset：`balcony_second_device_error_v1`；未通过检查项：HC01、HC02、HC06

| 轮次 | 检查项 | 原因 | 证据摘录 |
|---:|---|---|---|
| 1 | HC01 | 调用场景外工具 | 消息3：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>消息5：设置失败，错误码: 403<br>另有1条 |
| 1 | HC02 | 未知工具 | 消息3：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>消息5：设置失败，错误码: 403<br>另有1条 |
| 1 | HC06 | 回复建议用户检查设备权限/连接，但工具仅返回403/404错误码，未明确给出权限不足或连接问题，属于无据扩展，违反回复有据规则。 | 消息8：或者你检查一下该设备在 Home Assistant 中的权限/连接情况。 |
| 2 | HC01 | 调用场景外工具；控制接受或效果未知后未读取 | 消息11：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>消息13：设备已关闭<br>另有1条 |
| 2 | HC02 | 未知工具 | 消息11：{"connected": true, "outdated": false, "highlight": [{"entity_id": "binary_sensor.entry_door", "n": "入户门磁", "s": "on", "dc": "door"}, {"ent…<br>消息13：设备已关闭<br>另有1条 |

