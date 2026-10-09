# 数据准备报告

SFT 训练数据集已生成，目标模型训练适配待验证。

源轨迹 599 条；SFT 训练数据 556 条；未通过 28 条；待复核 15 条；重复 0 条。

`train.jsonl` 已生成完整 messages 和逐条 tools；未运行训练，也未完成目标模型模板及损失掩码验证。

## 1 来源与数量

| 批次文件 | 场景 | 数量 |
|---|---|---:|
| data/raw/weather/conversations.json | weather | 300 |
| data/raw/home_switch/conversations.json | home_switch | 299 |

## 2 任务覆盖

只统计已有字段。表中为不同取值数及缺失样本数；每个具体取值的样本数见 inventory.json。多标签数不能相加当作样本总数。

| 场景 | 字段 | 不同取值数 | 未提供样本数 |
|---|---|---:|---:|
| home_switch | template_id | 20 | 0 |
| home_switch | variable_group_id | 100 | 0 |
| home_switch | question_pattern_id | 3 | 0 |
| home_switch | variant_id | 9 | 254 |
| home_switch | scenario_ids | 15 | 0 |
| weather | template_id | 20 | 0 |
| weather | variable_group_id | 100 | 0 |
| weather | question_pattern_id | 3 | 0 |
| weather | variant_id | 0 | 300 |
| weather | scenario_ids | 28 | 0 |

## 3 对话结构

轮数仅统计真实用户消息；原始长度含 system 和运行器消息。字符数不是 token 数，P90 使用最近秩法。

| 场景 | 单轮 | 多轮 | 无用户轮 |
|---|---:|---:|---:|
| home_switch | 87 | 212 | 0 |
| weather | 165 | 135 | 0 |

| 场景 | 指标 | 最小值 | 中位数 | P90 | 最大值 |
|---|---|---:|---:|---:|---:|
| 合计 | 每条消息数 | 3 | 7 | 13 | 24 |
| 合计 | 每条正文字符数 | 385 | 1278 | 4812 | 10910 |
| 合计 | 每条工具调用数 | 0 | 1 | 4 | 8 |
| 合计 | 每次调用参数字符数 | 2 | 21 | 66 | 68 |
| home_switch | 每条消息数 | 3 | 9 | 15 | 24 |
| home_switch | 每条正文字符数 | 1249 | 3605 | 7121 | 10910 |
| home_switch | 每条工具调用数 | 0 | 3 | 5 | 8 |
| home_switch | 每次调用参数字符数 | 2 | 21.0 | 66 | 68 |
| weather | 每条消息数 | 3 | 5.0 | 9 | 9 |
| weather | 每条正文字符数 | 385 | 846.5 | 1140 | 1324 |
| weather | 每条工具调用数 | 0 | 1.0 | 2 | 2 |
| weather | 每次调用参数字符数 | 17 | 35 | 48 | 49 |

## 处理结果与异常说明

此处用于核对数据去向，不增加盘点维度。

| 场景 | 训练数据 | 未通过 | 待复核 | 重复 |
|---|---:|---:|---:|---:|
| home_switch | 273 | 11 | 15 | 0 |
| weather | 283 | 17 | 0 | 0 |

- 待复核：`runtime_injected_messages`，15 条。原文保留在 raw，通过 review.jsonl 的 source_index 和 source_sample_id 回查。

评分采用最新修订版本。本次读取并校验已有评分、检查项和证据，没有重新调用模型评分。

未通过样本可能可用于后续 DPO rejected；当前不做适用性评估或配对。

输入不追加元数据日期、时区；家居目录保留原始 system 可见文本，工具按每条原轨迹保留。天气工具为恢复版本，来源与校验值记录在 manifest.json。

下一阶段直接使用 train.jsonl 验证 Qwen3.5-9B 模板渲染、工具定义和 assistant-only 损失标签，通过后冻结版本并试跑。
测试由独立评估种子生成器负责，本次不划分测试集，不生成覆盖不足报告或补数建议。
