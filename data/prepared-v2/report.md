# 数据准备报告

SFT 训练数据集已生成，目标模型训练适配待验证。

源轨迹 677 条；SFT 训练数据 606 条；未通过 51 条；待复核 20 条；重复 0 条。

`train.jsonl` 已生成完整 messages 和逐条 tools；未运行训练，也未完成目标模型模板及损失掩码验证。

## 1 来源与数量

| 批次文件 | 场景 | 数量 |
|---|---|---:|
| weather-conversations.json | weather | 320 |
| home_switch-conversations.json | home_switch | 357 |

## 2 任务覆盖

只统计已有字段。表中为不同取值数及缺失样本数；每个具体取值的样本数见 inventory.json。多标签数不能相加当作样本总数。

| 场景 | 字段 | 不同取值数 | 未提供样本数 |
|---|---|---:|---:|
| home_switch | template_id | 20 | 0 |
| home_switch | variable_group_id | 158 | 0 |
| home_switch | question_pattern_id | 3 | 0 |
| home_switch | variant_id | 9 | 291 |
| home_switch | scenario_ids | 15 | 0 |
| weather | template_id | 20 | 0 |
| weather | variable_group_id | 120 | 0 |
| weather | question_pattern_id | 3 | 0 |
| weather | variant_id | 0 | 320 |
| weather | scenario_ids | 28 | 0 |

## 3 对话结构

轮数仅统计真实用户消息；原始长度含 system 和运行器消息。字符数不是 token 数，P90 使用最近秩法。

| 场景 | 单轮 | 多轮 | 无用户轮 |
|---|---:|---:|---:|
| home_switch | 88 | 269 | 0 |
| weather | 170 | 150 | 0 |

| 场景 | 指标 | 最小值 | 中位数 | P90 | 最大值 |
|---|---|---:|---:|---:|---:|
| 合计 | 每条消息数 | 3 | 7 | 13 | 24 |
| 合计 | 每条正文字符数 | 385 | 2231 | 5313 | 10910 |
| 合计 | 每条工具调用数 | 0 | 1 | 4 | 8 |
| 合计 | 每次调用参数字符数 | 2 | 21 | 66 | 69 |
| home_switch | 每条消息数 | 3 | 9 | 15 | 24 |
| home_switch | 每条正文字符数 | 1249 | 3625 | 7121 | 10910 |
| home_switch | 每条工具调用数 | 0 | 3 | 5 | 8 |
| home_switch | 每次调用参数字符数 | 2 | 21 | 66 | 69 |
| weather | 每条消息数 | 3 | 5.0 | 9 | 9 |
| weather | 每条正文字符数 | 385 | 855.5 | 1203 | 2251 |
| weather | 每条工具调用数 | 0 | 1.0 | 2 | 2 |
| weather | 每次调用参数字符数 | 17 | 35.0 | 48 | 49 |

## 处理结果与异常说明

此处用于核对数据去向，不增加盘点维度。

| 场景 | 训练数据 | 未通过 | 待复核 | 重复 |
|---|---:|---:|---:|---:|
| home_switch | 310 | 31 | 16 | 0 |
| weather | 296 | 20 | 4 | 0 |

- 待复核：`evidence_review:工具只返回城市未匹配，回答却断言该城市并不真实存在，超出该查询的证据范围。`，1 条。原文保留在 raw，通过 review.jsonl 的 source_index 和 source_sample_id 回查。
- 待复核：`evidence_review:已承认没有逐小时数据，仍推断下午三点大概率位于偏暖一端；不作为可靠的逐时信息缺失示范。`，1 条。原文保留在 raw，通过 review.jsonl 的 source_index 和 source_sample_id 回查。
- 待复核：`evidence_review:把当前0.0mm扩大成今天没有降雨，整日断言缺少依据。`，1 条。原文保留在 raw，通过 review.jsonl 的 source_index 和 source_sample_id 回查。
- 待复核：`evidence_review:第一轮将6天后澄清成往前数第6天，时间方向表述混乱；末轮日期虽正确，仍暂不入库。`，1 条。原文保留在 raw，通过 review.jsonl 的 source_index 和 source_sample_id 回查。
- 待复核：`runtime_injected_messages`，16 条。原文保留在 raw，通过 review.jsonl 的 source_index 和 source_sample_id 回查。

本次统一工具：get_lunar、get_news_from_newsnow、get_weather、handle_exit_intent、hass_get_state、hass_set_state、play_music、state_hub_snapshot、task_engine_control。

本导出步骤只读取并校验评分，不调用模型。各来源的评分沿用或更新范围见 manifest.json 的 score_policy；不能把导出成功理解为全量按新版规则重评。

未通过样本可能可用于后续 DPO rejected；当前不做适用性评估或配对。

输入不追加元数据日期、时区；家居目录保留原始 system 可见文本。全部训练样本使用 tools.json 中相同的完整非 MCP 工具列表，原工具范围仅用于历史评分追溯。定义与来源记录在 tools-source.json 和 manifest.json。

下一阶段直接使用 train.jsonl 验证 Qwen3.5-9B 模板渲染、工具定义和 assistant-only 损失标签，通过后冻结版本并试跑。
测试由独立评估种子生成器负责，本次不划分测试集，不生成覆盖不足报告或补数建议。
